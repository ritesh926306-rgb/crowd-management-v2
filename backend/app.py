"""
Venue Entry & Smart Crowd Management System
Backend Application with Flask, Dual MySQL / SQLite Support, HMAC-SHA256 Security, and Dynamic QR Generation.
"""

import os
import io
import csv
import hmac
import hashlib
import sqlite3
import datetime
import qrcode
import base64
import secrets
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, Response, jsonify
)
from dotenv import load_dotenv

# Optional PyMySQL for MySQL database connections
try:
    import pymysql
    import pymysql.cursors
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

# ----------------- CONFIGURATION & SECRETS -----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

# Load .env securely (Never expose keys in public code)
env_path = os.path.join(ROOT_DIR, ".env")
if not os.path.exists(env_path):
    env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
template_folder = os.path.join(FRONTEND_DIR, "templates") if os.path.exists(os.path.join(FRONTEND_DIR, "templates")) else os.path.join(BASE_DIR, "templates")
static_folder = os.path.join(FRONTEND_DIR, "static") if os.path.exists(os.path.join(FRONTEND_DIR, "static")) else os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder, static_url_path="/static")

# Secure Random Fallbacks (prevents predictable keys if .env is missing)
_flask_key = os.environ.get("FLASK_SECRET_KEY")
if not _flask_key:
    _flask_key = secrets.token_hex(32)
app.secret_key = _flask_key

_hmac_key = os.environ.get("HMAC_SECRET_KEY")
if not _hmac_key:
    _hmac_key = secrets.token_hex(32)
HMAC_SECRET_KEY = _hmac_key.encode("utf-8")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
GUARD_PIN = os.environ.get("GUARD_PIN", "guard123")
GUARD_PIN_REQUIRED = os.environ.get("GUARD_PIN_REQUIRED", "false").lower() in ("true", "1")

# Database Configuration
DB_TYPE = os.environ.get("DB_TYPE", "sqlite").lower()
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "venue_crowd")

if os.environ.get("VERCEL"):
    SQLITE_PATH = "/tmp/venue_crowd.db"
else:
    SQLITE_PATH = os.path.join(BASE_DIR, "venue_crowd.db")

# Venue Exit Gates configuration
GATES_CONFIG = [
    {
        "group": "Group A",
        "gate_id": "exit_1",
        "name": "Exit 1 (West)",
        "zone": "Zone Alpha (West Gate)",
        "color": "#00ADB5", # Teal
        "description": "Proceed West towards West Boulevard & Transit Hub 1"
    },
    {
        "group": "Group B",
        "gate_id": "exit_2",
        "name": "Exit 2 (North)",
        "zone": "Zone Beta (North Gate)",
        "color": "#1E3E62", # Navy
        "description": "Proceed North towards Main Highway & North Parking"
    },
    {
        "group": "Group C",
        "gate_id": "exit_3",
        "name": "Exit 3 (East)",
        "zone": "Zone Gamma (East Gate)",
        "color": "#D97706", # Amber
        "description": "Proceed East towards East Plaza & Metro Shuttle"
    },
    {
        "group": "Group D",
        "gate_id": "exit_4",
        "name": "Exit 4 (South)",
        "zone": "Zone Delta (South Gate)",
        "color": "#7C3AED", # Violet
        "description": "Proceed South towards South Promenade & Taxi Stand"
    }
]

# ----------------- DATABASE UTILITIES (MySQL + SQLite) -----------------

class UnifiedCursor:
    """Cursor adapter providing uniform parameter replacement and dictionary access."""
    def __init__(self, raw_cursor, is_mysql=False):
        self.cursor = raw_cursor
        self.is_mysql = is_mysql

    def execute(self, query, params=None):
        if self.is_mysql:
            # Convert SQLite parameter placeholder ? to MySQL %s
            query = query.replace("?", "%s")
        if params is None:
            return self.cursor.execute(query)
        return self.cursor.execute(query, params)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

class UnifiedConnection:
    """Connection adapter supporting both MySQL (via PyMySQL) and SQLite."""
    def __init__(self, raw_conn, is_mysql=False):
        self.conn = raw_conn
        self.is_mysql = is_mysql

    def cursor(self):
        if self.is_mysql:
            return UnifiedCursor(self.conn.cursor(), is_mysql=True)
        return UnifiedCursor(self.conn.cursor(), is_mysql=False)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

def get_db_connection():
    """Returns an active database connection (MySQL if configured, with SQLite fallback)."""
    if DB_TYPE == "mysql" and HAS_PYMYSQL:
        try:
            raw_conn = pymysql.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False
            )
            # Enable PIPES_AS_CONCAT so || concatenation operates identically across MySQL and SQLite
            with raw_conn.cursor() as cur:
                cur.execute("SET sql_mode=(SELECT CONCAT(COALESCE(@@sql_mode, ''), ',PIPES_AS_CONCAT'))")
            return UnifiedConnection(raw_conn, is_mysql=True)
        except Exception as e:
            print(f"[DATABASE WARNING] Unable to connect to MySQL at {DB_HOST}:{DB_PORT} ({e}). Falling back to SQLite.")
            
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return UnifiedConnection(conn, is_mysql=False)

def init_db():
    """Initialize database tables for either MySQL or SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if conn.is_mysql:
        # MySQL Production Tables
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            reg_code VARCHAR(64) UNIQUE NOT NULL,
            language VARCHAR(10) NOT NULL DEFAULT 'en',
            primary_name VARCHAR(255) NOT NULL,
            mobile VARCHAR(20) NOT NULL,
            age INT UNSIGNED NOT NULL,
            address TEXT NOT NULL,
            group_count INT UNSIGNED NOT NULL DEFAULT 1,
            assigned_group VARCHAR(50) NOT NULL,
            assigned_gate VARCHAR(100) NOT NULL,
            gate_id VARCHAR(50) NOT NULL,
            hmac_signature VARCHAR(128) NOT NULL,
            created_at DATETIME NOT NULL,
            checked_in TINYINT(1) DEFAULT 0,
            checked_in_at DATETIME NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            reg_id BIGINT UNSIGNED NOT NULL,
            member_name VARCHAR(255) NOT NULL,
            member_age INT UNSIGNED NOT NULL,
            member_mobile VARCHAR(20) DEFAULT '',
            FOREIGN KEY (reg_id) REFERENCES registrations (id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
    else:
        # SQLite Tables
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reg_code TEXT UNIQUE NOT NULL,
            language TEXT NOT NULL DEFAULT 'en',
            primary_name TEXT NOT NULL,
            mobile TEXT NOT NULL,
            age INTEGER NOT NULL,
            address TEXT NOT NULL,
            group_count INTEGER NOT NULL DEFAULT 1,
            assigned_group TEXT NOT NULL,
            assigned_gate TEXT NOT NULL,
            gate_id TEXT NOT NULL,
            hmac_signature TEXT NOT NULL,
            created_at TEXT NOT NULL,
            checked_in INTEGER DEFAULT 0,
            checked_in_at TEXT
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reg_id INTEGER NOT NULL,
            member_name TEXT NOT NULL,
            member_age INTEGER NOT NULL,
            member_mobile TEXT,
            FOREIGN KEY (reg_id) REFERENCES registrations (id) ON DELETE CASCADE
        )
        """)
    
    conn.commit()
    conn.close()

# Auto-initialize database on application launch and serverless cold-starts
_db_ready = False

@app.before_request
def ensure_db_ready():
    global _db_ready
    if not _db_ready:
        init_db()
        _db_ready = True

@app.context_processor
def inject_server_mode():
    return {"is_flask_backend": True}

# ----------------- SECURITY & HELPER FUNCTIONS -----------------

def generate_hmac_signature(reg_code: str, name: str, mobile: str, gate: str) -> str:
    """Generate SHA256 HMAC signature binding registration data with secret key."""
    canonical_data = f"{reg_code.strip()}|{name.strip().upper()}|{mobile.strip()}|{gate.strip()}".encode("utf-8")
    return hmac.new(HMAC_SECRET_KEY, canonical_data, hashlib.sha256).hexdigest()

def verify_hmac_signature(reg_code: str, name: str, mobile: str, gate: str, signature: str) -> bool:
    """Cryptographically verify signature against recomputed HMAC."""
    expected_sig = generate_hmac_signature(reg_code, name, mobile, gate)
    return hmac.compare_digest(expected_sig, signature)

def generate_qr_base64(data_string: str) -> str:
    """Generate QR code and return as Base64 data URI string."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0B192C", back_color="#FFFFFF")
    
    buffer = io.BytesIO()
    img.save(buffer)
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"

def determine_smart_split_gate() -> dict:
    """
    Capacity-based Crowd Split Logic:
    Calculates current total headcount across all 4 gates.
    Assigns incoming group to the exit gate with the lowest active visitor load.
    Prevents stampedes and bottlenecks at venue exits.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT gate_id, SUM(group_count) as total_headcount
        FROM registrations
        GROUP BY gate_id
    """)
    rows = cursor.fetchall()
    conn.close()
    
    gate_counts = {g["gate_id"]: 0 for g in GATES_CONFIG}
    for row in rows:
        if row["gate_id"] in gate_counts:
            gate_counts[row["gate_id"]] = row["total_headcount"] or 0
            
    # Find the gate with minimum load
    min_gate_id = min(gate_counts, key=gate_counts.get)
    for g in GATES_CONFIG:
        if g["gate_id"] == min_gate_id:
            return g
            
    return GATES_CONFIG[0]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin login required to access this dashboard.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

def guard_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if GUARD_PIN_REQUIRED and not (session.get("guard_logged_in") or session.get("is_admin")):
            flash("Guard PIN authentication required to operate terminal.", "warning")
            return redirect(url_for("guard_login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function

# ----------------- APPLICATION ROUTES -----------------

@app.route("/")
@app.route("/index.html")
def index():
    """Visitor registration form & language selection page."""
    lang = request.args.get("lang", "en")
    return render_template("index.html", lang=lang, gates=GATES_CONFIG)

@app.route("/register", methods=["POST"])
def register():
    """Handle new visitor registration with dynamic members and capacity split."""
    language = request.form.get("language", "en")
    primary_name = request.form.get("primary_name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    age_str = request.form.get("age", "").strip()
    address = request.form.get("address", "").strip()
    
    # Basic validation
    if not primary_name or not mobile or not age_str or not address:
        flash("Please fill in all mandatory primary visitor fields.", "error")
        return redirect(url_for("index", lang=language))
    
    if not mobile.isdigit() or len(mobile) != 10:
        flash("Please enter a valid 10-digit mobile number.", "error")
        return redirect(url_for("index", lang=language))
        
    try:
        age = int(age_str)
        if age < 1 or age > 120:
            raise ValueError()
    except ValueError:
        flash("Please enter a valid age between 1 and 120.", "error")
        return redirect(url_for("index", lang=language))

    # Parse accompanying members
    member_names = request.form.getlist("member_name[]")
    member_ages = request.form.getlist("member_age[]")
    member_mobiles = request.form.getlist("member_mobile[]")
    
    members_data = []
    for m_name, m_age, m_mob in zip(member_names, member_ages, member_mobiles):
        m_name = m_name.strip()
        m_age = m_age.strip()
        m_mob = m_mob.strip()
        if m_name and m_age:
            try:
                parsed_age = int(m_age)
                members_data.append({
                    "name": m_name,
                    "age": parsed_age,
                    "mobile": m_mob if (m_mob.isdigit() and len(m_mob) == 10) else ""
                })
            except ValueError:
                pass
                
    total_group_count = 1 + len(members_data)
    
    # Smart crowd split: Allocate to least loaded exit gate
    assigned = determine_smart_split_gate()
    
    # Generate Unique Registration Code
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    rand_suffix = hashlib.md5(f"{mobile}{timestamp_str}".encode()).hexdigest()[:6].upper()
    reg_code = f"REG-{rand_suffix}"
    
    # Compute HMAC Anti-Fraud Signature
    hmac_sig = generate_hmac_signature(reg_code, primary_name, mobile, assigned["name"])
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save to SQLite Database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO registrations (
            reg_code, language, primary_name, mobile, age, address,
            group_count, assigned_group, assigned_gate, gate_id,
            hmac_signature, created_at, checked_in
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, (
        reg_code, language, primary_name, mobile, age, address,
        total_group_count, assigned["group"], assigned["name"], assigned["gate_id"],
        hmac_sig, created_at
    ))
    
    reg_id = cursor.lastrowid
    
    for member in members_data:
        cursor.execute("""
            INSERT INTO group_members (reg_id, member_name, member_age, member_mobile)
            VALUES (?, ?, ?, ?)
        """, (reg_id, member["name"], member["age"], member["mobile"]))
        
    conn.commit()
    conn.close()
    
    return redirect(url_for("view_pass", reg_code=reg_code))

@app.route("/pass/<reg_code>")
def view_pass(reg_code):
    """Display official Digital Entry Pass / ID Card with dynamic QR code & route map."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM registrations WHERE reg_code = ?", (reg_code,))
    reg = cursor.fetchone()
    
    if not reg:
        conn.close()
        flash("Pass not found for the requested registration code.", "error")
        return redirect(url_for("index"))
        
    cursor.execute("SELECT * FROM group_members WHERE reg_id = ?", (reg["id"],))
    members = cursor.fetchall()
    conn.close()
    
    # Host-aware verification URL for scanning
    host_url = request.host_url.rstrip("/")
    verification_url = f"{host_url}/verify/{reg['reg_code']}"
    
    # Render Dynamic Verification QR Code
    qr_base64 = generate_qr_base64(verification_url)
    
    # Find gate details for styling & map route
    gate_info = next((g for g in GATES_CONFIG if g["gate_id"] == reg["gate_id"]), GATES_CONFIG[0])
    
    return render_template(
        "pass.html",
        reg=reg,
        members=members,
        qr_code=qr_base64,
        verification_url=verification_url,
        gate_info=gate_info
    )

@app.route("/pass.html")
def pass_html_redirect():
    code = request.args.get("code")
    if code:
        return redirect(url_for("view_pass", reg_code=code))
    return redirect(url_for("index"))

# ----------------- SECURITY GUARD TERMINAL & VERIFICATION -----------------

@app.route("/guard/login", methods=["GET", "POST"])
def guard_login():
    """Guard PIN authentication terminal."""
    if session.get("guard_logged_in") or session.get("is_admin"):
        return redirect(url_for("verify_terminal"))
        
    next_url = request.args.get("next") or url_for("verify_terminal")
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        if pin == GUARD_PIN:
            session["guard_logged_in"] = True
            session.permanent = True
            flash("Guard terminal unlocked. Scanner active.", "success")
            return redirect(next_url)
        else:
            flash("Invalid Guard Access PIN. Entry denied.", "error")
            
    return render_template("guard_login.html")

@app.route("/guard/logout")
def guard_logout():
    """Lock Guard Terminal."""
    session.pop("guard_logged_in", None)
    flash("Guard terminal locked successfully.", "info")
    return redirect(url_for("verify_terminal"))

@app.route("/verify", strict_slashes=False)
@app.route("/verify.html")
@app.route("/guard", strict_slashes=False)
@guard_required
def verify_terminal():
    """
    Standby Security Guard Scanner & Verification Terminal.
    Loads camera scanner ready to scan passes in real time.
    """
    return render_template(
        "verify.html",
        is_valid=None,
        tamper_reason=None,
        reg=None,
        members=[],
        gate_info=None,
        is_already_checked_in=False,
        guard_active=bool(session.get("guard_logged_in") or session.get("is_admin"))
    )

@app.route("/verify/<reg_code>")
@guard_required
def verify_pass(reg_code):
    """
    Security Guard Verification Terminal:
    Performs cryptographic HMAC recalculation, anti-passback check, and displays full pass details.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM registrations WHERE reg_code = ?", (reg_code,))
    reg = cursor.fetchone()
    
    if not reg:
        conn.close()
        return render_template(
            "verify.html",
            is_valid=False,
            tamper_reason="REGISTRATION CODE NOT FOUND IN DATABASE. POTENTIAL COUNTERFEIT PASS.",
            reg=None,
            members=[],
            gate_info=None,
            is_already_checked_in=False,
            guard_active=bool(session.get("guard_logged_in") or session.get("is_admin"))
        )
        
    cursor.execute("SELECT * FROM group_members WHERE reg_id = ?", (reg["id"],))
    members = cursor.fetchall()
    conn.close()
    
    # Verify Cryptographic HMAC Integrity
    is_hmac_valid = verify_hmac_signature(
        reg["reg_code"],
        reg["primary_name"],
        reg["mobile"],
        reg["assigned_gate"],
        reg["hmac_signature"]
    )
    
    gate_info = next((g for g in GATES_CONFIG if g["gate_id"] == reg["gate_id"]), GATES_CONFIG[0])
    is_already_checked_in = (reg["checked_in"] == 1)
    
    if not is_hmac_valid:
        return render_template(
            "verify.html",
            is_valid=False,
            tamper_reason="CRYPTOGRAPHIC SIGNATURE MISMATCH! DATA TAMPERING DETECTED.",
            reg=reg,
            members=members,
            gate_info=gate_info,
            is_already_checked_in=is_already_checked_in,
            guard_active=bool(session.get("guard_logged_in") or session.get("is_admin"))
        )
        
    return render_template(
        "verify.html",
        is_valid=True,
        tamper_reason=None,
        reg=reg,
        members=members,
        gate_info=gate_info,
        is_already_checked_in=is_already_checked_in,
        guard_active=bool(session.get("guard_logged_in") or session.get("is_admin"))
    )

@app.route("/api/verify/<reg_code>", methods=["GET"])
def api_verify_pass(reg_code):
    """
    Real-time JSON Verification API:
    Allows the in-browser camera scanner to verify passes instantly without full page reloads.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM registrations WHERE reg_code = ?", (reg_code,))
    reg = cursor.fetchone()
    
    if not reg:
        conn.close()
        return jsonify({
            "success": False,
            "is_valid": False,
            "tamper_reason": "REGISTRATION CODE NOT FOUND IN DATABASE. POTENTIAL COUNTERFEIT PASS."
        }), 404
        
    cursor.execute("SELECT * FROM group_members WHERE reg_id = ?", (reg["id"],))
    members_raw = cursor.fetchall()
    conn.close()
    
    members = [
        {
            "member_name": m["member_name"],
            "member_age": m["member_age"],
            "member_mobile": m["member_mobile"] or ""
        }
        for m in members_raw
    ]
    
    is_hmac_valid = verify_hmac_signature(
        reg["reg_code"],
        reg["primary_name"],
        reg["mobile"],
        reg["assigned_gate"],
        reg["hmac_signature"]
    )
    
    gate_info = next((g for g in GATES_CONFIG if g["gate_id"] == reg["gate_id"]), GATES_CONFIG[0])
    is_already_checked_in = (reg["checked_in"] == 1)
    
    reg_dict = {
        "id": reg["id"],
        "reg_code": reg["reg_code"],
        "primary_name": reg["primary_name"],
        "mobile": reg["mobile"],
        "age": reg["age"],
        "address": reg["address"],
        "group_count": reg["group_count"],
        "assigned_group": reg["assigned_group"],
        "assigned_gate": reg["assigned_gate"],
        "gate_id": reg["gate_id"],
        "checked_in": reg["checked_in"],
        "checked_in_at": reg["checked_in_at"] or "",
        "created_at": reg["created_at"],
        "hmac_signature": reg["hmac_signature"]
    }
    
    if not is_hmac_valid:
        return jsonify({
            "success": True,
            "is_valid": False,
            "is_hmac_valid": False,
            "tamper_reason": "CRYPTOGRAPHIC SIGNATURE MISMATCH! DATA TAMPERING DETECTED.",
            "reg": reg_dict,
            "members": members,
            "gate_info": gate_info,
            "is_already_checked_in": is_already_checked_in
        })
        
    return jsonify({
        "success": True,
        "is_valid": True,
        "is_hmac_valid": True,
        "tamper_reason": None,
        "reg": reg_dict,
        "members": members,
        "gate_info": gate_info,
        "is_already_checked_in": is_already_checked_in
    })

@app.route("/api/check-in/<reg_code>", methods=["POST"])
def api_check_in(reg_code):
    """Security guard check-in confirmation toggle."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, checked_in FROM registrations WHERE reg_code = ?", (reg_code,))
    reg = cursor.fetchone()
    
    if not reg:
        conn.close()
        return jsonify({"success": False, "message": "Record not found"}), 404
        
    new_status = 1 if reg["checked_in"] == 0 else 0
    checked_in_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == 1 else None
    
    cursor.execute(
        "UPDATE registrations SET checked_in = ?, checked_in_at = ? WHERE id = ?",
        (new_status, checked_in_at, reg["id"])
    )
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "checked_in": new_status,
        "checked_in_at": checked_in_at
    })

# ----------------- ADMIN CONTROLS -----------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page with password protection."""
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
        
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            session.permanent = True
            flash("Welcome to Venue Command & Control Admin Panel.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid administrator password. Access denied.", "error")
            
    return render_template("login.html")

@app.route("/admin/logout")
def admin_logout():
    """Admin logout handler."""
    session.pop("is_admin", None)
    flash("Successfully logged out from Admin Panel.", "info")
    return redirect(url_for("admin_login"))

@app.route("/admin", strict_slashes=False)
@app.route("/admin.html")
@login_required
def admin_dashboard():
    """Private Admin Dashboard with real-time crowd analytics and registration table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all registrations with member aggregation
    cursor.execute("""
        SELECT r.*,
               COUNT(m.id) as accompanying_count,
               GROUP_CONCAT(m.member_name || ' (' || m.member_age || 'y)', ', ') as members_summary
        FROM registrations r
        LEFT JOIN group_members m ON r.id = m.reg_id
        GROUP BY r.id
        ORDER BY r.id DESC
    """)
    registrations = cursor.fetchall()
    
    # Total headcount & total passes
    cursor.execute("SELECT SUM(group_count) as total_people, COUNT(id) as total_passes FROM registrations")
    stats_row = cursor.fetchone()
    total_people = stats_row["total_people"] or 0
    total_passes = stats_row["total_passes"] or 0
    
    # Checked-in crowd
    cursor.execute("SELECT SUM(group_count) as admitted_people FROM registrations WHERE checked_in = 1")
    admitted_row = cursor.fetchone()
    admitted_people = admitted_row["admitted_people"] or 0
    
    # Gate capacity breakdown
    cursor.execute("""
        SELECT gate_id, SUM(group_count) as gate_headcount
        FROM registrations
        GROUP BY gate_id
    """)
    gate_counts = {row["gate_id"]: (row["gate_headcount"] or 0) for row in cursor.fetchall()}
    conn.close()
    
    # Prepare Gate Stats with percentages
    gate_analytics = []
    for g in GATES_CONFIG:
        count = gate_counts.get(g["gate_id"], 0)
        percentage = round((count / total_people * 100), 1) if total_people > 0 else 0
        gate_analytics.append({
            **g,
            "count": count,
            "percentage": percentage
        })
        
    # Entrance QR Code for Venue Signage (Points to Registration Page)
    host_url = request.host_url.rstrip("/")
    entrance_url = f"{host_url}/"
    entrance_qr_base64 = generate_qr_base64(entrance_url)
    
    return render_template(
        "admin.html",
        registrations=registrations,
        total_people=total_people,
        total_passes=total_passes,
        admitted_people=admitted_people,
        gate_analytics=gate_analytics,
        entrance_url=entrance_url,
        entrance_qr=entrance_qr_base64
    )

@app.route("/admin/entrance-poster")
@login_required
def entrance_poster():
    """Printable High-Resolution Static Entrance QR Code Poster for Venue Entry."""
    host_url = request.host_url.rstrip("/")
    entrance_url = f"{host_url}/"
    entrance_qr_base64 = generate_qr_base64(entrance_url)
    return render_template("entrance_poster.html", entrance_url=entrance_url, entrance_qr=entrance_qr_base64)

@app.route("/admin/export-csv")
@login_required
def export_csv():
    """Export all stored registrations and member details to RFC 4180 CSV."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT r.id, r.reg_code, r.created_at, r.language,
               r.primary_name, r.mobile, r.age, r.address,
               r.group_count, r.assigned_group, r.assigned_gate,
               r.checked_in, r.checked_in_at, r.hmac_signature,
               GROUP_CONCAT(m.member_name || ' [Age: ' || m.member_age || COALESCE(', Ph: ' || m.member_mobile, '') || ']', ' | ') as members_list
        FROM registrations r
        LEFT JOIN group_members m ON r.id = m.reg_id
        GROUP BY r.id
        ORDER BY r.id ASC
    """)
    records = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # CSV Header
    writer.writerow([
        "Reg ID", "Registration Code", "Timestamp", "Language",
        "Primary Visitor Name", "Mobile Number", "Age", "Common Address",
        "Total Group Size", "Assigned Group", "Assigned Exit Gate",
        "Checked In Status", "Checked In Timestamp", "Accompanying Group Members",
        "HMAC Security Hash"
    ])
    
    for r in records:
        writer.writerow([
            r["id"],
            r["reg_code"],
            r["created_at"],
            r["language"].upper(),
            r["primary_name"],
            r["mobile"],
            r["age"],
            r["address"],
            r["group_count"],
            r["assigned_group"],
            r["assigned_gate"],
            "ADMITTED" if r["checked_in"] == 1 else "PENDING",
            r["checked_in_at"] or "N/A",
            r["members_list"] or "None (Solo Visitor)",
            r["hmac_signature"]
        ])
        
    csv_data = output.getvalue()
    filename = f"venue_crowd_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@app.route("/admin/delete/<int:reg_id>", methods=["POST"])
@login_required
def delete_registration(reg_id):
    """Delete a registration record and its members (admin only)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM group_members WHERE reg_id = ?", (reg_id,))
    cursor.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
    conn.commit()
    conn.close()
    flash(f"Registration #{reg_id} deleted successfully.", "info")
    return redirect(url_for("admin_dashboard"))

# ----------------- MAIN INITIALIZATION -----------------

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"===============================================================")
    print(f" VENUE ENTRY & SMART CROWD MANAGEMENT SYSTEM RUNNING")
    print(f" Local URL:   http://127.0.0.1:{port}")
    print(f" Admin Panel: http://127.0.0.1:{port}/admin (Password: admin123)")
    print(f" Entry Poster: http://127.0.0.1:{port}/admin/entrance-poster")
    print(f"===============================================================")
    app.run(host="0.0.0.0", port=port, debug=True)
