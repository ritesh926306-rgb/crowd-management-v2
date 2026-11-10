"""
Event Entry & Smart Crowd Management System
Backend Application with Flask, PostgreSQL / SQLite Support,
HMAC-SHA256 Security, bcrypt Password Hashing, Rate Limiting, and Dynamic QR Generation.
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
import math
from datetime import timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, Response, jsonify
)

# ---------------------------------------------------------------------------
# Optional python-dotenv with built-in .env parser fallback
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(dotenv_path=None):
        if not dotenv_path or not os.path.exists(dotenv_path):
            return
        try:
            with open(dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Optional bcrypt for password hashing
# ---------------------------------------------------------------------------
try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

# ---------------------------------------------------------------------------
# Optional Flask-Limiter for rate limiting
# ---------------------------------------------------------------------------
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    HAS_LIMITER = True
except ImportError:
    HAS_LIMITER = False

# ---------------------------------------------------------------------------
# Optional PyMySQL for MySQL database connections
# ---------------------------------------------------------------------------
try:
    import pymysql
    import pymysql.cursors
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

# ---------------------------------------------------------------------------
# Optional psycopg2 for PostgreSQL database connections
# ---------------------------------------------------------------------------
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# ---------------------------------------------------------------------------
# CONFIGURATION & SECRETS
# ---------------------------------------------------------------------------
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
template_folder = (
    os.path.join(FRONTEND_DIR, "templates")
    if os.path.exists(os.path.join(FRONTEND_DIR, "templates"))
    else os.path.join(BASE_DIR, "templates")
)
static_folder = (
    os.path.join(FRONTEND_DIR, "static")
    if os.path.exists(os.path.join(FRONTEND_DIR, "static"))
    else os.path.join(BASE_DIR, "static")
)

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder, static_url_path="/static")

# Secure Random Fallbacks (prevents predictable keys if .env is missing)
_flask_key = os.environ.get("FLASK_SECRET_KEY")
if not _flask_key:
    _flask_key = secrets.token_hex(32)
app.secret_key = _flask_key

# Session cookie security configuration
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=15)

_hmac_key = os.environ.get("HMAC_SECRET_KEY")
if not _hmac_key:
    _hmac_key = secrets.token_hex(32)
HMAC_SECRET_KEY = _hmac_key.encode("utf-8")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
GUARD_PIN = os.environ.get("GUARD_PIN", "guard123")
GUARD_PIN_REQUIRED = os.environ.get("GUARD_PIN_REQUIRED", "true").lower() in ("true", "1")
GUARD_SESSION_MINUTES = int(os.environ.get("GUARD_SESSION_MINUTES", 15))

# ---------------------------------------------------------------------------
# Database Configuration — SQLite (default), PostgreSQL (via DATABASE_URL),
# or MySQL (via DB_TYPE=mysql env var)
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_TYPE = os.environ.get("DB_TYPE", "sqlite").lower()
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "venue_crowd")

# Detect PostgreSQL from DATABASE_URL
if DATABASE_URL and DATABASE_URL.startswith("postgres"):
    DB_TYPE = "postgresql"

if os.environ.get("VERCEL"):
    SQLITE_PATH = "/tmp/venue_crowd.db"
else:
    SQLITE_PATH = os.path.join(BASE_DIR, "venue_crowd.db")

# ---------------------------------------------------------------------------
# Event Exit Gates configuration — generic event terminology
# ---------------------------------------------------------------------------
GATES_CONFIG = [
    {
        "group": "Group A",
        "gate_id": "exit_1",
        "name": "Exit 1 (West)",
        "zone": "Event Zone Alpha (West Gate)",
        "color": "#00ADB5",  # Teal
        "description": "Proceed West towards West Boulevard & Transit Hub 1"
    },
    {
        "group": "Group B",
        "gate_id": "exit_2",
        "name": "Exit 2 (North)",
        "zone": "Event Zone Beta (North Gate)",
        "color": "#1E3E62",  # Navy
        "description": "Proceed North towards Main Highway & North Parking"
    },
    {
        "group": "Group C",
        "gate_id": "exit_3",
        "name": "Exit 3 (East)",
        "zone": "Event Zone Gamma (East Gate)",
        "color": "#D97706",  # Amber
        "description": "Proceed East towards East Plaza & Metro Shuttle"
    },
    {
        "group": "Group D",
        "gate_id": "exit_4",
        "name": "Exit 4 (South)",
        "zone": "Event Zone Delta (South Gate)",
        "color": "#7C3AED",  # Violet
        "description": "Proceed South towards South Promenade & Taxi Stand"
    }
]

# ---------------------------------------------------------------------------
# Rate Limiter Setup
# ---------------------------------------------------------------------------
if HAS_LIMITER:
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[],
        storage_uri="memory://"
    )

# ---------------------------------------------------------------------------
# DATABASE UTILITIES (PostgreSQL + MySQL + SQLite)
# ---------------------------------------------------------------------------

class UnifiedCursor:
    """Cursor adapter providing uniform parameter replacement and dictionary access."""

    def __init__(self, raw_cursor, db_kind="sqlite"):
        self.cursor = raw_cursor
        self.db_kind = db_kind  # "sqlite", "mysql", or "postgresql"

    def execute(self, query, params=None):
        if self.db_kind in ("mysql", "postgresql"):
            # Convert SQLite ? placeholder to %s for MySQL/PostgreSQL
            query = query.replace("?", "%s")
        if params is None:
            return self.cursor.execute(query)
        return self.cursor.execute(query, params)

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        if self.db_kind == "postgresql" and isinstance(row, dict):
            return row
        return row

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):
        if self.db_kind == "postgresql":
            try:
                row = self.cursor.fetchone()
                if isinstance(row, dict) or hasattr(row, "get"):
                    return row.get("id") or (list(row.values())[0] if row else None)
                return row[0] if row else None
            except Exception:
                return None
        return self.cursor.lastrowid


class UnifiedConnection:
    """Connection adapter supporting PostgreSQL (psycopg2), MySQL (PyMySQL), and SQLite."""

    def __init__(self, raw_conn, db_kind="sqlite"):
        self.conn = raw_conn
        self.db_kind = db_kind
        # Expose is_mysql for legacy compat checks
        self.is_mysql = db_kind == "mysql"
        self.is_postgresql = db_kind == "postgresql"

    def cursor(self):
        if self.db_kind == "postgresql":
            raw = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            return UnifiedCursor(raw, db_kind="postgresql")
        if self.db_kind == "mysql":
            return UnifiedCursor(self.conn.cursor(), db_kind="mysql")
        return UnifiedCursor(self.conn.cursor(), db_kind="sqlite")

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def get_db_connection():
    """Returns an active database connection (PostgreSQL > MySQL > SQLite fallback)."""
    # --- PostgreSQL via DATABASE_URL ---
    if DB_TYPE == "postgresql" and HAS_PSYCOPG2 and DATABASE_URL:
        try:
            raw_conn = psycopg2.connect(DATABASE_URL)
            raw_conn.autocommit = False
            return UnifiedConnection(raw_conn, db_kind="postgresql")
        except Exception as e:
            print(f"[DATABASE WARNING] Unable to connect to PostgreSQL ({e}). Falling back to SQLite.")

    # --- MySQL via PyMySQL ---
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
            with raw_conn.cursor() as cur:
                cur.execute("SET sql_mode=(SELECT CONCAT(COALESCE(@@sql_mode, ''), ',PIPES_AS_CONCAT'))")
            return UnifiedConnection(raw_conn, db_kind="mysql")
        except Exception as e:
            print(f"[DATABASE WARNING] Unable to connect to MySQL at {DB_HOST}:{DB_PORT} ({e}). Falling back to SQLite.")

    # --- SQLite fallback ---
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
    except Exception:
        pass
    return UnifiedConnection(conn, db_kind="sqlite")


def _upsert_setting(cursor, conn, key, value):
    """Insert or update a system_settings row in a DB-agnostic way."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if conn.db_kind == "postgresql":
        cursor.execute(
            """
            INSERT INTO system_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = EXCLUDED.updated_at
            """,
            (key, value, now_str)
        )
    elif conn.db_kind == "mysql":
        cursor.execute(
            "REPLACE INTO system_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
            (key, value, now_str)
        )
    else:
        cursor.execute(
            "INSERT OR REPLACE INTO system_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
            (key, value, now_str)
        )


def init_db():
    """Initialize database tables for PostgreSQL, MySQL, or SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if conn.db_kind == "postgresql":
        # PostgreSQL production tables
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id BIGSERIAL PRIMARY KEY,
            reg_code VARCHAR(64) UNIQUE NOT NULL,
            language VARCHAR(10) NOT NULL DEFAULT 'en',
            primary_name VARCHAR(255) NOT NULL,
            mobile VARCHAR(20) NOT NULL,
            age INTEGER NOT NULL,
            address TEXT NOT NULL,
            group_count INTEGER NOT NULL DEFAULT 1,
            assigned_group VARCHAR(50) NOT NULL,
            assigned_gate VARCHAR(100) NOT NULL,
            gate_id VARCHAR(50) NOT NULL,
            hmac_signature VARCHAR(128) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            checked_in SMALLINT DEFAULT 0,
            checked_in_at TIMESTAMP NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            id BIGSERIAL PRIMARY KEY,
            reg_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
            member_name VARCHAR(255) NOT NULL,
            member_age INTEGER NOT NULL,
            member_mobile VARCHAR(20) DEFAULT ''
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            setting_key VARCHAR(100) PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        """)

    elif conn.db_kind == "mysql":
        # MySQL production tables
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            setting_key VARCHAR(100) PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

    else:
        # SQLite tables
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# bcrypt Password Bootstrap
# ---------------------------------------------------------------------------

def _bcrypt_hash(plaintext: str) -> str:
    """Return bcrypt hash of plaintext (bytes → str). Falls back to plaintext if no bcrypt."""
    if HAS_BCRYPT:
        return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return plaintext


def _bcrypt_check(plaintext: str, hashed: str) -> bool:
    """Compare plaintext against stored bcrypt hash. Falls back to equality if no bcrypt."""
    if HAS_BCRYPT:
        try:
            return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False
    return plaintext == hashed


def _get_setting(key: str) -> str | None:
    """Fetch a single system_settings value by key. Returns None on miss/error."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return str(row["setting_value"]).strip()
    except Exception as e:
        print(f"[SETTINGS WARNING] Unable to fetch '{key}': {e}")
    return None


def _set_setting(key: str, value: str):
    """Upsert a single system_settings key/value pair."""
    conn = get_db_connection()
    cursor = conn.cursor()
    _upsert_setting(cursor, conn, key, value)
    conn.commit()
    conn.close()


def bootstrap_password_hashes():
    """
    On first startup, hash ADMIN_PASSWORD and GUARD_PIN with bcrypt and persist them.
    Also stores the plaintext guard password for admin display.
    This function is safe to call on every startup — it is a no-op if hashes already exist.
    """
    # Admin password hash
    if not _get_setting("admin_password_hash"):
        _set_setting("admin_password_hash", _bcrypt_hash(ADMIN_PASSWORD))

    # Guard password (plaintext for display) + hash for auth
    if not _get_setting("guard_password"):
        _set_setting("guard_password", GUARD_PIN)
    if not _get_setting("guard_password_hash"):
        plain = _get_setting("guard_password") or GUARD_PIN
        _set_setting("guard_password_hash", _bcrypt_hash(plain))

    # Default event settings
    event_defaults = {
        "event_name": os.environ.get("EVENT_NAME", "Event"),
        "event_venue": os.environ.get("EVENT_VENUE", "Main Venue"),
        "event_date": os.environ.get("EVENT_DATE", ""),
        "event_capacity": os.environ.get("EVENT_CAPACITY", "5000"),
        "event_description": os.environ.get("EVENT_DESCRIPTION", ""),
    }
    for k, v in event_defaults.items():
        if not _get_setting(k):
            _set_setting(k, v)


# ---------------------------------------------------------------------------
# Guard Password Helpers
# ---------------------------------------------------------------------------

def get_guard_password() -> str:
    """Return plaintext guard password (for admin display). Falls back to GUARD_PIN env var."""
    val = _get_setting("guard_password")
    return val if val else os.environ.get("GUARD_PIN", GUARD_PIN)


def set_guard_password(new_password: str):
    """Update guard plaintext password AND its bcrypt hash in system_settings."""
    _set_setting("guard_password", new_password)
    _set_setting("guard_password_hash", _bcrypt_hash(new_password))


def check_guard_password(pin: str) -> bool:
    """Verify guard pin against bcrypt hash (or plaintext fallback)."""
    stored_hash = _get_setting("guard_password_hash")
    if stored_hash:
        return _bcrypt_check(pin, stored_hash)
    # Fallback: plaintext equality
    return pin == get_guard_password()


def check_admin_password(password: str) -> bool:
    """Verify admin password against bcrypt hash (or plaintext fallback)."""
    stored_hash = _get_setting("admin_password_hash")
    if stored_hash:
        return _bcrypt_check(password, stored_hash)
    # Fallback: env plaintext
    return password == ADMIN_PASSWORD


# ---------------------------------------------------------------------------
# Event Settings Helpers
# ---------------------------------------------------------------------------

def get_event_config() -> dict:
    """
    Read event settings from system_settings, falling back to env vars and defaults.
    Returns a dict with: event_name, event_venue, event_date, event_capacity, event_description.
    """
    return {
        "event_name": _get_setting("event_name") or os.environ.get("EVENT_NAME", "Event"),
        "event_venue": _get_setting("event_venue") or os.environ.get("EVENT_VENUE", "Main Venue"),
        "event_date": _get_setting("event_date") or os.environ.get("EVENT_DATE", ""),
        "event_capacity": _get_setting("event_capacity") or os.environ.get("EVENT_CAPACITY", "5000"),
        "event_description": _get_setting("event_description") or os.environ.get("EVENT_DESCRIPTION", ""),
    }


# ---------------------------------------------------------------------------
# DB Readiness & Context Processors
# ---------------------------------------------------------------------------

_db_ready = False


@app.before_request
def ensure_db_ready():
    """Auto-initialize database on first request (supports serverless cold-starts)."""
    global _db_ready
    if not _db_ready:
        init_db()
        bootstrap_password_hashes()
        _db_ready = True

    # Enforce short-lived guard sessions
    if session.get("guard_logged_in") and not session.get("is_admin"):
        session.permanent = False
        session.modified = True
        # Check guard session age
        guard_login_time = session.get("guard_login_time")
        if guard_login_time:
            elapsed = (datetime.datetime.now() - datetime.datetime.fromisoformat(guard_login_time)).total_seconds()
            if elapsed > GUARD_SESSION_MINUTES * 60:
                session.pop("guard_logged_in", None)
                session.pop("guard_login_time", None)
                flash("Guard session expired. Please log in again.", "warning")


@app.context_processor
def inject_server_mode():
    return {"is_flask_backend": True}


@app.context_processor
def inject_event_settings():
    """Make event_config available to all templates automatically."""
    try:
        event_config = get_event_config()
    except Exception:
        event_config = {
            "event_name": "Event",
            "event_venue": "Main Venue",
            "event_date": "",
            "event_capacity": "5000",
            "event_description": "",
        }
    return {"event_config": event_config}


# ---------------------------------------------------------------------------
# SECURITY & HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def generate_hmac_signature(reg_code: str, name: str, mobile: str, gate: str) -> str:
    """Generate SHA256 HMAC signature binding registration data with the secret key."""
    canonical_data = f"{reg_code.strip()}|{name.strip().upper()}|{mobile.strip()}|{gate.strip()}".encode("utf-8")
    return hmac.new(HMAC_SECRET_KEY, canonical_data, hashlib.sha256).hexdigest()


def verify_hmac_signature(reg_code: str, name: str, mobile: str, gate: str, signature: str) -> bool:
    """Cryptographically verify signature against recomputed HMAC using constant-time compare."""
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
    Calculates current total headcount across all exit gates.
    Assigns incoming group to the gate with the lowest active visitor load.
    Prevents stampedes and bottlenecks at event exits.
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

    min_gate_id = min(gate_counts, key=gate_counts.get)
    for g in GATES_CONFIG:
        if g["gate_id"] == min_gate_id:
            return g

    return GATES_CONFIG[0]


def check_duplicate_mobile_today(mobile: str) -> bool:
    """Return True if this mobile number was already registered today."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM registrations WHERE mobile = ? AND created_at LIKE ? LIMIT 1",
            (mobile, f"{today}%")
        )
        row = cursor.fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def login_required(f):
    """Decorator: requires active admin session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin login required to access this dashboard.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


def guard_required(f):
    """Decorator: requires active guard or admin session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if GUARD_PIN_REQUIRED and not (session.get("guard_logged_in") or session.get("is_admin")):
            flash("Guard password authentication required to operate terminal.", "warning")
            return redirect(url_for("guard_login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# APPLICATION ROUTES — VISITOR REGISTRATION
# ---------------------------------------------------------------------------

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

    # Duplicate mobile check (warn only — do not block)
    if check_duplicate_mobile_today(mobile):
        flash(
            f"Note: Mobile number {mobile} was already used for a registration today. "
            "Proceeding with a new registration.",
            "warning"
        )

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

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        if conn.db_kind == "postgresql":
            cursor.execute("""
                INSERT INTO registrations (
                    reg_code, language, primary_name, mobile, age, address,
                    group_count, assigned_group, assigned_gate, gate_id,
                    hmac_signature, created_at, checked_in
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                RETURNING id
            """, (
                reg_code, language, primary_name, mobile, age, address,
                total_group_count, assigned["group"], assigned["name"], assigned["gate_id"],
                hmac_sig, created_at
            ))
            reg_id = cursor.lastrowid
        else:
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

        # Fallback in case cursor.lastrowid is None
        if not reg_id:
            cursor.execute("SELECT id FROM registrations WHERE reg_code = ?", (reg_code,))
            r_row = cursor.fetchone()
            if r_row:
                reg_id = r_row["id"]

        for member in members_data:
            cursor.execute("""
                INSERT INTO group_members (reg_id, member_name, member_age, member_mobile)
                VALUES (?, ?, ?, ?)
            """, (reg_id, member["name"], member["age"], member["mobile"]))

        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[REGISTRATION ERROR] Database insertion failed: {e}")
        flash("A database error occurred while generating your pass. Please try again.", "error")
        return redirect(url_for("index", lang=language))
    finally:
        try:
            conn.close()
        except Exception:
            pass

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
    """Legacy pass.html URL redirect."""
    code = request.args.get("code")
    if code:
        return redirect(url_for("view_pass", reg_code=code))
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# SECURITY GUARD TERMINAL & VERIFICATION
# ---------------------------------------------------------------------------

@app.route("/guard/login", methods=["GET", "POST"])
def guard_login():
    """Guard password authentication terminal."""
    if session.get("guard_logged_in"):
        return redirect(url_for("verify_terminal"))

    next_url = request.args.get("next") or url_for("verify_terminal")
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        if check_guard_password(pin):
            session["guard_logged_in"] = True
            session["guard_login_time"] = datetime.datetime.now().isoformat()
            session.permanent = False  # Short-lived guard session
            flash("Guard terminal unlocked. Scanner active.", "success")
            return redirect(next_url)
        else:
            flash("Invalid Guard Access Password. Entry denied.", "error")

    return render_template("guard_login.html")


if HAS_LIMITER:
    limiter.limit("5 per minute")(guard_login)


@app.route("/guard/logout", methods=["GET", "POST"])
def guard_logout():
    """Lock Guard Terminal and auto-logout guard session."""
    session.pop("guard_logged_in", None)
    session.pop("guard_login_time", None)
    if request.method == "POST" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "message": "Guard session locked."})
    flash("Guard terminal locked successfully. Password required to re-enter.", "info")
    return redirect(url_for("guard_login"))


@app.route("/api/guard/lock", methods=["POST"])
def api_guard_lock():
    """
    Immediately terminate the active guard session via API.
    Returns JSON confirmation. Useful for auto-lock timers in the frontend.
    """
    session.pop("guard_logged_in", None)
    session.pop("guard_login_time", None)
    return jsonify({"success": True, "message": "Guard session locked via API."})


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
    Allows the in-browser camera scanner to verify passes instantly without page reloads.
    Requires active Guard or Admin session.
    """
    if GUARD_PIN_REQUIRED and not (session.get("guard_logged_in") or session.get("is_admin")):
        return jsonify({
            "success": False,
            "is_valid": False,
            "tamper_reason": "UNAUTHORIZED: Guard login required to scan/verify passes."
        }), 401

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
    """Security guard check-in confirmation toggle into visitor registry."""
    if GUARD_PIN_REQUIRED and not (session.get("guard_logged_in") or session.get("is_admin")):
        return jsonify({"success": False, "message": "UNAUTHORIZED: Guard login required to admit visitors."}), 401

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


# ---------------------------------------------------------------------------
# ADMIN CONTROLS
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page with bcrypt-protected password authentication."""
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        password = request.form.get("password", "")
        if check_admin_password(password):
            session["is_admin"] = True
            session.permanent = True
            flash("Welcome to Event Command & Control Admin Panel.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid administrator password. Access denied.", "error")

    return render_template("login.html")


if HAS_LIMITER:
    limiter.limit("5 per minute")(admin_login)


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
    if conn.db_kind == "postgresql":
        cursor.execute("""
            SELECT r.*,
                   COUNT(m.id) as accompanying_count,
                   STRING_AGG(m.member_name || ' (' || m.member_age || 'y)', ', ') as members_summary
            FROM registrations r
            LEFT JOIN group_members m ON r.id = m.reg_id
            GROUP BY r.id
            ORDER BY r.id DESC
        """)
    elif conn.db_kind == "mysql":
        cursor.execute("""
            SELECT r.*,
                   COUNT(m.id) as accompanying_count,
                   GROUP_CONCAT(CONCAT(m.member_name, ' (', m.member_age, 'y)') SEPARATOR ', ') as members_summary
            FROM registrations r
            LEFT JOIN group_members m ON r.id = m.reg_id
            GROUP BY r.id
            ORDER BY r.id DESC
        """)
    else:
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

    # Entrance QR Code for Signage (Points to Registration Page)
    host_url = request.host_url.rstrip("/")
    entrance_url = f"{host_url}/"
    entrance_qr_base64 = generate_qr_base64(entrance_url)

    guard_password = get_guard_password()

    return render_template(
        "admin.html",
        registrations=registrations,
        total_people=total_people,
        total_passes=total_passes,
        admitted_people=admitted_people,
        gate_analytics=gate_analytics,
        entrance_url=entrance_url,
        entrance_qr=entrance_qr_base64,
        guard_password=guard_password
    )


@app.route("/admin/update-guard-password", methods=["POST"])
@login_required
def update_guard_password():
    """Admin dynamically updates Guard Portal access password anytime."""
    new_password = request.form.get("guard_password", "").strip()
    if not new_password:
        flash("Guard password cannot be empty.", "error")
        return redirect(url_for("admin_dashboard"))

    if len(new_password) < 4:
        flash("Guard password must be at least 4 characters for security.", "error")
        return redirect(url_for("admin_dashboard"))

    set_guard_password(new_password)
    flash(
        f"Guard Portal password successfully updated to '{new_password}'. "
        "Guards must now enter this password to unlock their terminal.",
        "success"
    )
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/event-settings", methods=["POST"])
@login_required
def update_event_settings():
    """Admin updates event-level configuration (name, venue, date, capacity, description)."""
    fields = ["event_name", "event_venue", "event_date", "event_capacity", "event_description"]
    for field in fields:
        value = request.form.get(field, "").strip()
        if value:
            _set_setting(field, value)

    flash("Event settings updated successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/entrance-poster")
@login_required
def entrance_poster():
    """Printable High-Resolution Static Entrance QR Code Poster for Event Entry."""
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

    if conn.db_kind == "postgresql":
        cursor.execute("""
            SELECT r.id, r.reg_code, r.created_at, r.language,
                   r.primary_name, r.mobile, r.age, r.address,
                   r.group_count, r.assigned_group, r.assigned_gate,
                   r.checked_in, r.checked_in_at, r.hmac_signature,
                   STRING_AGG(
                       m.member_name || ' [Age: ' || m.member_age ||
                       COALESCE(', Ph: ' || NULLIF(m.member_mobile, ''), '') || ']',
                       ' | '
                   ) as members_list
            FROM registrations r
            LEFT JOIN group_members m ON r.id = m.reg_id
            GROUP BY r.id
            ORDER BY r.id ASC
        """)
    elif conn.db_kind == "mysql":
        cursor.execute("""
            SELECT r.id, r.reg_code, r.created_at, r.language,
                   r.primary_name, r.mobile, r.age, r.address,
                   r.group_count, r.assigned_group, r.assigned_gate,
                   r.checked_in, r.checked_in_at, r.hmac_signature,
                   GROUP_CONCAT(
                       CONCAT(m.member_name, ' [Age: ', m.member_age, IF(m.member_mobile != '', CONCAT(', Ph: ', m.member_mobile), ''), ']')
                       SEPARATOR ' | '
                   ) as members_list
            FROM registrations r
            LEFT JOIN group_members m ON r.id = m.reg_id
            GROUP BY r.id
            ORDER BY r.id ASC
        """)
    else:
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
    filename = f"event_crowd_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

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
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM group_members WHERE reg_id = ?", (reg_id,))
        cursor.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
        conn.commit()
    finally:
        conn.close()
    flash(f"Registration #{reg_id} deleted successfully.", "info")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# API — Paginated Registrations (Admin AJAX)
# ---------------------------------------------------------------------------

@app.route("/api/registrations", methods=["GET"])
@login_required
def api_registrations():
    """
    Paginated and searchable JSON endpoint for admin AJAX registration table.

    Query params:
      - page      (int, default 1)
      - per_page  (int, default 25, max 100)
      - q         (search string — matches name, mobile, reg_code, address)
      - status    (all | admitted | pending)
      - gate_id   (filter by gate)
      - date_from (YYYY-MM-DD)
      - date_to   (YYYY-MM-DD)
    """
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 25))))
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all").lower()
    gate_id = request.args.get("gate_id", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Build dynamic WHERE clause
    conditions = []
    params = []

    if q:
        like_q = f"%{q}%"
        conditions.append(
            "(r.primary_name LIKE ? OR r.mobile LIKE ? OR r.reg_code LIKE ? OR r.address LIKE ?)"
        )
        params.extend([like_q, like_q, like_q, like_q])

    if status == "admitted":
        conditions.append("r.checked_in = 1")
    elif status == "pending":
        conditions.append("r.checked_in = 0")

    if gate_id:
        conditions.append("r.gate_id = ?")
        params.append(gate_id)

    if date_from:
        conditions.append("r.created_at >= ?")
        params.append(date_from)

    if date_to:
        conditions.append("r.created_at <= ?")
        params.append(date_to + " 23:59:59")

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Count total matching
    count_sql = f"SELECT COUNT(r.id) as total FROM registrations r {where_sql}"
    cursor.execute(count_sql, params)
    count_row = cursor.fetchone()
    total = count_row["total"] if count_row else 0
    total_pages = max(1, math.ceil(total / per_page))

    offset = (page - 1) * per_page

    # Fetch paginated rows with member aggregation
    if conn.db_kind == "postgresql":
        agg_expr = "STRING_AGG(m.member_name || ' (' || m.member_age || 'y)', ', ') as members_summary"
    elif conn.db_kind == "mysql":
        agg_expr = "GROUP_CONCAT(CONCAT(m.member_name, ' (', m.member_age, 'y)') SEPARATOR ', ') as members_summary"
    else:
        agg_expr = "GROUP_CONCAT(m.member_name || ' (' || m.member_age || 'y)', ', ') as members_summary"

    data_sql = f"""
        SELECT r.id, r.reg_code, r.created_at, r.language,
               r.primary_name, r.mobile, r.age, r.address,
               r.group_count, r.assigned_group, r.assigned_gate, r.gate_id,
               r.checked_in, r.checked_in_at,
               COUNT(m.id) as accompanying_count,
               {agg_expr}
        FROM registrations r
        LEFT JOIN group_members m ON r.id = m.reg_id
        {where_sql}
        GROUP BY r.id
        ORDER BY r.id DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(data_sql, params + [per_page, offset])
    rows = cursor.fetchall()
    conn.close()

    registrations = []
    for r in rows:
        registrations.append({
            "id": r["id"],
            "reg_code": r["reg_code"],
            "created_at": r["created_at"],
            "language": r["language"],
            "primary_name": r["primary_name"],
            "mobile": r["mobile"],
            "age": r["age"],
            "address": r["address"],
            "group_count": r["group_count"],
            "assigned_group": r["assigned_group"],
            "assigned_gate": r["assigned_gate"],
            "gate_id": r["gate_id"],
            "checked_in": r["checked_in"],
            "checked_in_at": r["checked_in_at"] or "",
            "accompanying_count": r["accompanying_count"] or 0,
            "members_summary": r["members_summary"] or ""
        })

    return jsonify({
        "registrations": registrations,
        "total": total,
        "pages": total_pages,
        "current_page": page,
        "per_page": per_page
    })


# ---------------------------------------------------------------------------
# API — Live Stats (Admin Dashboard Refresh)
# ---------------------------------------------------------------------------

@app.route("/api/stats", methods=["GET"])
@login_required
def api_stats():
    """
    JSON endpoint returning live crowd stats for admin dashboard auto-refresh.

    Returns:
      total_people, total_passes, admitted_people, pending_people,
      gate_breakdown (list), admission_rate (%)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT SUM(group_count) as total_people, COUNT(id) as total_passes FROM registrations")
        stats_row = cursor.fetchone()
        total_people = stats_row["total_people"] or 0
        total_passes = stats_row["total_passes"] or 0

        cursor.execute("SELECT SUM(group_count) as admitted_people FROM registrations WHERE checked_in = 1")
        admitted_row = cursor.fetchone()
        admitted_people = admitted_row["admitted_people"] or 0
        pending_people = total_people - admitted_people

        cursor.execute("""
            SELECT gate_id, SUM(group_count) as gate_headcount
            FROM registrations
            GROUP BY gate_id
        """)
        gate_rows = cursor.fetchall()
        conn.close()

        gate_counts = {row["gate_id"]: (row["gate_headcount"] or 0) for row in gate_rows}
        gate_breakdown = []
        for g in GATES_CONFIG:
            count = gate_counts.get(g["gate_id"], 0)
            gate_breakdown.append({
                "gate_id": g["gate_id"],
                "name": g["name"],
                "zone": g["zone"],
                "color": g["color"],
                "count": count,
                "percentage": round((count / total_people * 100), 1) if total_people > 0 else 0
            })

        admission_rate = round((admitted_people / total_people * 100), 1) if total_people > 0 else 0

        return jsonify({
            "success": True,
            "total_people": total_people,
            "total_passes": total_passes,
            "admitted_people": admitted_people,
            "pending_people": pending_people,
            "admission_rate": admission_rate,
            "gate_breakdown": gate_breakdown,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# SECURITY HEADERS & ANTI-CACHE
# ---------------------------------------------------------------------------

@app.after_request
def add_terminal_security_headers(response):
    """
    Prevent browser from caching sensitive guard terminal pages.
    Ensures back-navigation forces fresh session validation.
    """
    if request.path.startswith("/guard") or request.path.startswith("/verify"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ---------------------------------------------------------------------------
# ERROR HANDLERS
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def handle_404(e):
    """Return JSON for API routes, redirect for UI routes."""
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Not Found", "message": str(e)}), 404
    flash("The requested resource or pass was not found.", "warning")
    return redirect(url_for("index"))


@app.errorhandler(429)
def handle_429(e):
    """Rate limit exceeded handler."""
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Too Many Requests", "message": "Rate limit exceeded. Please wait and try again."}), 429
    flash("Too many login attempts. Please wait a moment and try again.", "error")
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(500)
def handle_500(e):
    """Internal server error handler."""
    return jsonify({
        "success": False,
        "error": "Internal Server Error",
        "message": "A server error occurred. Please contact event operations."
    }), 500


# ---------------------------------------------------------------------------
# MAIN INITIALIZATION
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    bootstrap_password_hashes()
    port = int(os.environ.get("PORT", 5000))
    print("=" * 63)
    print("  EVENT ENTRY & SMART CROWD MANAGEMENT SYSTEM RUNNING")
    print(f"  Local URL:     http://127.0.0.1:{port}")
    print(f"  Admin Panel:   http://127.0.0.1:{port}/admin")
    print(f"  Entry Poster:  http://127.0.0.1:{port}/admin/entrance-poster")
    print(f"  Guard Terminal: http://127.0.0.1:{port}/verify")
    print("=" * 63)
    app.run(host="0.0.0.0", port=port, debug=True)
