"""
Venue Entry & Smart Crowd Management System
Backend Application with Flask, SQLite, HMAC-SHA256 Security, and Dynamic QR Generation.
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
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, Response, jsonify
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "venue-crowd-secret-key-2026-prod-99x")

# Cryptographic HMAC Secret Key for Anti-Fraud Pass Signature
HMAC_SECRET_KEY = os.environ.get("HMAC_SECRET_KEY", "SECURE_VENUE_HMAC_MASTER_KEY_2026_@ANTIFRAUD").encode("utf-8")

# Admin Default Credentials
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venue_crowd.db")

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

# ----------------- DATABASE UTILITIES -----------------

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Registrations table
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
    
    # Group members sub-table
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

# ----------------- APPLICATION ROUTES -----------------

@app.route("/")
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

@app.route("/verify/<reg_code>")
def verify_pass(reg_code):
    """
    Security Guard Verification Terminal:
    Performs cryptographic HMAC recalculation and checks pass validity.
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
            members=[]
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
    
    if not is_hmac_valid:
        return render_template(
            "verify.html",
            is_valid=False,
            tamper_reason="CRYPTOGRAPHIC SIGNATURE MISMATCH! DATA TAMPERING DETECTED.",
            reg=reg,
            members=members,
            gate_info=gate_info
        )
        
    return render_template(
        "verify.html",
        is_valid=True,
        tamper_reason=None,
        reg=reg,
        members=members,
        gate_info=gate_info
    )

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

@app.route("/admin")
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
