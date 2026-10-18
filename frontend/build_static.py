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

# Sample exit gates configuration
GATES_CONFIG = [
    {
        "group": "Group A",
        "gate_id": "exit_1",
        "name": "Exit 1 (West)",
        "zone": "Zone Alpha (West Gate)",
        "color": "#00ADB5",
        "description": "Proceed West towards West Boulevard & Transit Hub 1"
    },
    {
        "group": "Group B",
        "gate_id": "exit_2",
        "name": "Exit 2 (North)",
        "zone": "Zone Beta (North Gate)",
        "color": "#1E3E62",
        "description": "Proceed North towards Main Highway & North Parking"
    },
    {
        "group": "Group C",
        "gate_id": "exit_3",
        "name": "Exit 3 (East)",
        "zone": "Zone Gamma (East Gate)",
        "color": "#D97706",
        "description": "Proceed East towards East Plaza & Metro Shuttle"
    },
    {
        "group": "Group D",
        "gate_id": "exit_4",
        "name": "Exit 4 (South)",
        "zone": "Zone Delta (South Gate)",
        "color": "#7C3AED",
        "description": "Proceed South towards South Promenade & Taxi Stand"
    }
]

def build():
    # Clean and recreate dist
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    os.makedirs(DIST_DIR, exist_ok=True)

    # Copy static assets
    dist_static = os.path.join(DIST_DIR, "static")
    shutil.copytree(STATIC_DIR, dist_static)

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

    # Mock url_for helper for static HTML export
    def mock_url_for(endpoint, **values):
        if endpoint == "static":
            filename = values.get("filename", "")
            return f"static/{filename}"
        elif endpoint == "index":
            return "index.html"
        elif endpoint == "register":
            return "pass.html"
        elif endpoint == "admin_login":
            return "login.html"
        elif endpoint == "admin_dashboard":
            return "admin.html"
        elif endpoint == "admin_logout":
            return "login.html"
        elif endpoint == "entrance_poster":
            return "entrance_poster.html"
        elif endpoint == "view_pass":
            return "pass.html"
        elif endpoint == "export_csv":
            return "#"
        return f"{endpoint}.html"

    env.globals["url_for"] = mock_url_for
    env.globals["get_flashed_messages"] = lambda **kwargs: []
    env.globals["session"] = {}
    class MockRequest:
        args = {"lang": "en"}
        host_url = "https://ritesh926306-rgb.github.io/crowd-management-v2/"
    env.globals["request"] = MockRequest()

    # Pages to render
    pages = [
        ("index.html", "index.html", {"lang": "en", "gates": GATES_CONFIG}),
        ("login.html", "login.html", {}),
        ("pass.html", "pass.html", {
            "reg": {
                "reg_code": "DEMO-SAMPLE-8899",
                "primary_name": "Demo Visitor",
                "mobile": "9876543210",
                "age": 30,
                "address": "123 Venue Boulevard, Central City",
                "assigned_gate": "Exit 1 (West)",
                "assigned_group": "Group A",
                "gate_id": "exit_1",
                "group_count": 2,
                "checked_in": 0,
                "created_at": "2026-10-18 20:00:00",
                "hmac_signature": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            },
            "gate_info": GATES_CONFIG[0],
            "members": [{"member_name": "Accompanying Guest", "member_age": 28, "member_mobile": "9876543211"}],
            "qr_code": "https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=https://ritesh926306-rgb.github.io/crowd-management-v2/verify.html?code=DEMO-SAMPLE-8899",
            "verification_url": "verify.html?code=DEMO-SAMPLE-8899"
        }),
        ("admin.html", "admin.html", {
            "total_people": 12,
            "total_passes": 5,
            "admitted_people": 6,
            "gate_analytics": [
                {"gate_id": "exit_1", "name": "Exit 1 (West)", "group": "Group A", "zone": "Zone Alpha", "count": 3, "percentage": 25.0},
                {"gate_id": "exit_2", "name": "Exit 2 (North)", "group": "Group B", "zone": "Zone Beta", "count": 3, "percentage": 25.0},
                {"gate_id": "exit_3", "name": "Exit 3 (East)", "group": "Group C", "zone": "Zone Gamma", "count": 4, "percentage": 33.3},
                {"gate_id": "exit_4", "name": "Exit 4 (South)", "group": "Group D", "zone": "Zone Delta", "count": 2, "percentage": 16.7}
            ],
            "registrations": [
                {"id": 1, "reg_code": "REG-A1B2C3", "primary_name": "Rajesh Kumar", "mobile": "9876543210", "age": 34, "group_count": 2, "assigned_gate": "Exit 1 (West)", "assigned_group": "Group A", "checked_in": 1, "created_at": "2026-10-18 19:30:00", "checked_in_at": "2026-10-18 19:45:00"},
                {"id": 2, "reg_code": "REG-D4E5F6", "primary_name": "Anita Verma", "mobile": "9812345678", "age": 29, "group_count": 3, "assigned_gate": "Exit 2 (North)", "assigned_group": "Group B", "checked_in": 1, "created_at": "2026-10-18 19:40:00", "checked_in_at": "2026-10-18 20:00:00"},
                {"id": 3, "reg_code": "REG-7G8H9I", "primary_name": "Sunil Patel", "mobile": "9823456789", "age": 42, "group_count": 4, "assigned_gate": "Exit 3 (East)", "assigned_group": "Group C", "checked_in": 0, "created_at": "2026-10-18 20:10:00", "checked_in_at": None}
            ],
            "members_map": {
                1: [{"member_name": "Pooja Kumar", "member_age": 31, "member_mobile": "9876543211"}],
                2: [{"member_name": "Aarav Verma", "member_age": 6, "member_mobile": ""}, {"member_name": "Ravi Verma", "member_age": 32, "member_mobile": "9812345679"}],
                3: [{"member_name": "Geeta Patel", "member_age": 39, "member_mobile": ""}, {"member_name": "Karan Patel", "member_age": 14, "member_mobile": ""}, {"member_name": "Diya Patel", "member_age": 10, "member_mobile": ""}]
            }
        }),
        ("verify.html", "verify.html", {
            "is_valid": True,
            "tamper_reason": None,
            "reg": {
                "reg_code": "DEMO-SAMPLE-8899",
                "primary_name": "Demo Visitor",
                "mobile": "9876543210",
                "assigned_gate": "Exit 1 (West)",
                "assigned_group": "Group A",
                "group_count": 2,
                "checked_in": 0,
                "created_at": "2026-10-18 20:00:00"
            },
            "members": [{"member_name": "Accompanying Guest", "member_age": 28}],
            "gate_info": GATES_CONFIG[0]
        }),
        ("entrance_poster.html", "entrance_poster.html", {
            "entrance_url": "https://ritesh926306-rgb.github.io/crowd-management-v2/",
            "entrance_qr": ""
        })
    ]

    for template_name, output_filename, context in pages:
        template = env.get_template(template_name)
        content = template.render(**context)
        output_path = os.path.join(DIST_DIR, output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[EXPORT] Rendered {template_name} -> {output_filename}")

    # Add .nojekyll so GitHub Pages does not ignore files
    with open(os.path.join(DIST_DIR, ".nojekyll"), "w") as f:
        f.write("")

    print(f"[SUCCESS] Frontend bundled successfully to {DIST_DIR}")

if __name__ == "__main__":
    build()
