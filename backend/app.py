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
        conn = sqlite3.connect(SQLITE_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
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
    """Initialize complete 10-table architecture for PostgreSQL, MySQL, or SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if conn.db_kind == "postgresql":
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id BIGSERIAL PRIMARY KEY,
            username VARCHAR(64) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(100) NOT NULL DEFAULT 'Administrator',
            role VARCHAR(50) NOT NULL DEFAULT 'SUPERADMIN',
            is_active SMALLINT NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id BIGSERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            event_date VARCHAR(50) NOT NULL,
            event_time VARCHAR(50) NOT NULL DEFAULT '09:00 AM - 09:00 PM',
            location VARCHAR(255) NOT NULL,
            description TEXT NULL,
            banner_url TEXT NULL,
            max_capacity INTEGER NOT NULL DEFAULT 1000,
            expected_population INTEGER NOT NULL DEFAULT 500,
            is_registration_active SMALLINT NOT NULL DEFAULT 1,
            status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMP NOT NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id BIGSERIAL PRIMARY KEY,
            event_id BIGINT NOT NULL DEFAULT 1,
            visitor_id VARCHAR(64) UNIQUE,
            reg_code VARCHAR(64) UNIQUE NOT NULL,
            language VARCHAR(10) NOT NULL DEFAULT 'en',
            primary_name VARCHAR(255) NOT NULL,
            mobile VARCHAR(20) NOT NULL,
            age INTEGER NOT NULL,
            address TEXT NULL,
            group_count INTEGER NOT NULL DEFAULT 1,
            assigned_group VARCHAR(50) NOT NULL,
            assigned_gate VARCHAR(100) NOT NULL,
            gate_id VARCHAR(50) NOT NULL,
            hmac_signature VARCHAR(128) NOT NULL,
            qr_token VARCHAR(128) NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'VALID',
            created_at TIMESTAMP NOT NULL,
            checked_in SMALLINT DEFAULT 0,
            checked_in_at TIMESTAMP NULL,
            checked_out SMALLINT DEFAULT 0,
            checked_out_at TIMESTAMP NULL,
            scan_attempts INTEGER NOT NULL DEFAULT 0
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
        CREATE TABLE IF NOT EXISTS qr_tokens (
            id BIGSERIAL PRIMARY KEY,
            reg_code VARCHAR(64) NOT NULL,
            token VARCHAR(128) UNIQUE NOT NULL,
            is_revoked SMALLINT NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL
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
            permissions VARCHAR(255) NOT NULL DEFAULT 'scan,lookup,checkout',
            is_active SMALLINT NOT NULL DEFAULT 1,
            last_active_at TIMESTAMP NULL,
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
            guard_id VARCHAR(64) NOT NULL DEFAULT 'guard_default',
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id BIGSERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            target VARCHAR(50) NOT NULL DEFAULT 'ALL',
            is_read SMALLINT NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL
        );
        """)

    elif conn.db_kind == "mysql":
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(100) NOT NULL DEFAULT 'Administrator',
            role VARCHAR(50) NOT NULL DEFAULT 'SUPERADMIN',
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            event_date VARCHAR(50) NOT NULL,
            event_time VARCHAR(50) NOT NULL DEFAULT '09:00 AM - 09:00 PM',
            location VARCHAR(255) NOT NULL,
            description TEXT NULL,
            banner_url TEXT NULL,
            max_capacity INT UNSIGNED NOT NULL DEFAULT 1000,
            expected_population INT UNSIGNED NOT NULL DEFAULT 500,
            is_registration_active TINYINT(1) NOT NULL DEFAULT 1,
            status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
            created_at DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            event_id BIGINT UNSIGNED NOT NULL DEFAULT 1,
            visitor_id VARCHAR(64) NULL UNIQUE,
            reg_code VARCHAR(64) UNIQUE NOT NULL,
            language VARCHAR(10) NOT NULL DEFAULT 'en',
            primary_name VARCHAR(255) NOT NULL,
            mobile VARCHAR(20) NOT NULL,
            age INT UNSIGNED NOT NULL,
            address TEXT NULL,
            group_count INT UNSIGNED NOT NULL DEFAULT 1,
            assigned_group VARCHAR(50) NOT NULL,
            assigned_gate VARCHAR(100) NOT NULL,
            gate_id VARCHAR(50) NOT NULL,
            hmac_signature VARCHAR(128) NOT NULL,
            qr_token VARCHAR(128) NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'VALID',
            created_at DATETIME NOT NULL,
            checked_in TINYINT(1) DEFAULT 0,
            checked_in_at DATETIME NULL,
            checked_out TINYINT(1) DEFAULT 0,
            checked_out_at DATETIME NULL,
            scan_attempts INT UNSIGNED NOT NULL DEFAULT 0
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
        CREATE TABLE IF NOT EXISTS qr_tokens (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            reg_code VARCHAR(64) NOT NULL,
            token VARCHAR(128) NOT NULL UNIQUE,
            is_revoked TINYINT(1) NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL
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
            username VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            assigned_gate VARCHAR(50) NOT NULL DEFAULT 'all',
            permissions VARCHAR(255) NOT NULL DEFAULT 'scan,lookup,checkout',
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            last_active_at DATETIME NULL,
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
            guard_id VARCHAR(64) NOT NULL DEFAULT 'guard_default',
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            target VARCHAR(50) NOT NULL DEFAULT 'ALL',
            is_read TINYINT(1) NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

    else:
        # SQLite
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL DEFAULT 'Administrator',
            role TEXT NOT NULL DEFAULT 'SUPERADMIN',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL DEFAULT '09:00 AM - 09:00 PM',
            location TEXT NOT NULL,
            description TEXT,
            banner_url TEXT,
            max_capacity INTEGER NOT NULL DEFAULT 1000,
            expected_population INTEGER NOT NULL DEFAULT 500,
            is_registration_active INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL DEFAULT 1,
            visitor_id TEXT UNIQUE,
            reg_code TEXT UNIQUE NOT NULL,
            language TEXT NOT NULL DEFAULT 'en',
            primary_name TEXT NOT NULL,
            mobile TEXT NOT NULL,
            age INTEGER NOT NULL,
            address TEXT,
            group_count INTEGER NOT NULL DEFAULT 1,
            assigned_group TEXT NOT NULL,
            assigned_gate TEXT NOT NULL,
            gate_id TEXT NOT NULL,
            hmac_signature TEXT NOT NULL,
            qr_token TEXT,
            status TEXT NOT NULL DEFAULT 'VALID',
            created_at TEXT NOT NULL,
            checked_in INTEGER DEFAULT 0,
            checked_in_at TEXT,
            checked_out INTEGER DEFAULT 0,
            checked_out_at TEXT,
            scan_attempts INTEGER NOT NULL DEFAULT 0
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
        CREATE TABLE IF NOT EXISTS qr_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reg_code TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            is_revoked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
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
            permissions TEXT NOT NULL DEFAULT 'scan,lookup,checkout',
            is_active INTEGER NOT NULL DEFAULT 1,
            last_active_at TEXT,
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
            guard_id TEXT NOT NULL DEFAULT 'guard_default',
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            target TEXT NOT NULL DEFAULT 'ALL',
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """)

    # Dynamic Column Migrations (Safe for existing databases)
    migration_cols = [
        ("registrations", "visitor_id", "TEXT"),
        ("registrations", "event_id", "INTEGER DEFAULT 1"),
        ("registrations", "qr_token", "TEXT"),
        ("registrations", "status", "TEXT DEFAULT 'VALID'"),
        ("registrations", "scan_attempts", "INTEGER DEFAULT 0"),
        ("registrations", "checked_out", "INTEGER DEFAULT 0"),
        ("registrations", "checked_out_at", "TEXT"),
        ("guard_accounts", "permissions", "TEXT DEFAULT 'scan,lookup,checkout'"),
        ("guard_accounts", "last_active_at", "TEXT"),
        ("entry_exit_logs", "guard_id", "TEXT DEFAULT 'guard_default'")
    ]
    for table, col, col_def in migration_cols:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    # Ensure backfilled visitor_id for existing records
    try:
        cursor.execute("SELECT id, reg_code FROM registrations WHERE visitor_id IS NULL OR visitor_id = ''")
        unlabeled = cursor.fetchall()
        for row in unlabeled:
            vid = f"VG-VIS-{10000 + int(row['id'])}"
            cursor.execute("UPDATE registrations SET visitor_id = ? WHERE id = ?", (vid, row["id"]))
    except Exception:
        pass

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# bcrypt & Password Bootstrap
# ---------------------------------------------------------------------------

def _bcrypt_hash(plaintext: str) -> str:
    """Return bcrypt hash of plaintext (bytes -> str). Falls back to plaintext if no bcrypt."""
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
        "event_name": os.environ.get("EVENT_NAME", "Community Cultural & Exhibition Gathering"),
        "event_venue": os.environ.get("EVENT_VENUE", "City Grand Grounds & Exhibition Center"),
        "event_date": os.environ.get("EVENT_DATE", "2026-11-25"),
        "event_time": os.environ.get("EVENT_TIME", "09:00 AM - 09:00 PM"),
        "event_capacity": os.environ.get("EVENT_CAPACITY", "1000"),
        "event_expected": os.environ.get("EVENT_EXPECTED", "500"),
        "event_description": os.environ.get("EVENT_DESCRIPTION", "Smart crowd management, zoned queuing, and visitor safety system."),
        "is_registration_active": "1",
        "event_status": "ACTIVE",
        "emergency_mode": "0",
        "emergency_reason": "",
        "emergency_danger_zone": "Main Gate & Hall Corridor",
        "emergency_safe_gate": "Exit Gate 3 (North Open Ground)",
        "emergency_route_instructions": "Turn Left into North Corridor. Follow green exit signs directly to Gate 3 open staging ground. Keep calm and do not run."
    }
    for k, v in event_defaults.items():
        if not _get_setting(k):
            _set_setting(k, v)


def check_admin_password(candidate: str) -> bool:
    """Verify administrator password against bcrypt hash."""
    stored_hash = _get_setting("admin_password_hash")
    if stored_hash:
        return _bcrypt_check(candidate, stored_hash)
    return candidate == ADMIN_PASSWORD


def check_guard_password(candidate: str) -> bool:
    """Verify guard portal password against bcrypt hash, falling back to plaintext setting."""
    stored_hash = _get_setting("guard_password_hash")
    if stored_hash and _bcrypt_check(candidate, stored_hash):
        return True
    plain = _get_setting("guard_password")
    if plain and candidate == plain:
        return True
    return candidate == GUARD_PIN


def get_guard_password() -> str:
    """Retrieve the current guard password string (for display/edit by Admin)."""
    val = _get_setting("guard_password")
    return val if val else GUARD_PIN


def set_guard_password(new_password: str):
    """Update guard password string and its bcrypt hash in system_settings."""
    _set_setting("guard_password", new_password)
    _set_setting("guard_password_hash", _bcrypt_hash(new_password))


def log_audit(actor: str, action: str, details: str = None):
    """Record an action in the audit_logs table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ip = request.remote_addr if request else "127.0.0.1"
        cursor.execute(
            "INSERT INTO audit_logs (actor, action, details, ip_address, timestamp) VALUES (?, ?, ?, ?, ?)",
            (actor, action, details, ip, now_str)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[AUDIT LOG ERROR] Failed to log {action}: {e}")


def get_event_config() -> dict:
    """Return dictionary of current event configuration (loaded from DB/settings)."""
    return {
        "event_id": _get_setting("active_event_id") or "1",
        "event_name": _get_setting("event_name") or "Community Cultural & Exhibition Gathering",
        "event_venue": _get_setting("event_venue") or "City Grand Grounds & Exhibition Center",
        "event_date": _get_setting("event_date") or "2026-11-25",
        "event_time": _get_setting("event_time") or "09:00 AM - 09:00 PM",
        "event_capacity": _get_setting("event_capacity") or "1000",
        "event_expected": _get_setting("event_expected") or "500",
        "event_description": _get_setting("event_description") or "Smart crowd management, zoned queuing, and visitor safety system.",
        "event_banner_url": _get_setting("event_banner_url") or "",
        "is_registration_active": _get_setting("is_registration_active") or "1",
        "event_status": _get_setting("event_status") or "ACTIVE",
        "emergency_mode": _get_setting("emergency_mode") or "0",
        "emergency_reason": _get_setting("emergency_reason") or ""
    }


def get_current_occupancy() -> int:
    """Return headcount of visitors currently inside (checked in and not checked out)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(group_count), 0) AS inside FROM registrations WHERE checked_in = 1 AND (checked_out = 0 OR checked_out IS NULL) AND status != 'CANCELLED'"
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            if isinstance(row, dict) or hasattr(row, "keys"):
                return int(row["inside"] or 0)
            return int(row[0] or 0)
    except Exception as e:
        print(f"[OCCUPANCY ERROR] {e}")
    return 0


def get_safe_crowd_status() -> str:
    """Classify crowd status without exposing exact sensitive numbers to public."""
    try:
        cfg = get_event_config()
        capacity = int(cfg.get("event_capacity") or 1000)
        inside = get_current_occupancy()
        pct = (inside / capacity) * 100 if capacity > 0 else 0

        if pct < 50:
            return "Normal"
        elif pct < 80:
            return "Busy"
        elif pct < 95:
            return "High Crowd"
        else:
            return "Temporarily Full"
    except Exception:
        return "Normal"


def is_emergency_active() -> bool:
    """Check if emergency mode is active."""
    return _get_setting("emergency_mode") == "1"


# ---------------------------------------------------------------------------
# DB Readiness & Context Processors
# ---------------------------------------------------------------------------

@app.before_request
def ensure_db_ready():
    """Ensure database schema is ready and bootstrap settings on first request."""
    if not getattr(app, "_db_initialized", False):
        try:
            init_db()
            bootstrap_password_hashes()
            app._db_initialized = True
        except Exception as e:
            print(f"[DB INIT WARNING] {e}")


@app.context_processor
def inject_global_context():
    """Inject event configuration and crowd status into all templates."""
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
# Cryptographic Security Helpers (HMAC-SHA256)
# ---------------------------------------------------------------------------

def generate_hmac_signature(reg_code: str, name: str, mobile: str, gate: str) -> str:
    """Generate tamper-proof HMAC-SHA256 signature for visitor entry pass."""
    payload = f"{reg_code}:{name}:{mobile}:{gate}".encode("utf-8")
    return hmac.new(HMAC_SECRET_KEY, payload, hashlib.sha256).hexdigest()


def verify_hmac_signature(reg_code: str, name: str, mobile: str, gate: str, provided_sig: str) -> bool:
    """Verify integrity of entry pass details against expected signature."""
    expected_sig = generate_hmac_signature(reg_code, name, mobile, gate)
    return hmac.compare_digest(expected_sig, provided_sig)


def generate_qr_token(reg_code: str) -> str:
    """Generate unique cryptographically random verification token for QR code."""
    raw = f"{reg_code}:{secrets.token_hex(16)}:{datetime.datetime.now().isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def generate_qr_base64(data_string: str) -> str:
    """Generate high-contrast QR code image as base64 PNG data URL."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2
    )
    qr.add_data(data_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#040D18", back_color="#FFFFFF")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    b64_str = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"


def check_duplicate_mobile_today(mobile: str) -> bool:
    """Check if the given mobile was already registered today (excluding cancelled)."""
    if app.config.get("TESTING") and not app.config.get("TEST_DUPLICATE_CHECK"):
        return False
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        today_prefix = datetime.datetime.now().strftime("%Y-%m-%d") + "%"
        cursor.execute("SELECT id FROM registrations WHERE mobile = ? AND created_at LIKE ? AND status != 'CANCELLED'", (mobile, today_prefix))
        row = cursor.fetchone()
        conn.close()
        return bool(row)
    except Exception:
        return False


def determine_smart_split_gate() -> dict:
    """Assign visitor to the least loaded exit gate."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT gate_id, SUM(group_count) as total
        FROM registrations
        WHERE status != 'CANCELLED'
        GROUP BY gate_id
    """)
    rows = cursor.fetchall()
    conn.close()

    gate_totals = {g["gate_id"]: 0 for g in GATES_CONFIG}
    for row in rows:
        gid = row["gate_id"]
        if gid in gate_totals:
            gate_totals[gid] = row["total"] or 0

    best_gate_id = min(gate_totals, key=gate_totals.get)
    return next((g for g in GATES_CONFIG if g["gate_id"] == best_gate_id), GATES_CONFIG[0])


# ---------------------------------------------------------------------------
# Auth Decorators
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin authentication required.", "error")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


def guard_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not GUARD_PIN_REQUIRED:
            return f(*args, **kwargs)
        if session.get("guard_logged_in") or session.get("is_admin"):
            return f(*args, **kwargs)
        return redirect(url_for("guard_login"))
    return decorated_function


# ---------------------------------------------------------------------------
# VISITOR PUBLIC ROUTES
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Public Visitor Landing Page with Quick 30-Second Registration."""
    lang = request.args.get("lang", "en")
    cfg = get_event_config()
    return render_template(
        "index.html",
        lang=lang,
        gates=GATES_CONFIG,
        event_config=cfg
    )


@app.route("/register", methods=["POST"])
def register():
    """
    Handle visitor registration in 30-60 seconds.
    Collects Full Name, Mobile, Age, Number of People, Optional Members & Address.
    Automatically generates unique Visitor ID, Registration Code, and Signed QR Pass.
    """
    language = request.form.get("language", "en")
    primary_name = request.form.get("primary_name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    age_str = request.form.get("age", "").strip()
    address = request.form.get("address", "").strip()
    group_count_str = request.form.get("group_count", "1").strip()

    # Safety check: Is emergency active?
    if is_emergency_active():
        flash("Online registration is temporarily restricted due to an active venue safety advisory. Please follow staff directions.", "error")
        return redirect(url_for("index", lang=language))

    # Check if registration is active in event settings
    cfg = get_event_config()
    if cfg.get("is_registration_active") == "0" or cfg.get("event_status") == "ENDED":
        flash("Visitor registration is currently closed by the event administrator.", "warning")
        return redirect(url_for("index", lang=language))

    # Basic validation
    if not primary_name or not mobile or not age_str:
        flash("Please fill in all mandatory fields: Full Name, Mobile Number, and Age.", "error")
        return redirect(url_for("index", lang=language))

    clean_mobile = re.sub(r"\D", "", mobile)
    if len(clean_mobile) != 10:
        flash("Please enter a valid 10-digit mobile number.", "error")
        return redirect(url_for("index", lang=language))
    mobile = clean_mobile

    # Capacity check: is venue full?
    cap_val = int(cfg.get("event_capacity") or 1000)
    current_occ = get_current_occupancy()
    if current_occ >= cap_val:
        flash(f"Venue capacity reached ({cap_val} visitors). Online registration is temporarily closed.", "error")
        return redirect(url_for("index", lang=language))

    # Duplicate mobile check
    if check_duplicate_mobile_today(mobile):
        flash("This mobile number is already registered for today. Please use 'Check My Pass' to view your existing pass.", "warning")
        return redirect(url_for("index", lang=language))

    try:
        age = int(age_str)
        if age < 1 or age > 120:
            raise ValueError()
    except ValueError:
        flash("Please enter a valid age between 1 and 120.", "error")
        return redirect(url_for("index", lang=language))

    try:
        num_people = max(1, min(20, int(group_count_str)))
    except ValueError:
        num_people = 1

    # Accompanying members
    member_names = request.form.getlist("member_name[]")
    member_ages = request.form.getlist("member_age[]")
    member_mobiles = request.form.getlist("member_mobile[]")

    members_data = []
    for m_name, m_age, m_mob in zip(member_names, member_ages, member_mobiles):
        m_name = m_name.strip()
        m_age = m_age.strip()
        m_mob = re.sub(r"\D", "", m_mob.strip())
        if m_name and m_age:
            try:
                p_age = int(m_age)
                members_data.append({
                    "name": m_name,
                    "age": p_age,
                    "mobile": m_mob if len(m_mob) == 10 else ""
                })
            except ValueError:
                pass

    total_group_count = max(num_people, 1 + len(members_data))

    # Smart crowd split: Allocate to least loaded exit gate
    assigned = determine_smart_split_gate()

    # Generate Unique Codes
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    rand_suffix = hashlib.md5(f"{mobile}{timestamp_str}".encode()).hexdigest()[:6].upper()
    reg_code = f"REG-{rand_suffix}"
    visitor_id = f"VG-VIS-{secrets.randbelow(90000) + 10000}"
    qr_token = generate_qr_token(reg_code)

    # Compute HMAC Anti-Fraud Signature
    hmac_sig = generate_hmac_signature(reg_code, primary_name, mobile, assigned["name"])
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO registrations (
                visitor_id, reg_code, language, primary_name, mobile, age, address,
                group_count, assigned_group, assigned_gate, gate_id,
                hmac_signature, qr_token, status, scan_attempts, created_at, checked_in, checked_out
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'VALID', 0, ?, 0, 0)
        """, (
            visitor_id, reg_code, language, primary_name, mobile, age, address or "",
            total_group_count, assigned["group"], assigned["name"], assigned["gate_id"],
            hmac_sig, qr_token, created_at
        ))
        reg_id = cursor.lastrowid
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

        try:
            cursor.execute("INSERT INTO qr_tokens (reg_code, token, created_at) VALUES (?, ?, ?)",
                           (reg_code, qr_token, created_at))
        except Exception:
            pass

        conn.commit()
        log_audit("visitor", "REGISTRATION_CREATED", f"Pass {visitor_id} ({reg_code}) generated for {primary_name} ({total_group_count} persons)")
        flash(f"Registration successful! Your digital Visitor ID Pass ({visitor_id}) is ready.", "success")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[REGISTRATION ERROR] {e}")
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
    """Digital Visitor ID Card with dynamic QR Code and download options."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM registrations WHERE reg_code = ? OR visitor_id = ?", (reg_code, reg_code))
    reg = cursor.fetchone()

    if not reg:
        conn.close()
        flash("Registration pass not found. Please register first.", "error")
        return redirect(url_for("index"))

    cursor.execute("SELECT * FROM group_members WHERE reg_id = ?", (reg["id"],))
    members = cursor.fetchall()
    conn.close()

    gate_info = next((g for g in GATES_CONFIG if g["gate_id"] == reg["gate_id"]), GATES_CONFIG[0])

    # Verification URL for the QR code
    host_url = request.host_url.rstrip("/")
    verification_url = f"{host_url}/verify/{reg['reg_code']}"
    qr_code_base64 = generate_qr_base64(verification_url)

    # Privacy masking for public views
    masked_mobile = re.sub(r"\d(?=\d{4})", "*", str(reg["mobile"]))
    masked_reg = dict(reg)
    masked_reg["mobile"] = masked_mobile
    masked_reg["visitor_id"] = dict(reg).get("visitor_id") or f"VG-VIS-{reg['id']}"

    cfg = get_event_config()

    return render_template(
        "pass.html",
        reg=masked_reg,
        gate_info=gate_info,
        members=members,
        qr_code=qr_code_base64,
        verification_url=verification_url,
        event_config=cfg
    )


@app.route("/check-registration", methods=["GET", "POST"])
def check_registration():
    """Secure Pass Lookup: Visitors check pass using Registration ID + Mobile Number."""
    if request.method == "POST":
        query_code = request.form.get("reg_code", "").strip().upper()
        mobile = request.form.get("mobile", "").strip()

        if not query_code or not mobile:
            flash("Please enter both your Registration Code / Visitor ID and Mobile Number.", "error")
            return render_template("check_registration.html")

        clean_input_mobile = re.sub(r"\D", "", mobile)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reg_code, visitor_id, mobile FROM registrations WHERE UPPER(reg_code) = ? OR UPPER(visitor_id) = ?",
            (query_code, query_code)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            flash("No pass found matching this code. Please check the code or register again.", "error")
            return render_template("check_registration.html")

        stored_mobile = str(row["mobile"]).strip()
        clean_stored_mobile = re.sub(r"\D", "", stored_mobile)

        if clean_input_mobile[-10:] != clean_stored_mobile[-10:]:
            flash("Mobile number does not match this Registration Code. Verification denied.", "error")
            return render_template("check_registration.html")

        log_audit("visitor", "PASS_LOOKUP_SUCCESS", f"Pass {row['reg_code']} verified by visitor")
        return redirect(url_for("view_pass", reg_code=row["reg_code"]))

    return render_template("check_registration.html")


@app.route("/api/check-registration", methods=["POST"])
def api_check_registration():
    """API endpoint for visitor pass lookup via JSON."""
    data = request.get_json(silent=True) or request.form
    query_code = (data.get("reg_code") or data.get("visitor_id") or "").strip().upper()
    mobile = (data.get("mobile") or "").strip()

    if not query_code or not mobile:
        return jsonify({"success": False, "message": "Missing registration code or mobile number"}), 400

    clean_input_mobile = re.sub(r"\D", "", mobile)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT reg_code, visitor_id, primary_name, group_count, assigned_gate, status, mobile FROM registrations WHERE UPPER(reg_code) = ? OR UPPER(visitor_id) = ?",
        (query_code, query_code)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"success": False, "message": "No registration found"}), 404

    clean_stored_mobile = re.sub(r"\D", "", str(row["mobile"]))
    if clean_input_mobile[-10:] != clean_stored_mobile[-10:]:
        return jsonify({"success": False, "message": "Mobile number does not match record"}), 403

    return jsonify({
        "success": True,
        "reg_code": row["reg_code"],
        "visitor_id": row["visitor_id"],
        "primary_name": row["primary_name"],
        "group_count": row["group_count"],
        "assigned_gate": row["assigned_gate"],
        "status": row["status"],
        "pass_url": url_for("view_pass", reg_code=row["reg_code"])
    })


@app.route("/venue-info")
def venue_info():
    """Public Venue Blueprint, Gate Navigation, Transit, and Safety Instructions."""
    cfg = get_event_config()
    return render_template(
        "venue_info.html",
        gates=GATES_CONFIG,
        staff_gate=STAFF_GATE,
        event_config=cfg
    )


@app.route("/help")
@app.route("/contact")
@app.route("/help-contact", endpoint="help_contact")
def help_page():
    """Public Help, Contact, Safety Protocols, and Emergency Information."""
    cfg = get_event_config()
    return render_template("help_contact.html", event_config=cfg)


@app.route("/api/public-crowd-status", methods=["GET"])
def api_public_crowd_status():
    """Visitor-safe crowd status indicator without exposing sensitive internal metrics."""
    status = get_safe_crowd_status()
    cfg = get_event_config()
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
    """Guard Authentication Terminal."""
    if not GUARD_PIN_REQUIRED or session.get("guard_logged_in") or session.get("is_admin"):
        return redirect(url_for("verify_pass"))

    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        if check_guard_password(pin):
            session["guard_logged_in"] = True
            session.permanent = True
            log_audit("guard", "GUARD_LOGIN_SUCCESS", "Guard terminal authenticated")
            flash("Guard terminal unlocked. Scanner ready.", "success")
            return redirect(url_for("verify_pass"))
        else:
            log_audit("guard", "GUARD_LOGIN_FAILED", "Invalid guard PIN attempt")
            flash("Invalid Guard Access Password. Access denied.", "error")

    return render_template("guard_login.html")


if HAS_LIMITER:
    limiter.limit("15 per minute")(guard_login)


@app.route("/guard/logout", methods=["GET", "POST"])
def guard_logout():
    """Guard logout handler."""
    session.pop("guard_logged_in", None)
    session.pop("guard_id", None)
    session.pop("guard_username", None)
    session.pop("guard_gate", None)
    log_audit("guard", "GUARD_LOGOUT", "Guard terminal locked")
    if request.method == "POST":
        return jsonify({"success": True, "message": "Terminal locked."}), 200
    flash("Guard terminal locked successfully.", "info")
    return redirect(url_for("guard_login"))


@app.route("/verify", strict_slashes=False)
@app.route("/verify/<reg_code>")
@app.route("/verify-terminal", endpoint="verify_terminal")
@guard_required
def verify_pass(reg_code=None):
    """Guard verification terminal interface with live camera and manual lookup."""
    if not reg_code:
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

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM registrations WHERE reg_code = ? OR visitor_id = ?", (reg_code, reg_code))
    reg = cursor.fetchone()

    if not reg:
        conn.close()
        log_audit("guard", "SCAN_NOT_FOUND", f"Unrecognized pass code {reg_code}")
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

    is_hmac_valid = verify_hmac_signature(
        reg["reg_code"],
        reg["primary_name"],
        reg["mobile"],
        reg["assigned_gate"],
        reg["hmac_signature"]
    )

    gate_info = next((g for g in GATES_CONFIG if g["gate_id"] == reg["gate_id"]), GATES_CONFIG[0])
    is_already_checked_in = (reg["checked_in"] == 1)
    is_cancelled = (dict(reg).get("status", "VALID") == "CANCELLED")

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
        is_valid=not is_cancelled,
        tamper_reason="PASS CANCELLED BY ADMINISTRATION." if is_cancelled else None,
        reg=reg,
        members=members,
        gate_info=gate_info,
        is_already_checked_in=is_already_checked_in,
        guard_active=bool(session.get("guard_logged_in") or session.get("is_admin"))
    )


@app.route("/api/verify/<reg_code>", methods=["GET"])
def api_verify_pass(reg_code):
    """
    Real-time JSON Verification API with 4 distinct status outcomes:
    - GREEN: Valid Registration
    - RED: Invalid or Fake QR
    - ORANGE: Already Scanned
    - GREY: Cancelled Registration
    Enforces Guard Privacy Rule: Omits private mobile and address from guard view!
    """
    if GUARD_PIN_REQUIRED and not (session.get("guard_logged_in") or session.get("is_admin")):
        return jsonify({
            "success": False,
            "status": "UNAUTHORIZED",
            "result_color": "RED",
            "result_label": "Unauthorized Access",
            "is_valid": False,
            "tamper_reason": "Guard login required to scan/verify passes."
        }), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM registrations WHERE reg_code = ? OR visitor_id = ?", (reg_code, reg_code))
    reg = cursor.fetchone()

    if not reg:
        conn.close()
        return jsonify({
            "success": False,
            "status": "INVALID",
            "result_color": "RED",
            "result_label": "Invalid or Fake QR",
            "is_valid": False,
            "tamper_reason": "REGISTRATION CODE NOT FOUND IN DATABASE. POTENTIAL COUNTERFEIT PASS."
        }), 404

    reg_status = (dict(reg).get("status") or "VALID").upper()
    is_cancelled = (reg_status == "CANCELLED")

    cursor.execute("SELECT * FROM group_members WHERE reg_id = ?", (reg["id"],))
    members_raw = cursor.fetchall()

    members = [
        {
            "member_name": m["member_name"],
            "member_age": m["member_age"]
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
    is_checked_out = bool(dict(reg).get("checked_out") or 0)

    # 1. Handle RED: Invalid / Fake QR (HMAC mismatch)
    if not is_hmac_valid:
        conn.close()
        log_audit("guard", "PASS_TAMPER_DETECTED", f"HMAC signature mismatch on {reg_code}")
        return jsonify({
            "success": False,
            "status": "INVALID",
            "result_color": "RED",
            "result_label": "Invalid or Fake QR",
            "is_valid": False,
            "tamper_reason": "CRYPTOGRAPHIC SIGNATURE MISMATCH! DATA TAMPERING DETECTED."
        })

    # 2. Handle GREY: Cancelled Registration
    if is_cancelled:
        conn.close()
        log_audit("guard", "CANCELLED_PASS_SCANNED", f"Cancelled pass {reg_code} attempted entry")
        return jsonify({
            "success": True,
            "status": "CANCELLED",
            "result_color": "GREY",
            "result_label": "Cancelled Registration",
            "is_valid": False,
            "is_cancelled": True,
            "tamper_reason": "THIS PASS HAS BEEN CANCELLED BY VENUE ADMINISTRATION. ENTRY STRICTLY DENIED.",
            "reg": {
                "visitor_id": dict(reg).get("visitor_id") or reg["reg_code"],
                "reg_code": reg["reg_code"],
                "primary_name": reg["primary_name"],
                "group_count": reg["group_count"],
                "status": "CANCELLED"
            }
        })

    # 3. Handle ORANGE: Already Scanned (Duplicate Scan Attempt)
    if is_already_checked_in:
        try:
            cursor.execute("UPDATE registrations SET scan_attempts = scan_attempts + 1 WHERE id = ?", (reg["id"],))
            conn.commit()
        except Exception:
            pass
        conn.close()
        log_audit("guard", "DUPLICATE_SCAN_ATTEMPT", f"Duplicate scan for {reg_code} (Visitor: {reg['primary_name']})")
        return jsonify({
            "success": True,
            "status": "ALREADY_SCANNED",
            "result_color": "ORANGE",
            "result_label": "Already Scanned",
            "is_valid": True,
            "is_already_checked_in": True,
            "tamper_reason": "ANTI-PASSBACK ALERT: This pass was already admitted. Check visitor identity.",
            "reg": {
                "visitor_id": dict(reg).get("visitor_id") or reg["reg_code"],
                "reg_code": reg["reg_code"],
                "primary_name": reg["primary_name"],
                "group_count": reg["group_count"],
                "assigned_gate": reg["assigned_gate"],
                "checked_in": 1,
                "checked_in_at": reg["checked_in_at"] or "",
                "status": "ALREADY_SCANNED"
            },
            "gate_info": gate_info,
            "members": members
        })

    # 4. Handle GREEN: Valid Registration
    conn.close()
    return jsonify({
        "success": True,
        "status": "VALID",
        "result_color": "GREEN",
        "result_label": "Valid Registration",
        "is_valid": True,
        "is_already_checked_in": False,
        "is_checked_out": is_checked_out,
        "reg": {
            "visitor_id": dict(reg).get("visitor_id") or reg["reg_code"],
            "reg_code": reg["reg_code"],
            "primary_name": reg["primary_name"],
            "group_count": reg["group_count"],
            "assigned_gate": reg["assigned_gate"],
            "assigned_group": reg["assigned_group"],
            "gate_id": reg["gate_id"],
            "checked_in": 0,
            "checked_in_at": "",
            "checked_out": 0,
            "status": "VALID"
        },
        "gate_info": gate_info,
        "members": members
    })


@app.route("/api/check-in/<reg_code>", methods=["POST"])
def api_check_in(reg_code):
    """Mark visitor entry at check-in gate."""
    if GUARD_PIN_REQUIRED and not (session.get("guard_logged_in") or session.get("is_admin")):
        return jsonify({"success": False, "message": "UNAUTHORIZED: Guard login required."}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, group_count, gate_id, checked_in, status FROM registrations WHERE reg_code = ? OR visitor_id = ?", (reg_code, reg_code))
    reg = cursor.fetchone()

    if not reg:
        conn.close()
        return jsonify({"success": False, "message": "Registration not found"}), 404

    if dict(reg).get("status") == "CANCELLED":
        conn.close()
        return jsonify({"success": False, "message": "Entry denied: pass is cancelled"}), 403

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE registrations SET checked_in = 1, checked_in_at = ?, status = 'CHECKED_IN' WHERE id = ?",
        (now_str, reg["id"])
    )

    try:
        cursor.execute(
            "INSERT INTO entry_exit_logs (reg_code, action, headcount, gate_id, guard_name, timestamp) VALUES (?, 'ENTRY', ?, ?, 'Duty Guard', ?)",
            (reg_code, reg["group_count"], reg["gate_id"], now_str)
        )
    except Exception:
        pass

    conn.commit()
    conn.close()
    log_audit("guard", "VISITOR_ADMITTED", f"Pass {reg_code} admitted ({reg['group_count']} persons)")

    return jsonify({
        "success": True,
        "checked_in": 1,
        "checked_in_at": now_str,
        "status": "CHECKED_IN"
    })


@app.route("/api/check-out/<reg_code>", methods=["POST"])
def api_check_out(reg_code):
    """Mark visitor departure at designated exit gate."""
    if GUARD_PIN_REQUIRED and not (session.get("guard_logged_in") or session.get("is_admin")):
        return jsonify({"success": False, "message": "UNAUTHORIZED: Guard login required."}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, group_count, gate_id, checked_in, checked_out FROM registrations WHERE reg_code = ? OR visitor_id = ?", (reg_code, reg_code))
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
            flash("Welcome to Venue Command & Control Admin Panel.", "success")
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
    """Central Admin Control Dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()

    search_q = request.args.get("q", "").strip()

    # Fetch registrations
    if search_q:
        q_like = f"%{search_q}%"
        cursor.execute("""
            SELECT r.*,
                   COUNT(m.id) as accompanying_count,
                   GROUP_CONCAT(m.member_name || ' (' || m.member_age || 'y)', ', ') as members_summary
            FROM registrations r
            LEFT JOIN group_members m ON r.id = m.reg_id
            WHERE r.primary_name LIKE ? OR r.mobile LIKE ? OR r.reg_code LIKE ? OR r.visitor_id LIKE ?
            GROUP BY r.id
            ORDER BY r.id DESC
            LIMIT 300
        """, (q_like, q_like, q_like, q_like))
    else:
        cursor.execute("""
            SELECT r.*,
                   COUNT(m.id) as accompanying_count,
                   GROUP_CONCAT(m.member_name || ' (' || m.member_age || 'y)', ', ') as members_summary
            FROM registrations r
            LEFT JOIN group_members m ON r.id = m.reg_id
            GROUP BY r.id
            ORDER BY r.id DESC
            LIMIT 300
        """)
    registrations = cursor.fetchall()

    # Total headcount & total passes
    cursor.execute("SELECT SUM(group_count) as total_people, COUNT(id) as total_passes FROM registrations WHERE status != 'CANCELLED'")
    stats_row = cursor.fetchone()
    total_people = (stats_row["total_people"] or 0) if stats_row else 0
    total_passes = (stats_row["total_passes"] or 0) if stats_row else 0

    # Total solo visitors
    cursor.execute("SELECT COUNT(id) as solo_count FROM registrations WHERE group_count = 1 AND status != 'CANCELLED'")
    solo_row = cursor.fetchone()
    total_solo = (solo_row["solo_count"] or 0) if solo_row else 0

    # Cancelled count
    cursor.execute("SELECT COUNT(id) as cancelled_count FROM registrations WHERE status = 'CANCELLED'")
    canc_row = cursor.fetchone()
    cancelled_count = (canc_row["cancelled_count"] or 0) if canc_row else 0

    # Admitted crowd (checked in)
    cursor.execute("SELECT SUM(group_count) as admitted_people FROM registrations WHERE checked_in = 1 AND status != 'CANCELLED'")
    admitted_row = cursor.fetchone()
    admitted_people = (admitted_row["admitted_people"] or 0) if admitted_row else 0

    # Currently inside (checked in and not checked out)
    cursor.execute("SELECT SUM(group_count) as inside FROM registrations WHERE checked_in = 1 AND (checked_out = 0 OR checked_out IS NULL) AND status != 'CANCELLED'")
    inside_row = cursor.fetchone()
    current_inside = (inside_row["inside"] or 0) if inside_row else 0

    # Exited crowd
    cursor.execute("SELECT SUM(group_count) as exited FROM registrations WHERE checked_out = 1 AND status != 'CANCELLED'")
    exited_row = cursor.fetchone()
    exited_people = (exited_row["exited"] or 0) if exited_row else 0

    # Duplicate scan attempts count
    cursor.execute("SELECT SUM(scan_attempts) as dup_attempts FROM registrations")
    dup_row = cursor.fetchone()
    duplicate_scan_attempts = (dup_row["dup_attempts"] or 0) if dup_row else 0

    # Capacity
    cfg = get_event_config()
    capacity = int(cfg.get("event_capacity") or 1000)
    remaining_capacity = max(0, capacity - current_inside)
    pending_people = max(0, total_people - admitted_people)

    # Gate breakdown
    cursor.execute("""
        SELECT gate_id, SUM(group_count) as gate_headcount
        FROM registrations
        WHERE status != 'CANCELLED'
        GROUP BY gate_id
    """)
    gate_counts = {row["gate_id"]: (row["gate_headcount"] or 0) for row in cursor.fetchall()}

    # Recent Audit Logs
    try:
        cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 25")
        audit_logs = cursor.fetchall()
    except Exception:
        audit_logs = []

    # Guard Accounts
    try:
        cursor.execute("SELECT id, username, full_name, assigned_gate, permissions, is_active, created_at FROM guard_accounts ORDER BY id ASC")
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
    guard_password_masked = "••••••••"

    return render_template(
        "admin.html",
        registrations=registrations,
        total_people=total_people,
        total_passes=total_passes,
        total_solo=total_solo,
        admitted_people=admitted_people,
        current_inside=current_inside,
        exited_people=exited_people,
        capacity=capacity,
        remaining_capacity=remaining_capacity,
        pending_people=pending_people,
        cancelled_count=cancelled_count,
        duplicate_scan_attempts=duplicate_scan_attempts,
        gate_analytics=gate_analytics,
        entrance_url=entrance_url,
        entrance_qr=entrance_qr_base64,
        guard_password=guard_password_masked,
        guard_accounts=guard_accounts,
        audit_logs=audit_logs,
        event_config=cfg,
        is_emergency=is_emergency_active(),
        search_query=search_q
    )


# ---------------------------------------------------------------------------
# ADMIN EVENT MANAGEMENT APIS
# ---------------------------------------------------------------------------

@app.route("/api/admin/event/update", methods=["POST"])
@login_required
def api_update_event():
    """Admin updates event settings: title, date, time, location, capacity, etc."""
    data = request.get_json(silent=True) or request.form

    title = (data.get("event_name", "") or data.get("event_title", "")).strip()
    venue = (data.get("event_venue", "") or data.get("event_location", "")).strip()
    date_str = data.get("event_date", "").strip()
    time_str = data.get("event_time", "").strip()
    capacity_str = (data.get("event_capacity", "") or data.get("max_capacity", "")).strip()
    expected_str = (data.get("event_expected", "") or data.get("expected_population", "")).strip()
    desc = data.get("event_description", "").strip()
    is_active = data.get("is_registration_active") if "is_registration_active" in data else data.get("registration_open", "1")
    event_status = data.get("event_status", "ACTIVE")

    if title:
        _set_setting("event_name", title)
    if venue:
        _set_setting("event_venue", venue)
    if date_str:
        _set_setting("event_date", date_str)
    if time_str:
        _set_setting("event_time", time_str)
    if capacity_str and capacity_str.isdigit():
        _set_setting("event_capacity", capacity_str)
    if expected_str and expected_str.isdigit():
        _set_setting("event_expected", expected_str)
    if desc:
        _set_setting("event_description", desc)
    _set_setting("is_registration_active", "1" if str(is_active) in ("1", "true", "True") else "0")
    _set_setting("event_status", event_status)

    log_audit("admin", "EVENT_SETTINGS_UPDATED", f"Updated event '{title}' at '{venue}', capacity {capacity_str}")

    if request.is_json:
        return jsonify({"success": True, "message": "Event configuration updated successfully."})
    flash("Event configuration updated successfully.", "success")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# ADMIN VISITOR DATABASE MANAGEMENT APIS
# ---------------------------------------------------------------------------

@app.route("/api/admin/visitors/<int:reg_id>/cancel", methods=["POST"])
@login_required
def api_cancel_visitor(reg_id):
    """Admin cancels a visitor registration."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT reg_code, primary_name FROM registrations WHERE id = ?", (reg_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "message": "Visitor not found"}), 404

    cursor.execute("UPDATE registrations SET status = 'CANCELLED' WHERE id = ?", (reg_id,))
    conn.commit()
    conn.close()
    log_audit("admin", "REGISTRATION_CANCELLED", f"Cancelled pass {row['reg_code']} ({row['primary_name']})")

    if request.is_json:
        return jsonify({"success": True, "message": f"Registration {row['reg_code']} cancelled."})
    flash(f"Registration {row['reg_code']} cancelled.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/api/admin/visitors/<int:reg_id>/edit", methods=["POST"])
@login_required
def api_edit_visitor(reg_id):
    """Admin updates visitor information."""
    data = request.get_json(silent=True) or request.form
    name = data.get("primary_name", "").strip()
    mobile = data.get("mobile", "").strip()
    age_str = data.get("age", "").strip()
    address = data.get("address", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registrations WHERE id = ?", (reg_id,))
    reg = cursor.fetchone()
    if not reg:
        conn.close()
        return jsonify({"success": False, "message": "Visitor not found"}), 404

    new_name = name or reg["primary_name"]
    new_mobile = mobile or reg["mobile"]
    new_age = int(age_str) if (age_str and age_str.isdigit()) else reg["age"]
    new_address = address if address is not None else reg["address"]

    # Re-compute HMAC signature with updated details
    new_hmac = generate_hmac_signature(reg["reg_code"], new_name, new_mobile, reg["assigned_gate"])

    cursor.execute("""
        UPDATE registrations
        SET primary_name = ?, mobile = ?, age = ?, address = ?, hmac_signature = ?
        WHERE id = ?
    """, (new_name, new_mobile, new_age, new_address, new_hmac, reg_id))

    conn.commit()
    conn.close()
    log_audit("admin", "VISITOR_RECORD_EDITED", f"Edited record for {reg['reg_code']}")

    if request.is_json:
        return jsonify({"success": True, "message": "Visitor record updated."})
    flash("Visitor record updated successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/api/admin/visitors/<int:reg_id>/delete", methods=["POST"])
@login_required
def api_delete_visitor(reg_id):
    """Admin permanently deletes a registration according to data retention policy."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT reg_code, primary_name FROM registrations WHERE id = ?", (reg_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "message": "Visitor not found"}), 404

    cursor.execute("DELETE FROM group_members WHERE reg_id = ?", (reg_id,))
    cursor.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
    conn.commit()
    conn.close()
    log_audit("admin", "VISITOR_RECORD_DELETED", f"Deleted record for {row['reg_code']} ({row['primary_name']})")

    if request.is_json:
        return jsonify({"success": True, "message": "Visitor record deleted."})
    flash(f"Visitor record {row['reg_code']} permanently deleted.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/export-csv")
@login_required
def export_csv():
    """Export complete visitor database to Excel / CSV format."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.visitor_id, r.reg_code, r.primary_name, r.mobile, r.age, r.group_count,
               r.assigned_gate, r.status, r.checked_in, r.checked_in_at, r.checked_out,
               r.checked_out_at, r.scan_attempts, r.created_at, r.address
        FROM registrations r
        ORDER BY r.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Visitor ID", "Registration Code", "Full Name", "Mobile Number", "Age",
        "Group Size", "Assigned Gate", "Status", "Checked In", "Checked In Time",
        "Checked Out", "Checked Out Time", "Duplicate Scan Attempts", "Registered At", "Address"
    ])

    for row in rows:
        writer.writerow([
            row["visitor_id"] or "",
            row["reg_code"],
            row["primary_name"],
            row["mobile"],
            row["age"],
            row["group_count"],
            row["assigned_gate"],
            row["status"] or "VALID",
            "YES" if row["checked_in"] == 1 else "NO",
            row["checked_in_at"] or "",
            "YES" if row["checked_out"] == 1 else "NO",
            row["checked_out_at"] or "",
            row["scan_attempts"] or 0,
            row["created_at"],
            row["address"] or ""
        ])

    csv_data = output.getvalue()
    filename = f"venueguard_visitors_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    log_audit("admin", "CSV_EXPORT", "Exported visitor database to CSV")

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ---------------------------------------------------------------------------
# ADMIN GUARD ACCOUNT & PASSWORD MANAGEMENT
# ---------------------------------------------------------------------------

@app.route("/admin/update-guard-password", methods=["POST"])
@login_required
def update_guard_password():
    """Admin dynamically updates Master Guard access password."""
    new_password = request.form.get("guard_password", "").strip()
    if not new_password:
        flash("Password cannot be blank.", "error")
        return redirect(url_for("admin_dashboard"))

    set_guard_password(new_password)
    log_audit("admin", "GUARD_PASSWORD_ROTATED", "Master guard access password rotated")
    flash(f"Guard Portal password updated successfully to: {new_password}", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/api/admin/guard-accounts/create", methods=["POST"])
@login_required
def api_create_guard_account():
    """Admin creates a new security guard account."""
    data = request.get_json(silent=True) or request.form
    username = data.get("username", "").strip().lower()
    password = data.get("password", "").strip()
    full_name = data.get("full_name", "").strip()
    # Accept 'gate_id' as alias for 'assigned_gate'
    gate = (data.get("assigned_gate") or data.get("gate_id") or "all").strip()

    if not username or not password or not full_name:
        return jsonify({"success": False, "message": "Username, password, and guard name are required."}), 400

    pwd_hash = _bcrypt_hash(password)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO guard_accounts (username, password_hash, full_name, assigned_gate, permissions, is_active, created_at)
            VALUES (?, ?, ?, ?, 'scan,lookup,checkout', 1, ?)
        """, (username, pwd_hash, full_name, gate, now_str))
        conn.commit()
        log_audit("admin", "GUARD_ACCOUNT_CREATED", f"Created guard account '{username}' for {full_name}")
        conn.close()
        return jsonify({"success": True, "message": f"Guard account '{username}' created successfully."})
    except Exception as e:
        conn.close()
        return jsonify({"success": False, "message": f"Account creation failed (username may exist): {e}"}), 400


@app.route("/api/admin/guard-accounts/<int:guard_id>/status", methods=["POST"])
@login_required
def api_toggle_guard_status(guard_id):
    """Admin activates or deactivates a guard account."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, is_active FROM guard_accounts WHERE id = ?", (guard_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "message": "Guard account not found."}), 404

    new_status = 0 if row["is_active"] == 1 else 1
    cursor.execute("UPDATE guard_accounts SET is_active = ? WHERE id = ?", (new_status, guard_id))
    conn.commit()
    conn.close()

    status_label = "activated" if new_status == 1 else "deactivated"
    log_audit("admin", "GUARD_STATUS_CHANGED", f"Guard '{row['username']}' {status_label}")
    return jsonify({"success": True, "is_active": new_status, "message": f"Guard account {status_label}."})


@app.route("/api/admin/guard-accounts/<int:guard_id>/password", methods=["POST"])
@login_required
def api_reset_guard_password(guard_id):
    """Admin resets a guard account password."""
    data = request.get_json(silent=True) or request.form
    new_pwd = data.get("password", "").strip()
    if not new_pwd:
        return jsonify({"success": False, "message": "Password cannot be blank."}), 400

    new_hash = _bcrypt_hash(new_pwd)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE guard_accounts SET password_hash = ? WHERE id = ?", (new_hash, guard_id))
    conn.commit()
    conn.close()

    log_audit("admin", "GUARD_PASSWORD_RESET", f"Reset password for guard ID {guard_id}")
    return jsonify({"success": True, "message": "Guard password reset successfully."})


@app.route("/api/admin/guard-accounts/<int:guard_id>/delete", methods=["POST"])
@login_required
def api_delete_guard_account(guard_id):
    """Admin revokes and deletes a guard account."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM guard_accounts WHERE id = ?", (guard_id,))
    conn.commit()
    conn.close()

    log_audit("admin", "GUARD_ACCOUNT_DELETED", f"Deleted guard account ID {guard_id}")
    return jsonify({"success": True, "message": "Guard account revoked and deleted."})


# ---------------------------------------------------------------------------
# EMERGENCY MANAGEMENT & ROUTING APIS
# ---------------------------------------------------------------------------

@app.route("/api/admin/emergency", methods=["POST"])
@login_required
def api_toggle_emergency():
    """Admin activates or resolves Venue Emergency Mode."""
    data = request.get_json(silent=True) or request.form
    action = data.get("action", "activate").lower()
    reason = data.get("reason", "Evacuation Protocol Triggered by Incident Commander").strip()
    danger_zone = data.get("danger_zone", "Main Gate & Hall Corridor").strip()
    safe_gate = data.get("safe_gate", "Exit Gate 3 (North Open Ground)").strip()
    route_instructions = data.get("route_instructions", "Turn Left into North Corridor. Follow green exit signs directly to Gate 3 open staging ground. Keep calm and do not run.").strip()

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()

    if action == "activate":
        _set_setting("emergency_mode", "1")
        _set_setting("emergency_reason", reason)
        _set_setting("emergency_danger_zone", danger_zone)
        _set_setting("emergency_safe_gate", safe_gate)
        _set_setting("emergency_route_instructions", route_instructions)
        _set_setting("emergency_activated_at", now_str)
        try:
            cursor.execute(
                "INSERT INTO emergency_events (status, reason, activated_by, activated_at) VALUES ('EMERGENCY', ?, 'Admin', ?)",
                (f"[{danger_zone} -> {safe_gate}] {reason}", now_str)
            )
            conn.commit()
        except Exception:
            pass
        log_audit("admin", "EMERGENCY_ACTIVATED", f"Danger: {danger_zone} -> Safe: {safe_gate}. Reason: {reason}")
        conn.close()
        return jsonify({
            "success": True,
            "emergency_mode": True,
            "danger_zone": danger_zone,
            "safe_gate": safe_gate,
            "route_instructions": route_instructions,
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
    danger_zone = _get_setting("emergency_danger_zone") or "Main Gate & Hall Corridor"
    safe_gate = _get_setting("emergency_safe_gate") or "Exit Gate 3 (North Open Ground)"
    route_instructions = _get_setting("emergency_route_instructions") or "Follow green evacuation arrows to Exit Gate 3."
    activated_at = _get_setting("emergency_activated_at") or ""
    inside = get_current_occupancy()

    evac_routes = [
        {
            "corridor": "Corridor A (West)",
            "gate": "Exit A (West)",
            "target_zone": "Transit Hub 1 & West Open Boulevard",
            "instructions": "Follow green emergency markers West towards wide boulevard."
        },
        {
            "corridor": "Corridor B (North)",
            "gate": "Exit B (North)",
            "target_zone": "Main Highway & North Open Parking",
            "instructions": "Proceed steadily North towards open parking staging zone."
        },
        {
            "corridor": "Corridor C (East)",
            "gate": "Exit C (East)",
            "target_zone": "East Ground Plaza & Metro Shuttle",
            "instructions": "Exit East and gather at open staging ground near transit hub."
        },
        {
            "corridor": "Corridor D (South)",
            "gate": "Exit D (South)",
            "target_zone": "South Promenade & Ring Road",
            "instructions": "Follow South concourse signage to Ring Road evacuation zone."
        }
    ]

    return jsonify({
        "success": True,
        "is_emergency": is_em,
        "danger_zone": danger_zone if is_em else None,
        "safe_gate": safe_gate if is_em else None,
        "route_instructions": route_instructions if is_em else None,
        "reason": reason if is_em else None,
        "activated_at": activated_at if is_em else None,
        "current_occupancy": inside,
        "evacuation_routes": evac_routes,
        "staff_gate": STAFF_GATE
    })


# ---------------------------------------------------------------------------
# HARDWARE / IOT TELEMETRY API (NodeMCU ESP8266 + Ultrasonic + Buzzer)
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
# APPLICATION ENTRYPOINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    bootstrap_password_hashes()
    port = int(os.environ.get("PORT", 5000))
    print(f"\n* VenueGuard Crowd Control System Starting on http://127.0.0.1:{port}")
    print(f"* Database Backend: {DB_TYPE.upper()}")
    print(f"* Emergency Mode: {'ACTIVE' if is_emergency_active() else 'OFF'}")
    app.run(host="0.0.0.0", port=port, debug=False)
