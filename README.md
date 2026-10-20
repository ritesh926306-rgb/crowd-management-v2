# 🛡️ VenueGuard — Smart Venue Entry & Dynamic Crowd Management System

[![GitHub Pages](https://img.shields.io/badge/Live_Demo-GitHub_Pages-00FFC6?logo=github&logoColor=black)](https://ritesh926306-rgb.github.io/crowd-management-v2/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-4479A1?logo=mysql&logoColor=white)](https://mysql.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![Security: HMAC-SHA256](https://img.shields.io/badge/Security-HMAC--SHA256-00ADB5)](https://en.wikipedia.org/wiki/HMAC)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production-grade, full-stack **Venue Entry & Smart Crowd Management System** built with **Python/Flask**, dual database support (**MySQL 8.0 & SQLite3**), **HMAC-SHA256** cryptographic anti-fraud verification, camera-based QR scanning, and automated **GitHub Actions CI/CD**.

Designed for high-density public venues, religious festivals (temples/mandirs), stadiums, and large concerts to eliminate bottlenecks, prevent stampedes, and block counterfeit tickets.

---

## 🌟 Key Features

- **Dynamic Crowd Load Balancing (Smart Split):** Automatically calculates live headcount across venue gates (West, North, East, South) and assigns visitors to the least congested exit route.
- **Cryptographic Anti-Counterfeit Passes:** Every entry pass is signed with HMAC-SHA256 using a server secret key. Altered screenshots, fake dates, or forged names fail security verification.
- **Live Camera QR Scanner Terminal:** Security guards can scan visitor passes using mobile or laptop cameras with instantaneous admission validation and tamper detection.
- **PIN-Protected Guard Portal:** Dedicated guard terminal with session lock and PIN code (`1234`).
- **Admin Command Center:** Real-time analytics charts, gate congestion split, live visitor search, CSV data export, and admission toggle.
- **Bilingual Interface:** Instant language switching between English and Hindi (हिंदी).
- **Dual Execution Modes:**
  - **Full-Stack Mode:** Python Flask backend with live MySQL/SQLite database and dynamic QR generation.
  - **Static Demo Mode:** Zero-backend interactive demo hosted on GitHub Pages powered by client-side state management.

---

## 📁 Repository Architecture & Folder Structure

```
crowd-management-v2/
├── .github/
│   └── workflows/
│       ├── deploy.yml            # CI/CD: MySQL test, GitHub Pages deploy & GHCR Docker build
│       └── tests.yml             # Automated integration & security test runner
├── .env.example                  # Environment variables template (safe for VCS)
├── .gitignore                    # Excludes keys, .env, DB files, venv, caches
├── Dockerfile                    # Container definition for containerized deployment
├── package.json                  # Node.js runner scripts
├── run_dev.bat                   # 1-Click Windows execution script (auto-detects venv)
├── README.md                     # Comprehensive project documentation
│
├── backend/                      # 🐍 Flask Backend Server
│   ├── app.py                    # Main Flask app, routes, HMAC security, SQLite/MySQL DB
│   ├── schema.sql                # Production MySQL database schema (InnoDB, utf8mb4)
│   ├── requirements.txt          # Python dependencies (Flask, PyMySQL, qrcode, Pillow, etc.)
│   ├── test_app.py               # Unit & integration test suite (6 automated tests)
│   └── venue_crowd.db            # SQLite database (auto-initialized fallback)
│
├── frontend/                     # 🎨 Frontend Web Application
│   ├── build_static.py           # Static site compiler for GitHub Pages deployment
│   ├── templates/                # Jinja2 HTML templates
│   │   ├── base.html             # Base layout, navbar, i18n handler
│   │   ├── index.html            # Visitor registration form & venue architecture overview
│   │   ├── pass.html             # Digital entry pass with dynamic QR & SVG floorplan
│   │   ├── verify.html           # Guard terminal with camera QR scanner & manual lookup
│   │   ├── guard_login.html      # Guard PIN security authentication
│   │   ├── admin.html            # Real-time analytics, crowd control & CSV export
│   │   ├── login.html            # Admin login screen
│   │   └── entrance_poster.html  # High-res printable QR poster for entrance gates
│   └── static/
│       ├── style.css             # Glassmorphism dark-navy responsive design system
│       ├── static-mode.js        # Client-side state bridge for GitHub Pages
│       └── html5-qrcode.min.js   # Fast camera QR scanner library
│
└── dist/                         # 🌐 Compiled static distribution for GitHub Pages
```

---

## 🔒 Security Architecture (Anti-Hacker Hardening)

1. **Zero Secret Exposure in Source Code**:
   - Secrets (`FLASK_SECRET_KEY`, `HMAC_SECRET_KEY`, `ADMIN_PASSWORD`, `GUARD_PIN`, `DB_PASSWORD`) are loaded strictly from the `.env` file via `python-dotenv`.
   - If `.env` is absent, the backend dynamically generates a cryptographically secure 256-bit random key using Python's `secrets.token_hex(32)`.
2. **Strict `.gitignore` Exclusion**:
   - `.env`, `.env.*`, `*.key`, `*.pem`, `*.db`, `*.sqlite3`, and `credentials.json` are excluded from Git commits.
   - Public GitHub repositories only contain `.env.example`.
3. **Parameterized SQL Queries**:
   - All database queries use strict parameterized queries (`?` for SQLite, `%s` for MySQL) to eliminate SQL injection attacks completely.
   - A unified database abstraction layer (`UnifiedConnection`) guarantees compatibility across MySQL and SQLite.
4. **Cryptographic Anti-Counterfeit Verification**:
   - Every visitor pass is digitally signed using HMAC-SHA256:
     $$\text{HMAC-SHA256}(\text{RegCode} \parallel \text{Name} \parallel \text{Mobile} \parallel \text{Gate}, \text{SecretKey})$$
   - Any modification to pass details (such as editing the name or changing the gate) immediately invalidates the signature and triggers a security alert on the guard terminal.

---

## 🗄️ Database Setup (MySQL & SQLite)

The system automatically supports **zero-config SQLite** by default and can switch to **MySQL 8.0+** via configuration:

### 1. Zero-Config SQLite (Default)
No setup required. If `DB_TYPE=sqlite` or MySQL is unavailable, the application automatically initializes `backend/venue_crowd.db`.

### 2. MySQL Setup (Production)
1. Import the schema via MySQL CLI:
   ```bash
   mysql -u root -p < backend/schema.sql
   ```
2. Configure `.env`:
   ```ini
   DB_TYPE=mysql
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your_mysql_password
   DB_NAME=venue_crowd
   ```
*(If MySQL is temporarily unreachable, the application gracefully falls back to SQLite so service is never disrupted).*

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9 or higher
- Git

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ritesh926306-rgb/crowd-management-v2.git
   cd crowd-management-v2
   ```

2. **Set up virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   ```

---

## 🖥️ Running Locally

### Option A: 1-Click Windows Batch Script
Double-click `run_dev.bat` (automatically activates `venv` if present).

### Option B: Python Direct
```bash
python backend/app.py
```

### Option C: NPM Script
```bash
npm run dev
```

---

## 🌐 Application Endpoints & Credentials

| Portal / Page | URL | Description | Default Credentials |
| :--- | :--- | :--- | :--- |
| **Visitor Registration** | [http://127.0.0.1:5000](http://127.0.0.1:5000) | Public registration (English & Hindi) | *Public Access* |
| **Pass Viewer** | [http://127.0.0.1:5000/pass/&lt;code&gt;](http://127.0.0.1:5000) | Digital Entry Pass with SVG Route & QR | *Public (via Pass Code)* |
| **Guard Portal & Scanner** | [http://127.0.0.1:5000/guard](http://127.0.0.1:5000/guard) | Camera QR scanner & admission clearance | Guard PIN: `1234` |
| **Admin Command Center** | [http://127.0.0.1:5000/admin](http://127.0.0.1:5000/admin) | Real-time congestion charts & CSV export | Password: `admin123` |
| **Entrance QR Poster** | [http://127.0.0.1:5000/admin/entrance-poster](http://127.0.0.1:5000/admin/entrance-poster) | Printable gate QR poster for visitors | Password: `admin123` |

---

## 🧪 Automated Testing

Execute the comprehensive test suite verifying registration, group member cascading, HMAC cryptography, anti-tampering verification, and gate capacity balancing:

```bash
python -m unittest discover -s backend -p "test_*.py"
```

Or via npm:
```bash
npm test
```

---

## 🔄 CI/CD & GitHub Actions

The repository includes a GitHub Actions pipeline (`.github/workflows/deploy.yml`):

1. **MySQL 8.0 Service Test:** Boots a containerized MySQL 8.0 database service, runs `schema.sql`, and executes backend integration tests against live MySQL.
2. **GitHub Pages Deployment:** Runs `frontend/build_static.py` to compile the static site and deploys it automatically to the `gh-pages` branch.
3. **Docker Container Registry (GHCR):** Builds a Docker image and publishes it to GitHub Packages (`ghcr.io`).

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
