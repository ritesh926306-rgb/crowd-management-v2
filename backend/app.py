"""
VenueGuard — Smart Crowd Control & Event Management System
Backend Application with Flask, PostgreSQL / MySQL / SQLite Support,
HMAC-SHA256 Cryptographic Pass Verification, bcrypt Password Hashing,
Role-Based Portals, Rate Limiting, Audit Trails, and Hardware Telemetry.
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
import re
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

# Load .env securely
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
HARDWARE_API_KEY = os.environ.get("HARDWARE_API_KEY", "vg-device-key-2026")

# ---------------------------------------------------------------------------
# Database Configuration — SQLite (default), PostgreSQL, or MySQL
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_TYPE = os.environ.get("DB_TYPE", "sqlite").lower()
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "venue_crowd")

if DATABASE_URL and DATABASE_URL.startswith("postgres"):
    DB_TYPE = "postgresql"

if os.environ.get("VERCEL"):
    SQLITE_PATH = "/tmp/venue_crowd.db"
else:
    SQLITE_PATH = os.path.join(BASE_DIR, "venue_crowd.db")

# ---------------------------------------------------------------------------
# Event Gates Configuration: Main Entry + 4 Normal Exits + Restricted Gate E
# ---------------------------------------------------------------------------
GATES_CONFIG = [
    {
        "group": "Group A",
        "gate_id": "exit_1",
        "name": "Exit A (West)",
        "zone": "Event Zone Alpha (West Gate)",
        "color": "#00ADB5",
        "description": "Proceed West towards West Boulevard & Transit Hub 1"
    },
    {
        "group": "Group B",
        "gate_id": "exit_2",
        "name": "Exit B (North)",
        "zone": "Event Zone Beta (North Gate)",
        "color": "#1E3E62",
        "description": "Proceed North towards Main Highway & North Parking"
    },
    {
        "group": "Group C",
        "gate_id": "exit_3",
        "name": "Exit C (East)",
        "zone": "Event Zone Gamma (East Gate)",
        "color": "#D97706",
        "description": "Proceed East towards East Plaza & Metro Shuttle"
    },
    {
        "group": "Group D",
        "gate_id": "exit_4",
        "name": "Exit D (South)",
        "zone": "Event Zone Delta (South Gate)",
        "color": "#7C3AED",
        "description": "Proceed South towards South Promenade & Taxi Stand"
    }
]

STAFF_GATE = {
    "gate_id": "gate_e",
    "name": "Gate E (Restricted Staff Only)",
    "zone": "Security & Incident Command Corridor",
    "description": "Authorized Security, Medical Personnel, and Venue Operations Staff Only. Strictly restricted from public entry/exit."
}

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
        self.db_kind = db_kind

    def execute(self, query, params=None):
        if self.db_kind in ("mysql", "postgresql"):
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

    def cursor(self):
        if self.db_kind == "postgresql":
            return UnifiedCursor(self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor), self.db_kind)
        elif self.db_kind == "mysql":
            return UnifiedCursor(self.conn.cursor(pymysql.cursors.DictCursor), self.db_kind)
        else:
            return UnifiedCursor(self.conn.cursor(), self.db_kind)

    def commit(self):
        return self.conn.commit()

    def rollback(self):
        return self.conn.rollback()

    def close(self):
        return self.conn.close()


def get_db_connection() -> UnifiedConnection:
    """Connect to configured database with proper pooling and row factory."""
    if DB_TYPE == "postgresql":
        if not HAS_PSYCOPG2:
            raise RuntimeError("psycopg2 is required for PostgreSQL. Run: pip install psycopg2-binary")
        raw_conn = psycopg2.connect(DATABASE_URL)
        return UnifiedConnection(raw_conn, db_kind="postgresql")

    elif DB_TYPE == "mysql":
        if not HAS_PYMYSQL:
            raise RuntimeError("PyMySQL is required for MySQL. Run: pip install pymysql")
        raw_conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            autocommit=False
        )
        return UnifiedConnection(raw_conn, db_kind="mysql")

    else:
        # SQLite with WAL mode & 30s timeout
        raw_conn = sqlite3.connect(SQLITE_PATH, timeout=30.0)
        raw_conn.row_factory = sqlite3.Row
        raw_conn.execute("PRAGMA journal_mode=WAL;")
        raw_conn.execute("PRAGMA synchronous=NORMAL;")
        return UnifiedConnection(raw_conn, db_kind="sqlite")


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
            checked_in_at TIMESTAMP NULL,
            checked_out SMALLINT DEFAULT 0,
            checked_out_at TIMESTAMP NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            id BIGSERIAL PRIMARY KEY,
            reg_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
            member_name VARCHAR(255) NOT NULL,
            member_age INTEGER NOT NULL,
            member_mobile VARCHAR(20) DEFAULT ''
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            setting_key VARCHAR(100) PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS guard_accounts (
            id BIGSERIAL PRIMARY KEY,
            username VARCHAR(64) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            assigned_gate VARCHAR(50) NOT NULL DEFAULT 'all',
            is_active SMALLINT NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS entry_exit_logs (
            id BIGSERIAL PRIMARY KEY,
            reg_code VARCHAR(64) NOT NULL,
            action VARCHAR(10) NOT NULL,
            headcount INTEGER NOT NULL DEFAULT 1,
            gate_id VARCHAR(50) NOT NULL,
            guard_name VARCHAR(100) NOT NULL DEFAULT 'Duty Guard',
            timestamp TIMESTAMP NOT NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id BIGSERIAL PRIMARY KEY,
            actor VARCHAR(100) NOT NULL,
            action VARCHAR(100) NOT NULL,
            details TEXT NULL,
            ip_address VARCHAR(45) NULL,
            timestamp TIMESTAMP NOT NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergency_events (
            id BIGSERIAL PRIMARY KEY,
            status VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
            reason TEXT NOT NULL,
            activated_by VARCHAR(100) NOT NULL,
            activated_at TIMESTAMP NOT NULL,
            resolved_at TIMESTAMP NULL
        );
        """)

    elif conn.db_kind == "mysql":
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
            checked_in_at DATETIME NULL,
            checked_out TINYINT(1) DEFAULT 0,
            checked_out_at DATETIME NULL
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS guard_accounts (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(64) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            assigned_gate VARCHAR(50) NOT NULL DEFAULT 'all',
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS entry_exit_logs (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            reg_code VARCHAR(64) NOT NULL,
            action VARCHAR(10) NOT NULL,
            headcount INT UNSIGNED NOT NULL DEFAULT 1,
            gate_id VARCHAR(50) NOT NULL,
            guard_name VARCHAR(100) NOT NULL DEFAULT 'Duty Guard',
            timestamp DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            actor VARCHAR(100) NOT NULL,
            action VARCHAR(100) NOT NULL,
            details TEXT NULL,
            ip_address VARCHAR(45) NULL,
            timestamp DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergency_events (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            status VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
            reason TEXT NOT NULL,
            activated_by VARCHAR(100) NOT NULL,
            activated_at DATETIME NOT NULL,
            resolved_at DATETIME NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

    else:
        # SQLite
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
            checked_in_at TEXT,
            checked_out INTEGER DEFAULT 0,
            checked_out_at TEXT
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS guard_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            assigned_gate TEXT NOT NULL DEFAULT 'all',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS entry_exit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reg_code TEXT NOT NULL,
            action TEXT NOT NULL,
            headcount INTEGER NOT NULL DEFAULT 1,
            gate_id TEXT NOT NULL,
            guard_name TEXT NOT NULL DEFAULT 'Duty Guard',
            timestamp TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergency_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL DEFAULT 'NORMAL',
            reason TEXT NOT NULL,
            activated_by TEXT NOT NULL,
            activated_at TEXT NOT NULL,
            resolved_at TEXT
        )
        """)

    # Safe column migrations for existing databases
    try:
        cursor.execute("ALTER TABLE registrations ADD COLUMN checked_out INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE registrations ADD COLUMN checked_out_at TEXT")
    except Exception:
        pass

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# bcrypt & Password Bootstrap
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
    Also initializes default event and safety settings.
    """
    # Admin password hash
    if not _get_setting("admin_password_hash"):
        _set_setting("admin_password_hash", _bcrypt_hash(ADMIN_PASSWORD))

    # Guard password hash
    if not _get_setting("guard_password"):
        _set_setting("guard_password", GUARD_PIN)
    if not _get_setting("guard_password_hash"):
        plain = _get_setting("guard_password") or GUARD_PIN
        _set_setting("guard_password_hash", _bcrypt_hash(plain))

    # Event defaults — initial prototype capacity 1000
    event_defaults = {
        "event_name": os.environ.get("EVENT_NAME", "National Cultural & Devotional Gathering"),
        "event_venue": os.environ.get("EVENT_VENUE", "Grand Pavilion & Convention Grounds"),
        "event_date": os.environ.get("EVENT_DATE", "2026-12-15"),
        "event_capacity": os.environ.get("EVENT_CAPACITY", "1000"),
        "event_description": os.environ.get("EVENT_DESCRIPTION", "Official venue entry and smart crowd management system with digital QR verification and multi-gate safety allocation."),
        "emergency_mode": "0",
        "emergency_reason": ""
    }
    for k, v in event_defaults.items():
        if not _get_setting(k):
            _set_setting(k, v)


# ---------------------------------------------------------------------------
# Audit Logging Helper
# ---------------------------------------------------------------------------

def log_audit(actor: str, action: str, details: str = ""):
    """Record an audit trail event for security compliance."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ip = "127.0.0.1"
        try:
            if request:
                ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        except Exception:
            pass
        cursor.execute(
            "INSERT INTO audit_logs (actor, action, details, ip_address, timestamp) VALUES (?, ?, ?, ?, ?)",
            (actor, action, details, ip, now_str)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[AUDIT LOG WARNING] {e}")


# ---------------------------------------------------------------------------
# Guard & Admin Authentication Helpers
# ---------------------------------------------------------------------------

def get_guard_password() -> str:
    """Return guard password string (used in unit test compatibility and legacy display)."""
    val = _get_setting("guard_password")
    return val if val else os.environ.get("GUARD_PIN", GUARD_PIN)


def set_guard_password(new_password: str):
    """Update guard plaintext password AND its bcrypt hash in system_settings."""
    _set_setting("guard_password", new_password)
    _set_setting("guard_password_hash", _bcrypt_hash(new_password))
    log_audit("admin", "GUARD_PASSWORD_UPDATED", "Guard portal master password was updated.")


def check_guard_password(pin: str) -> bool:
    """Verify guard pin against bcrypt hash, guard accounts, or fallback."""
    stored_hash = _get_setting("guard_password_hash")
    if stored_hash and _bcrypt_check(pin, stored_hash):
        return True
    # Check individual guard accounts
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM guard_accounts WHERE (username = ? OR id = ?) AND is_active = 1", (pin, pin))
        row = cursor.fetchone()
        conn.close()
        if row and _bcrypt_check(pin, row["password_hash"]):
            return True
    except Exception:
        pass
    # Fallback equality
    return pin == get_guard_password()


def check_admin_password(password: str) -> bool:
    """Verify admin password against bcrypt hash (or plaintext fallback)."""
    stored_hash = _get_setting("admin_password_hash")
    if stored_hash:
        return _bcrypt_check(password, stored_hash)
    return password == ADMIN_PASSWORD


# ---------------------------------------------------------------------------
# Event Settings & Crowd Occupancy Helpers
# ---------------------------------------------------------------------------

def get_event_config() -> dict:
    """Read event settings from system_settings, falling back to defaults."""
    return {
        "event_name": _get_setting("event_name") or "National Cultural & Devotional Gathering",
        "event_venue": _get_setting("event_venue") or "Grand Pavilion & Convention Grounds",
        "event_date": _get_setting("event_date") or "2026-12-15",
        "event_capacity": _get_setting("event_capacity") or "1000",
        "event_description": _get_setting("event_description") or "Smart crowd management with digital QR verification.",
        "emergency_mode": _get_setting("emergency_mode") or "0",
        "emergency_reason": _get_setting("emergency_reason") or ""
    }


def get_current_occupancy() -> int:
    """Return headcount of visitors currently inside (checked in and not checked out)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(group_count) as inside FROM registrations WHERE checked_in = 1 AND (checked_out = 0 OR checked_out IS NULL)")
        row = cursor.fetchone()
        conn.close()
        return (row["inside"] or 0) if row else 0
    except Exception:
        return 0


def get_safe_crowd_status() -> str:
    """
    Returns public non-sensitive crowd status string without exposing exact raw headcounts:
    'Normal', 'Busy', 'High Crowd', or 'Temporarily Full'.
    """
    try:
        cfg = get_event_config()
        capacity = int(cfg.get("event_capacity") or 1000)
        inside = get_current_occupancy()
        if capacity <= 0:
            return "Normal"
        ratio = inside / capacity
        if ratio >= 0.95:
            return "Temporarily Full"
        elif ratio >= 0.80:
            return "High Crowd"
        elif ratio >= 0.50:
            return "Busy"
        return "Normal"
    except Exception:
        return "Normal"


def is_emergency_active() -> bool:
    """Check if emergency mode is active."""
    return _get_setting("emergency_mode") == "1"


# ---------------------------------------------------------------------------
# DB Readiness & Context Processors
# ---------------------------------------------------------------------------

_db_ready = False

@app.before_request
def ensure_db_ready():
    """Auto-initialize database on first request."""
    global _db_ready
    if not _db_ready:
        init_db()
        bootstrap_password_hashes()
        _db_ready = True


@app.context_processor
def inject_global_data():
    """Inject event config, safe crowd status, and environment flags into all templates."""
    event_cfg = get_event_config()
    safe_status = get_safe_crowd_status()
    is_emergency = is_emergency_active()
    return {
        "event_config": event_cfg,
        "safe_crowd_status": safe_status,
        "is_emergency_active": is_emergency,
        "is_flask_backend": True
    }


# ---------------------------------------------------------------------------
# Cryptographic HMAC & QR Generation Utilities
# ---------------------------------------------------------------------------

def generate_hmac_signature(reg_code: str, name: str, mobile: str, gate: str) -> str:
    """Generate SHA256 HMAC signature over canonical representation of pass data."""
    canonical_data = f"{reg_code}|{name.strip()}|{mobile.strip()}|{gate.strip()}".encode("utf-8")
    signature = hmac.new(HMAC_SECRET_KEY, canonical_data, hashlib.sha256).hexdigest()
    return signature


def verify_hmac_signature(reg_code: str, name: str, mobile: str, gate: str, signature: str) -> bool:
    """Cryptographically verify signature against recomputed HMAC using constant-time compare."""
    recomputed = generate_hmac_signature(reg_code, name, mobile, gate)
    return hmac.compare_digest(recomputed, signature)


def generate_qr_base64(data_string: str) -> str:
    """Generate QR code and return as Base64 data URI string."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(data_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0B192C", back_color="#FFFFFF")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"


def check_duplicate_mobile_today(mobile: str) -> bool:
    """Return True if mobile already registered today."""
    today = datetime.date.today().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM registrations WHERE mobile = ? AND created_at >= ?", (mobile, today))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def determine_smart_split_gate() -> dict:
    """
    Select the least-loaded exit gate among the 4 normal exit corridors (Exit A, B, C, D).
    Gate E is strictly restricted to staff and never assigned to visitors.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT gate_id, SUM(group_count) as total_headcount
        FROM registrations
        GROUP BY gate_id
    """)
    gate_counts = {row["gate_id"]: (row["total_headcount"] or 0) for row in cursor.fetchall()}
    conn.close()

    sorted_gates = sorted(GATES_CONFIG, key=lambda g: gate_counts.get(g["gate_id"], 0))
    return sorted_gates[0]


# ---------------------------------------------------------------------------
# Auth Decorators
# ---------------------------------------------------------------------------

def login_required(f):
    """Require Admin authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            next_url = request.full_path if request.query_string else request.path
            flash("Administrator login required to access this resource.", "error")
            return redirect(url_for("admin_login", next=next_url))
        return f(*args, **kwargs)
    return decorated_function


def guard_required(f):
    """Require Security Guard or Admin session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if GUARD_PIN_REQUIRED:
            if not (session.get("guard_logged_in") or session.get("is_admin")):
                next_url = request.full_path if request.query_string else request.path
                flash("Guard authentication required to access verification scanner.", "warning")
                return redirect(url_for("guard_login", next=next_url))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# PUBLIC VISITOR ROUTES
# ---------------------------------------------------------------------------

@app.route("/")
@app.route("/index.html")
def index():
    """Public Visitor Homepage with Clean Hero, Guidelines, and 4-Step Registration Wizard."""
    lang = request.args.get("lang", "en")
    safe_status = get_safe_crowd_status()
    return render_template("index.html", lang=lang, gates=GATES_CONFIG, safe_crowd_status=safe_status)


@app.route("/register", methods=["POST"])
def register():
    """Handle new visitor registration with dynamic members and capacity split."""
    language = request.form.get("language", "en")
    primary_name = request.form.get("primary_name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    age_str = request.form.get("age", "").strip()
    address = request.form.get("address", "").strip()

    # Safety check: Is emergency active?
    if is_emergency_active():
        flash("Online registration is temporarily restricted due to an active venue safety advisory. Please follow staff directions.", "error")
        return redirect(url_for("index", lang=language))

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
                    hmac_signature, created_at, checked_in, checked_out
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
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
                    hmac_signature, created_at, checked_in, checked_out
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """, (
                reg_code, language, primary_name, mobile, age, address,
                total_group_count, assigned["group"], assigned["name"], assigned["gate_id"],
                hmac_sig, created_at
            ))
            reg_id = cursor.lastrowid

        # Fallback if cursor.lastrowid is None
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
        log_audit("visitor", "REGISTRATION_CREATED", f"Pass {reg_code} generated for {primary_name} ({total_group_count} people)")
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
    """Display official Digital Entry Pass / ID Card with masked privacy protections."""
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
    qr_base64 = generate_qr_base64(verification_url)

    gate_info = next((g for g in GATES_CONFIG if g["gate_id"] == reg["gate_id"]), GATES_CONFIG[0])

    # Privacy masking for public views (protects against casual over-the-shoulder viewing)
    is_staff = bool(session.get("guard_logged_in") or session.get("is_admin"))
    raw_mobile = str(reg["mobile"])
    masked_mobile = (raw_mobile[:2] + "••••••" + raw_mobile[-2:]) if (not is_staff and len(raw_mobile) >= 8) else raw_mobile

    raw_addr = str(reg["address"])
    if not is_staff and len(raw_addr) > 20:
        parts = raw_addr.split(",")
        masked_address = parts[-1].strip() if len(parts) > 1 else raw_addr[:15] + "..."
    else:
        masked_address = raw_addr

    return render_template(
        "pass.html",
        reg=reg,
        members=members,
        qr_code=qr_base64,
        verification_url=verification_url,
        gate_info=gate_info,
        masked_mobile=masked_mobile,
        masked_address=masked_address,
        is_staff=is_staff
    )


@app.route("/pass.html")
def pass_html_redirect():
    """Pass.html URL redirect."""
    code = request.args.get("code")
    if code:
        return redirect(url_for("view_pass", reg_code=code))
    return redirect(url_for("index"))


@app.route("/check-registration", methods=["GET", "POST"])
def check_registration():
    """Secure Pass Lookup: Visitors check pass using Registration ID + Mobile Number."""
    if request.method == "POST":
        reg_code = request.form.get("reg_code", "").strip().upper()
        mobile = request.form.get("mobile", "").strip()

        if not reg_code or not mobile:
            flash("Please enter both your Registration Code and Mobile Number.", "error")
            return render_template("check_registration.html")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT reg_code, mobile FROM registrations WHERE UPPER(reg_code) = ?", (reg_code,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            flash("No pass found matching this Registration Code. Please check the code or register again.", "error")
            return render_template("check_registration.html")

        # Verify mobile number (match full or last 10 digits to prevent private data exposure)
        stored_mobile = str(row["mobile"]).strip()
        clean_input_mobile = re.sub(r"\D", "", mobile)
        clean_stored_mobile = re.sub(r"\D", "", stored_mobile)

        if clean_input_mobile[-10:] != clean_stored_mobile[-10:]:
            flash("Mobile number does not match this Registration Code. Verification denied.", "error")
            return render_template("check_registration.html")

        log_audit("visitor", "PASS_LOOKUP_SUCCESS", f"Pass {reg_code} verified by visitor")
        return redirect(url_for("view_pass", reg_code=row["reg_code"]))

    return render_template("check_registration.html")


@app.route("/api/check-registration", methods=["POST"])
def api_check_registration():
    """API endpoint for visitor pass lookup via JSON."""
    data = request.get_json(silent=True) or request.form
    reg_code = (data.get("reg_code") or "").strip().upper()
    mobile = (data.get("mobile") or "").strip()

    if not reg_code or not mobile:
        return jsonify({"success": False, "message": "Both Registration Code and Mobile Number are required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registrations WHERE UPPER(reg_code) = ?", (reg_code,))
    reg = cursor.fetchone()

    if not reg:
        conn.close()
        return jsonify({"success": False, "message": "No registration record found for this code."}), 404

    clean_input = re.sub(r"\D", "", mobile)
    clean_stored = re.sub(r"\D", "", str(reg["mobile"]))
    if clean_input[-10:] != clean_stored[-10:]:
        conn.close()
        return jsonify({"success": False, "message": "Security Verification Failed: Mobile number mismatch."}), 403

    cursor.execute("SELECT member_name, member_age FROM group_members WHERE reg_id = ?", (reg["id"],))
    members = cursor.fetchall()
    conn.close()

    gate_info = next((g for g in GATES_CONFIG if g["gate_id"] == reg["gate_id"]), GATES_CONFIG[0])

    return jsonify({
        "success": True,
        "reg_code": reg["reg_code"],
        "primary_name": reg["primary_name"],
        "group_count": reg["group_count"],
        "assigned_gate": reg["assigned_gate"],
        "assigned_group": reg["assigned_group"],
        "gate_info": gate_info,
        "checked_in": reg["checked_in"],
        "checked_in_at": reg["checked_in_at"] or "",
        "checked_out": reg["checked_out"] if "checked_out" in reg else 0,
        "members": [{"name": m["member_name"], "age": m["member_age"]} for m in members]
    })


@app.route("/venue-info")
def venue_info():
    """Public Venue Information: Address, Entry/Exit Guidelines, Parking, and Map."""
    cfg = get_event_config()
    return render_template("venue_info.html", event_config=cfg, gates=GATES_CONFIG, staff_gate=STAFF_GATE)


@app.route("/help")
@app.route("/contact")
def help_contact():
    """Public Help, Contact, Safety Protocols, and Emergency Information."""
    cfg = get_event_config()
    return render_template("help_contact.html", event_config=cfg)


@app.route("/api/public-crowd-status", methods=["GET"])
def api_public_crowd_status():
    """Non-sensitive safe crowd status API for public visitors."""
    cfg = get_event_config()
    status = get_safe_crowd_status()
    is_emergency = is_emergency_active()
    return jsonify({
        "success": True,
        "status": status,
        "event_name": cfg["event_name"],
        "event_venue": cfg["event_venue"],
        "is_emergency": is_emergency,
        "emergency_message": "Please proceed calmly to the nearest designated exit corridor." if is_emergency else None
    })


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
            session.permanent = False
            log_audit("guard", "GUARD_LOGIN_SUCCESS", "Guard authenticated at terminal")
            flash("Guard terminal unlocked. Scanner active.", "success")
            return redirect(next_url)
        else:
            log_audit("guard", "GUARD_LOGIN_FAILED", "Invalid guard access attempt")
            flash("Invalid Guard Access Password. Entry denied.", "error")

    return render_template("guard_login.html")


if HAS_LIMITER:
    limiter.limit("10 per minute")(guard_login)


@app.route("/guard/logout", methods=["GET", "POST"])
def guard_logout():
    """Lock Guard Terminal and terminate guard session."""
    session.pop("guard_logged_in", None)
    session.pop("guard_login_time", None)
    log_audit("guard", "GUARD_LOGOUT", "Guard terminal locked")
    if request.method == "POST" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "message": "Guard session locked."})
    flash("Guard terminal locked successfully. Password required to re-enter.", "info")
    return redirect(url_for("guard_login"))


@app.route("/api/guard/lock", methods=["POST"])
def api_guard_lock():
    """Terminate guard session via API."""
    session.pop("guard_logged_in", None)
    session.pop("guard_login_time", None)
    return jsonify({"success": True, "message": "Guard session locked via API."})


@app.route("/verify", strict_slashes=False)
@app.route("/verify.html")
@app.route("/guard", strict_slashes=False)
@guard_required
def verify_terminal():
    """Standby Security Guard Scanner & Verification Terminal."""
    current_inside = get_current_occupancy()
    cfg = get_event_config()
    capacity = int(cfg.get("event_capacity") or 1000)
    is_emergency = is_emergency_active()

    return render_template(
        "verify.html",
        is_valid=None,
        tamper_reason=None,
        reg=None,
        members=[],
        gate_info=None,
        is_already_checked_in=False,
        current_inside=current_inside,
        capacity=capacity,
        is_emergency=is_emergency,
        gates=GATES_CONFIG,
        staff_gate=STAFF_GATE,
        guard_active=bool(session.get("guard_logged_in") or session.get("is_admin"))
    )


@app.route("/verify/<reg_code>")
@guard_required
def verify_pass(reg_code):
    """Performs cryptographic HMAC recalculation and displays full pass details."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM registrations WHERE reg_code = ?", (reg_code,))
    reg = cursor.fetchone()

    if not reg:
        conn.close()
        log_audit("guard", "PASS_VERIFY_NOT_FOUND", f"Unknown reg code: {reg_code}")
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
        log_audit("guard", "PASS_TAMPER_DETECTED", f"HMAC signature mismatch on {reg_code}")
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
    """Real-time JSON Verification API for Camera QR Scanner."""
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
    is_checked_out = bool(reg["checked_out"] if "checked_out" in reg else 0)

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
        "checked_out": reg["checked_out"] if "checked_out" in reg else 0,
        "checked_out_at": (reg["checked_out_at"] if "checked_out_at" in reg else "") or "",
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
            "is_already_checked_in": is_already_checked_in,
            "is_checked_out": is_checked_out
        })

    return jsonify({
        "success": True,
        "is_valid": True,
        "is_hmac_valid": True,
        "tamper_reason": None,
        "reg": reg_dict,
        "members": members,
        "gate_info": gate_info,
        "is_already_checked_in": is_already_checked_in,
        "is_checked_out": is_checked_out
    })


@app.route("/api/check-in/<reg_code>", methods=["POST"])
def api_check_in(reg_code):
    """Mark visitor entry / gate admission."""
    if GUARD_PIN_REQUIRED and not (session.get("guard_logged_in") or session.get("is_admin")):
        return jsonify({"success": False, "message": "UNAUTHORIZED: Guard login required to admit visitors."}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, group_count, gate_id, checked_in FROM registrations WHERE reg_code = ?", (reg_code,))
    reg = cursor.fetchone()

    if not reg:
        conn.close()
        return jsonify({"success": False, "message": "Record not found"}), 404

    new_status = 1 if reg["checked_in"] == 0 else 0
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    checked_in_at = now_str if new_status == 1 else None

    cursor.execute(
        "UPDATE registrations SET checked_in = ?, checked_in_at = ?, checked_out = 0 WHERE id = ?",
        (new_status, checked_in_at, reg["id"])
    )

    if new_status == 1:
        try:
            cursor.execute(
                "INSERT INTO entry_exit_logs (reg_code, action, headcount, gate_id, guard_name, timestamp) VALUES (?, 'ENTRY', ?, ?, 'Duty Guard', ?)",
                (reg_code, reg["group_count"], reg["gate_id"], now_str)
            )
        except Exception:
            pass

    conn.commit()
    conn.close()
    log_audit("guard", "VISITOR_ADMISSION", f"Pass {reg_code} status: {new_status}")

    return jsonify({
        "success": True,
        "checked_in": new_status,
        "checked_in_at": checked_in_at
    })


@app.route("/api/check-out/<reg_code>", methods=["POST"])
def api_check_out(reg_code):
    """Mark visitor exit at designated exit gate."""
    if GUARD_PIN_REQUIRED and not (session.get("guard_logged_in") or session.get("is_admin")):
        return jsonify({"success": False, "message": "UNAUTHORIZED: Guard login required to record exit."}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, group_count, gate_id, checked_in, checked_out FROM registrations WHERE reg_code = ?", (reg_code,))
    reg = cursor.fetchone()

    if not reg:
        conn.close()
        return jsonify({"success": False, "message": "Record not found"}), 404

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE registrations SET checked_out = 1, checked_out_at = ? WHERE id = ?",
        (now_str, reg["id"])
    )

    try:
        cursor.execute(
            "INSERT INTO entry_exit_logs (reg_code, action, headcount, gate_id, guard_name, timestamp) VALUES (?, 'EXIT', ?, ?, 'Duty Guard', ?)",
            (reg_code, reg["group_count"], reg["gate_id"], now_str)
        )
    except Exception:
        pass

    conn.commit()
    conn.close()
    log_audit("guard", "VISITOR_EXIT", f"Pass {reg_code} marked exited")

    return jsonify({
        "success": True,
        "checked_out": 1,
        "checked_out_at": now_str
    })


# ---------------------------------------------------------------------------
# ADMIN COMMAND CENTER
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
            log_audit("admin", "ADMIN_LOGIN_SUCCESS", "Administrator authenticated")
            flash("Welcome to Event Command & Control Admin Panel.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            log_audit("admin", "ADMIN_LOGIN_FAILED", "Failed admin login attempt")
            flash("Invalid administrator password. Access denied.", "error")

    return render_template("login.html")


if HAS_LIMITER:
    limiter.limit("10 per minute")(admin_login)


@app.route("/admin/logout")
def admin_logout():
    """Admin logout handler."""
    session.pop("is_admin", None)
    log_audit("admin", "ADMIN_LOGOUT", "Admin logged out")
    flash("Successfully logged out from Admin Panel.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin", strict_slashes=False)
@app.route("/admin.html")
@login_required
def admin_dashboard():
    """Private Admin Dashboard with real-time crowd analytics and registration table."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch registrations with member aggregation
    if conn.db_kind == "postgresql":
        cursor.execute("""
            SELECT r.*,
                   COUNT(m.id) as accompanying_count,
                   STRING_AGG(m.member_name || ' (' || m.member_age || 'y)', ', ') as members_summary
            FROM registrations r
            LEFT JOIN group_members m ON r.id = m.reg_id
            GROUP BY r.id
            ORDER BY r.id DESC
            LIMIT 200
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
            LIMIT 200
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
            LIMIT 200
        """)
    registrations = cursor.fetchall()

    # Total headcount & total passes
    cursor.execute("SELECT SUM(group_count) as total_people, COUNT(id) as total_passes FROM registrations")
    stats_row = cursor.fetchone()
    total_people = (stats_row["total_people"] or 0) if stats_row else 0
    total_passes = (stats_row["total_passes"] or 0) if stats_row else 0

    # Admitted crowd (checked in)
    cursor.execute("SELECT SUM(group_count) as admitted_people FROM registrations WHERE checked_in = 1")
    admitted_row = cursor.fetchone()
    admitted_people = (admitted_row["admitted_people"] or 0) if admitted_row else 0

    # Currently inside (checked in and not checked out)
    cursor.execute("SELECT SUM(group_count) as inside FROM registrations WHERE checked_in = 1 AND (checked_out = 0 OR checked_out IS NULL)")
    inside_row = cursor.fetchone()
    current_inside = (inside_row["inside"] or 0) if inside_row else 0

    # Exited crowd
    cursor.execute("SELECT SUM(group_count) as exited FROM registrations WHERE checked_out = 1")
    exited_row = cursor.fetchone()
    exited_people = (exited_row["exited"] or 0) if exited_row else 0

    # Capacity
    cfg = get_event_config()
    capacity = int(cfg.get("event_capacity") or 1000)
    remaining_capacity = max(0, capacity - current_inside)

    # Gate capacity breakdown
    cursor.execute("""
        SELECT gate_id, SUM(group_count) as gate_headcount
        FROM registrations
        GROUP BY gate_id
    """)
    gate_counts = {row["gate_id"]: (row["gate_headcount"] or 0) for row in cursor.fetchall()}

    # Recent Audit Logs
    try:
        cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 15")
        audit_logs = cursor.fetchall()
    except Exception:
        audit_logs = []

    # Guard Accounts
    try:
        cursor.execute("SELECT id, username, full_name, assigned_gate, is_active, created_at FROM guard_accounts ORDER BY id ASC")
        guard_accounts = cursor.fetchall()
    except Exception:
        guard_accounts = []

    conn.close()

    gate_analytics = []
    for g in GATES_CONFIG:
        count = gate_counts.get(g["gate_id"], 0)
        percentage = round((count / total_people * 100), 1) if total_people > 0 else 0
        gate_analytics.append({
            **g,
            "count": count,
            "percentage": percentage
        })

    host_url = request.host_url.rstrip("/")
    entrance_url = f"{host_url}/"
    entrance_qr_base64 = generate_qr_base64(entrance_url)

    # Note: Never leak guard plaintext password in template. We provide a masked indicator.
    guard_password_masked = "••••••••"

    return render_template(
        "admin.html",
        registrations=registrations,
        total_people=total_people,
        total_passes=total_passes,
        admitted_people=admitted_people,
        current_inside=current_inside,
        exited_people=exited_people,
        capacity=capacity,
        remaining_capacity=remaining_capacity,
        gate_analytics=gate_analytics,
        entrance_url=entrance_url,
        entrance_qr=entrance_qr_base64,
        guard_password=guard_password_masked,
        guard_accounts=guard_accounts,
        audit_logs=audit_logs,
        is_emergency=is_emergency_active()
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
    """Admin updates event-level configuration."""
    fields = ["event_name", "event_venue", "event_date", "event_capacity", "event_description"]
    for field in fields:
        value = request.form.get(field, "").strip()
        if value:
            _set_setting(field, value)

    log_audit("admin", "EVENT_SETTINGS_UPDATED", "Venue event settings modified")
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

    log_audit("admin", "EXPORT_CSV", f"Exported {len(records)} visitor records to CSV")

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
    log_audit("admin", "REGISTRATION_DELETED", f"Deleted registration #{reg_id}")
    flash(f"Registration #{reg_id} deleted successfully.", "info")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# EMERGENCY MANAGEMENT API
# ---------------------------------------------------------------------------

@app.route("/api/admin/emergency", methods=["POST"])
@login_required
def api_toggle_emergency():
    """Admin activates or resolves Venue Emergency Mode."""
    data = request.get_json(silent=True) or request.form
    action = data.get("action", "activate").lower()
    reason = data.get("reason", "Evacuation Protocol Triggered by Incident Commander").strip()

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()

    if action == "activate":
        _set_setting("emergency_mode", "1")
        _set_setting("emergency_reason", reason)
        try:
            cursor.execute(
                "INSERT INTO emergency_events (status, reason, activated_by, activated_at) VALUES ('EMERGENCY', ?, 'Admin', ?)",
                (reason, now_str)
            )
            conn.commit()
        except Exception:
            pass
        log_audit("admin", "EMERGENCY_ACTIVATED", f"Reason: {reason}")
        conn.close()
        return jsonify({
            "success": True,
            "emergency_mode": True,
            "message": "EMERGENCY PROTOCOL ACTIVATED. Entrances restricted, exit alarms active."
        })
    else:
        _set_setting("emergency_mode", "0")
        _set_setting("emergency_reason", "")
        try:
            cursor.execute(
                "UPDATE emergency_events SET status = 'RESOLVED', resolved_at = ? WHERE status = 'EMERGENCY' AND resolved_at IS NULL",
                (now_str,)
            )
            conn.commit()
        except Exception:
            pass
        log_audit("admin", "EMERGENCY_RESOLVED", "All emergency alerts cleared")
        conn.close()
        return jsonify({
            "success": True,
            "emergency_mode": False,
            "message": "Emergency Mode cleared. Regular venue operations resumed."
        })


@app.route("/api/emergency/status", methods=["GET"])
def api_emergency_status():
    """Real-time emergency status and evacuation route allocations."""
    is_em = is_emergency_active()
    reason = _get_setting("emergency_reason") or "Emergency evacuation in effect"
    inside = get_current_occupancy()

    # Dynamic group split based on 4 normal exit corridors
    # (Example: inside / 4 groups)
    group_size = max(1, math.ceil(inside / 4)) if inside > 0 else 0

    evac_routes = [
        {
            "corridor": "Corridor A (West)",
            "gate": "Exit A (West)",
            "target_zone": "West Boulevard & Staging Ground Alpha",
            "evacuation_group": "Group A",
            "estimated_people": group_size,
            "instructions": "Follow green emergency markers West towards wide boulevard."
        },
        {
            "corridor": "Corridor B (North)",
            "gate": "Exit B (North)",
            "target_zone": "Main Highway & North Open Parking",
            "evacuation_group": "Group B",
            "estimated_people": group_size,
            "instructions": "Proceed steadily North towards parking lot assembly."
        },
        {
            "corridor": "Corridor C (East)",
            "gate": "Exit C (East)",
            "target_zone": "East Plaza & Transit Loop",
            "evacuation_group": "Group C",
            "estimated_people": group_size,
            "instructions": "Proceed East towards shuttle departure zones."
        },
        {
            "corridor": "Corridor D (South)",
            "gate": "Exit D (South)",
            "target_zone": "South Promenade & Open Grounds",
            "evacuation_group": "Group D",
            "estimated_people": group_size,
            "instructions": "Exit South towards open park area."
        }
    ]

    return jsonify({
        "success": True,
        "is_emergency": is_em,
        "reason": reason if is_em else None,
        "current_occupancy": inside,
        "evacuation_routes": evac_routes,
        "staff_gate": STAFF_GATE
    })


# ---------------------------------------------------------------------------
# GUARD ACCOUNT MANAGEMENT API
# ---------------------------------------------------------------------------

@app.route("/api/admin/guard-accounts", methods=["GET", "POST"])
@login_required
def api_guard_accounts():
    """Admin lists or creates individual guard checkpoint accounts."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        username = (data.get("username") or "").strip().lower()
        full_name = (data.get("full_name") or "").strip()
        password = (data.get("password") or "").strip()
        assigned_gate = (data.get("assigned_gate") or "all").strip()

        if not username or not full_name or not password:
            conn.close()
            return jsonify({"success": False, "message": "Username, name, and password are required."}), 400

        pwd_hash = _bcrypt_hash(password)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            cursor.execute(
                "INSERT INTO guard_accounts (username, password_hash, full_name, assigned_gate, is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                (username, pwd_hash, full_name, assigned_gate, now_str)
            )
            conn.commit()
            log_audit("admin", "GUARD_ACCOUNT_CREATED", f"Created guard account: {username}")
            conn.close()
            return jsonify({"success": True, "message": f"Guard account '{username}' created."})
        except Exception as e:
            conn.close()
            return jsonify({"success": False, "message": f"Failed to create account: {e}"}), 400

    cursor.execute("SELECT id, username, full_name, assigned_gate, is_active, created_at FROM guard_accounts ORDER BY id ASC")
    guards = cursor.fetchall()
    conn.close()

    return jsonify({
        "success": True,
        "guards": [dict(g) if not isinstance(g, dict) else g for g in guards]
    })


@app.route("/api/admin/audit-logs", methods=["GET"])
@login_required
def api_audit_logs():
    """Retrieve security audit logs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 50")
    logs = cursor.fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "logs": [dict(l) if not isinstance(l, dict) else l for l in logs]
    })


# ---------------------------------------------------------------------------
# HARDWARE / IOT TELEMETRY API (ESP8266 + Ultrasonic + Buzzer)
# ---------------------------------------------------------------------------

@app.route("/api/hardware/telemetry", methods=["GET", "POST"])
def api_hardware_telemetry():
    """
    Authenticated Endpoint for NodeMCU ESP8266 Ultrasonic Sensor & Alarm System.
    Requires 'X-Device-Key' Header for mutual authentication.
    """
    device_key = request.headers.get("X-Device-Key") or request.args.get("key")
    if not device_key or device_key != HARDWARE_API_KEY:
        return jsonify({"success": False, "message": "UNAUTHORIZED: Invalid Device Authentication Key"}), 401

    is_em = is_emergency_active()
    inside = get_current_occupancy()
    cfg = get_event_config()
    capacity = int(cfg.get("event_capacity") or 1000)

    # If telemetry report sent by hardware
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        distance_cm = data.get("distance_cm")
        gate_sensor = data.get("gate_id", "entry_gate")
        try:
            log_audit("hardware", "IOT_PING", f"Sensor {gate_sensor} distance={distance_cm}cm, inside={inside}")
        except Exception:
            pass

    return jsonify({
        "success": True,
        "device_status": "AUTHENTICATED",
        "emergency_mode": is_em,
        "buzzer_active": is_em or (inside >= capacity),
        "current_occupancy": inside,
        "capacity": capacity,
        "gate_status": "CLOSED" if (is_em or inside >= capacity) else "OPEN"
    })


# ---------------------------------------------------------------------------
# API — Paginated Registrations (Admin AJAX)
# ---------------------------------------------------------------------------

@app.route("/api/registrations", methods=["GET"])
@login_required
def api_registrations():
    """Paginated and searchable JSON endpoint for admin AJAX registration table."""
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 25))))
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all").lower()
    gate_id = request.args.get("gate_id", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

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
    elif status == "exited":
        conditions.append("r.checked_out = 1")

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

    count_sql = f"SELECT COUNT(r.id) as total FROM registrations r {where_sql}"
    cursor.execute(count_sql, params)
    count_row = cursor.fetchone()
    total = count_row["total"] if count_row else 0
    total_pages = max(1, math.ceil(total / per_page))

    offset = (page - 1) * per_page

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
               r.checked_out, r.checked_out_at,
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
            "checked_out": r["checked_out"] if "checked_out" in r else 0,
            "checked_out_at": (r["checked_out_at"] if "checked_out_at" in r else "") or "",
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
    """JSON endpoint returning live crowd stats for admin dashboard auto-refresh."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT SUM(group_count) as total_people, COUNT(id) as total_passes FROM registrations")
        stats_row = cursor.fetchone()
        total_people = (stats_row["total_people"] or 0) if stats_row else 0
        total_passes = (stats_row["total_passes"] or 0) if stats_row else 0

        cursor.execute("SELECT SUM(group_count) as admitted_people FROM registrations WHERE checked_in = 1")
        admitted_row = cursor.fetchone()
        admitted_people = (admitted_row["admitted_people"] or 0) if admitted_row else 0

        cursor.execute("SELECT SUM(group_count) as inside FROM registrations WHERE checked_in = 1 AND (checked_out = 0 OR checked_out IS NULL)")
        inside_row = cursor.fetchone()
        current_inside = (inside_row["inside"] or 0) if inside_row else 0

        cursor.execute("SELECT SUM(group_count) as exited FROM registrations WHERE checked_out = 1")
        exited_row = cursor.fetchone()
        exited_people = (exited_row["exited"] or 0) if exited_row else 0

        cursor.execute("""
            SELECT gate_id, SUM(group_count) as gate_headcount
            FROM registrations
            GROUP BY gate_id
        """)
        gate_rows = cursor.fetchall()
        conn.close()

        cfg = get_event_config()
        capacity = int(cfg.get("event_capacity") or 1000)

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
            "current_inside": current_inside,
            "exited_people": exited_people,
            "capacity": capacity,
            "remaining_capacity": max(0, capacity - current_inside),
            "admission_rate": admission_rate,
            "gate_breakdown": gate_breakdown,
            "is_emergency": is_emergency_active(),
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# SECURITY HEADERS & ANTI-CACHE
# ---------------------------------------------------------------------------

@app.after_request
def add_terminal_security_headers(response):
    """Prevent browser from caching sensitive security terminal pages."""
    if request.path.startswith("/guard") or request.path.startswith("/verify") or request.path.startswith("/admin"):
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
    flash("The requested page or pass code was not found.", "warning")
    return redirect(url_for("index"))


@app.errorhandler(429)
def handle_429(e):
    """Rate limit exceeded handler."""
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Too Many Requests", "message": "Rate limit exceeded. Please wait and try again."}), 429
    flash("Too many requests. Please wait a moment and try again.", "error")
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
    print("  VENUEGUARD SMART CROWD MANAGEMENT SYSTEM RUNNING")
    print(f"  Public Portal:  http://127.0.0.1:{port}")
    print(f"  Pass Lookup:    http://127.0.0.1:{port}/check-registration")
    print(f"  Venue Info:     http://127.0.0.1:{port}/venue-info")
    print(f"  Help & Safety:  http://127.0.0.1:{port}/help")
    print(f"  Guard Portal:   http://127.0.0.1:{port}/verify")
    print(f"  Admin Panel:    http://127.0.0.1:{port}/admin")
    print("=" * 63)
    app.run(host="0.0.0.0", port=port, debug=True)
