#!/usr/bin/env python3
"""
Static Site Generator for GitHub Pages Deployment
Renders Jinja2 templates into static HTML with sample/interactive UI state
and bundles stylesheets for zero-configuration hosting on GitHub Pages.
"""

import os
import shutil
from jinja2 import Environment, FileSystemLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DIST_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "dist"))

# ─── Gate Configuration ───────────────────────────────────────────────────────
GATES_CONFIG = [
    { "group": "Group A", "gate_id": "exit_1", "name": "Exit 1 (West)",  "zone": "Zone Alpha (West Gate)",  "color": "#00FFC6", "description": "Proceed West towards West Boulevard & Transit Hub 1"     },
    { "group": "Group B", "gate_id": "exit_2", "name": "Exit 2 (North)", "zone": "Zone Beta (North Gate)",  "color": "#3B82F6", "description": "Proceed North towards Main Highway & North Parking"       },
    { "group": "Group C", "gate_id": "exit_3", "name": "Exit 3 (East)",  "zone": "Zone Gamma (East Gate)",  "color": "#F59E0B", "description": "Proceed East towards East Plaza & Metro Shuttle"           },
    { "group": "Group D", "gate_id": "exit_4", "name": "Exit 4 (South)", "zone": "Zone Delta (South Gate)", "color": "#A855F7", "description": "Proceed South towards South Promenade & Taxi Stand"        },
]

DEMO_REG = {
    "reg_code": "DEMO-SAMPLE-8899", "primary_name": "Demo Visitor",
    "mobile": "9876543210", "age": 30, "address": "123 Venue Boulevard, Central City",
    "assigned_gate": "Exit 1 (West)", "assigned_group": "Group A",
    "gate_id": "exit_1", "group_count": 2, "checked_in": 0, "checked_in_at": None,
    "created_at": "2026-10-18 20:00:00",
    "hmac_signature": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}

DEMO_MEMBERS = [{"member_name": "Accompanying Guest", "member_age": 28, "member_mobile": "9876543211"}]

DEMO_REGISTRATIONS = [
    { "id": 1, "reg_code": "REG-A1B2C3", "primary_name": "Rajesh Kumar",     "mobile": "9876543210", "age": 34, "address": "45 MG Road, Civil Lines",          "group_count": 2, "assigned_gate": "Exit 1 (West)",  "assigned_group": "Group A", "gate_id": "exit_1", "checked_in": 1, "created_at": "2026-10-18 19:30:00", "checked_in_at": "2026-10-18 19:45:00", "members_summary": "Pooja Kumar (31y)" },
    { "id": 2, "reg_code": "REG-D4E5F6", "primary_name": "Anita Verma",      "mobile": "9812345678", "age": 29, "address": "12 Lake View Apt, Sector 4",        "group_count": 3, "assigned_gate": "Exit 2 (North)", "assigned_group": "Group B", "gate_id": "exit_2", "checked_in": 1, "created_at": "2026-10-18 19:40:00", "checked_in_at": "2026-10-18 20:00:00", "members_summary": "Aarav Verma (6y), Ravi Verma (32y)" },
    { "id": 3, "reg_code": "REG-7G8H9I", "primary_name": "Sunil Patel",      "mobile": "9823456789", "age": 42, "address": "88 Sunrise Colony, Bhopal",         "group_count": 4, "assigned_gate": "Exit 3 (East)",  "assigned_group": "Group C", "gate_id": "exit_3", "checked_in": 0, "created_at": "2026-10-18 20:10:00", "checked_in_at": None,                  "members_summary": "Geeta Patel (39y), Karan Patel (14y), Diya Patel (10y)" },
    { "id": 4, "reg_code": "DEMO-SAMPLE-8899", "primary_name": "Demo Visitor","mobile": "9876543210", "age": 30, "address": "123 Venue Boulevard, Central City", "group_count": 2, "assigned_gate": "Exit 1 (West)",  "assigned_group": "Group A", "gate_id": "exit_1", "checked_in": 0, "created_at": "2026-10-18 20:00:00", "checked_in_at": None,                  "members_summary": "Accompanying Guest (28y)" },
]

def build():
    # Clean and recreate dist
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    os.makedirs(DIST_DIR, exist_ok=True)

    # Copy static assets
    shutil.copytree(STATIC_DIR, os.path.join(DIST_DIR, "static"))

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

    # ─── Mock url_for ─────────────────────────────────────────────────────────
    def mock_url_for(endpoint, **values):
        if endpoint == "static":
            return f"static/{values.get('filename', '')}"
        mapping = {
            "index":               "index.html",
            "register":            "pass.html",
            "admin_login":         "login.html",
            "admin_dashboard":     "admin.html",
            "admin_logout":        "login.html",
            "entrance_poster":     "entrance_poster.html",
            "export_csv":          "#",
            "delete_registration": "#",
        }
        if endpoint in mapping:
            return mapping[endpoint]
        if endpoint == "view_pass":
            return f"pass.html?code={values.get('reg_code', '')}"
        if endpoint == "verify_pass":
            return f"verify.html?code={values.get('reg_code', '')}"
        return f"{endpoint}.html"

    env.globals["url_for"]              = mock_url_for
    env.globals["get_flashed_messages"] = lambda **kwargs: []
    env.globals["session"]              = {}

    class MockRequest:
        args     = {"lang": "en"}
        host_url = "https://ritesh926306-rgb.github.io/crowd-management-v2/"
    env.globals["request"] = MockRequest()

    # ─── QR helpers ───────────────────────────────────────────────────────────
    QR_BASE     = "https://api.qrserver.com/v1/create-qr-code/?size=170x170&format=png&ecc=M"
    VERIFY_BASE = "https://ritesh926306-rgb.github.io/crowd-management-v2/verify.html?code="

    # ─── Pages ────────────────────────────────────────────────────────────────
    pages = [
        ("index.html", "index.html", {"lang": "en", "gates": GATES_CONFIG}),
        ("login.html", "login.html", {}),
        ("pass.html",  "pass.html",  {
            "reg":              DEMO_REG,
            "gate_info":        GATES_CONFIG[0],
            "members":          DEMO_MEMBERS,
            "qr_code":          f"{QR_BASE}&data={VERIFY_BASE}DEMO-SAMPLE-8899",
            "verification_url": "verify.html?code=DEMO-SAMPLE-8899",
        }),
        ("admin.html", "admin.html", {
            "total_people":   9,
            "total_passes":   4,
            "admitted_people": 5,
            "gate_analytics": [
                {"gate_id": "exit_1", "name": "Exit 1 (West)",  "group": "Group A", "zone": "Zone Alpha (West Gate)",  "count": 4, "percentage": 44},
                {"gate_id": "exit_2", "name": "Exit 2 (North)", "group": "Group B", "zone": "Zone Beta (North Gate)",  "count": 3, "percentage": 33},
                {"gate_id": "exit_3", "name": "Exit 3 (East)",  "group": "Group C", "zone": "Zone Gamma (East Gate)", "count": 2, "percentage": 22},
                {"gate_id": "exit_4", "name": "Exit 4 (South)", "group": "Group D", "zone": "Zone Delta (South Gate)","count": 0, "percentage": 0},
            ],
            "registrations": DEMO_REGISTRATIONS,
        }),
        ("verify.html", "verify.html", {
            "is_valid":     True,
            "tamper_reason": None,
            "reg":          DEMO_REG,
            "members":      DEMO_MEMBERS,
            "gate_info":    GATES_CONFIG[0],
        }),
        ("entrance_poster.html", "entrance_poster.html", {
            "entrance_url": "https://ritesh926306-rgb.github.io/crowd-management-v2/",
            "entrance_qr":  f"{QR_BASE}&data=https://ritesh926306-rgb.github.io/crowd-management-v2/",
        }),
    ]

    for template_name, output_filename, context in pages:
        template   = env.get_template(template_name)
        content    = template.render(**context)
        output_path = os.path.join(DIST_DIR, output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[EXPORT] Rendered {template_name} -> {output_filename}")

    # .nojekyll — required for GitHub Pages to serve all files
    with open(os.path.join(DIST_DIR, ".nojekyll"), "w") as f:
        f.write("")

    print(f"[SUCCESS] Frontend bundled successfully to {DIST_DIR}")

if __name__ == "__main__":
    build()
