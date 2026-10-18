# 🛡️ Smart Venue Entry & Dynamic Crowd Management System

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-4479A1?logo=mysql&logoColor=white)](https://mysql.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![Security: HMAC-SHA256](https://img.shields.io/badge/Security-HMAC--SHA256-00ADB5)](https://en.wikipedia.org/wiki/HMAC)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production-grade, modular **Venue Entry & Smart Crowd Management System** cleanly structured into **Frontend** and **Backend** with **Dual MySQL & SQLite** database engine support.

Designed for high-density public venues, religious festivals (temples/mandirs), stadiums, and large concerts. Includes anti-fraud cryptographic QR pass issuance, capacity-balanced dynamic crowd exit load balancing, guard verification terminals, and an admin command dashboard.

---

## 📁 Clean Architecture & Folder Structure

```
app.py2/
├── .env.example              # Environment variables template (Safe for GitHub)
├── .gitignore                # Comprehensive exclusions (keys, .env, DB, caches)
├── package.json              # NPM scripts ("npm run dev", "npm test")
├── run_dev.bat               # 1-Click Windows execution script
├── README.md                 # Project documentation & start guide
│
├── backend/                  # 🐍 Backend (Flask + MySQL / SQLite + HMAC Security)
│   ├── app.py                # Main backend server, security & REST/Web routes
│   ├── schema.sql            # Production MySQL database schema (InnoDB, utf8mb4)
│   ├── requirements.txt      # Python dependencies (Flask, PyMySQL, qrcode, etc.)
│   ├── test_app.py           # Automated integration test suite
│   └── venue_crowd.db        # SQLite database (auto-created fallback)
│
└── frontend/                 # 🎨 Frontend (Templates & Stylesheets)
    ├── templates/            # Jinja2 HTML templates
    │   ├── base.html         # Common UI layout & head links
    │   ├── index.html        # Bilingual visitor registration page
    │   ├── pass.html         # Digital entry pass with dynamic QR & SVG floorplan
    │   ├── verify.html       # Security guard scan & verify terminal
    │   ├── admin.html        # Real-time analytics, crowd control & CSV export
    │   ├── login.html        # Admin portal secure login
    │   └── entrance_poster.html # Printable QR code poster for venue gates
    └── static/
        └── style.css         # Modern responsive CSS (Dark/Navy/Teal theme)
```

---

## 🔒 Security Architecture (Anti-Hacker Hardening)

To guarantee that no API keys or credentials can ever be stolen or exposed on GitHub:

1. **Zero Secret Exposure in Source Code**:
   - Keys (`FLASK_SECRET_KEY`, `HMAC_SECRET_KEY`, `ADMIN_PASSWORD`, `DB_PASSWORD`) are loaded strictly from the local `.env` file via `python-dotenv`.
   - If `.env` is absent, the backend dynamically generates a cryptographically secure 256-bit random key using Python's `secrets.token_hex(32)`.
2. **Strict `.gitignore` Exclusion**:
   - `.env`, `.env.*`, `*.key`, `*.pem`, `*.db`, `*.sqlite3`, and `credentials.json` are excluded from Git commits.
   - Public GitHub repositories only contain `.env.example`.
3. **Parameterized SQL Queries**:
   - All database queries use strict parameterized queries (`?` for SQLite, `%s` for MySQL) to eliminate SQL injection attacks completely.
4. **Cryptographic Anti-Counterfeit Verification**:
   - Every visitor pass is digitally signed using HMAC-SHA256. Any tampering with pass details instantly triggers a security warning on guard verification terminals.

---

## 🗄️ MySQL Database Setup

The backend natively supports **MySQL** (as well as zero-config SQLite):

### 1. Import Schema into MySQL
You can import the schema via MySQL CLI, phpMyAdmin, or MySQL Workbench:
```bash
mysql -u root -p < backend/schema.sql
```
This creates the `venue_crowd` database with:
- `registrations` (Indexed on `reg_code`, `gate_id`, `checked_in`, `created_at`)
- `group_members` (Foreign key with `ON DELETE CASCADE`)
- `v_gate_congestion` (Real-time analytics view)

### 2. Configure `.env` for MySQL
In your `.env` file (copied from `.env.example`), set:
```ini
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=venue_crowd
```
*(If MySQL is offline or not installed, the application automatically falls back to SQLite so your app never crashes).*

---

## 🚀 Quick Start (Localhost)

### Method 1: With NPM (`npm run dev`)
If you have Node.js / NPM installed:
```bash
npm run dev
```

### Method 2: With Python Direct
```bash
# 1. Install dependencies (only required once)
pip install -r backend/requirements.txt

# 2. Start backend server
python backend/app.py
```

### Method 3: 1-Click Windows Batch Script
Double-click `run_dev.bat` or run:
```cmd
run_dev.bat
```

---

## 🌐 Localhost Access URLs

| Section | Local URL | Description | Default Credentials |
| :--- | :--- | :--- | :--- |
| **Visitor Registration** | [http://127.0.0.1:5000](http://127.0.0.1:5000) | Public registration page (English / Hindi) | *None (Public)* |
| **Admin Command Center**| [http://127.0.0.1:5000/admin](http://127.0.0.1:5000/admin) | Real-time analytics, live headcounts, CSV export | Password: `admin123` |
| **Entrance QR Poster** | [http://127.0.0.1:5000/admin/entrance-poster](http://127.0.0.1:5000/admin/entrance-poster) | Printable gate poster visitors scan to register | Password: `admin123` |
| **Guard Verify Portal** | [http://127.0.0.1:5000/verify](http://127.0.0.1:5000/verify) | Manual ticket lookup and live check-in toggle | *None (Guard access)* |

---

## 🐙 Sync Clean Code to GitHub

To commit and push your cleanly organized code to GitHub safely:

```bash
git add .
git commit -m "Refactor: separate frontend/backend, add MySQL support, and secure keys"
git push origin main
```
*Your secrets (`.env`) and database data (`*.db`) will stay completely private and secure on your local computer.*

---

## 🧪 Running Automated Tests

Run the integration test suite:
```bash
python -m unittest discover -s backend -p "test_*.py"
```
Or via npm:
```bash
npm test
```
All integration tests verify registration, dynamic members, HMAC signature generation, anti-tampering detection, and capacity load balancing.
