"""
VenueGuard Phase 9 - Master Upgrade Integration Test Suite
Validates fast visitor registration with optional address, unique Visitor ID generation,
4-status QR verification engine (GREEN, RED, ORANGE, GREY),
Admin event configuration management, visitor cancel/delete actions,
and guard account control APIs.

Uses an isolated temporary SQLite database for each test run to avoid
interference with the development database.
"""

import unittest
import json
import os
import tempfile
import shutil
import app as app_module
from app import app, init_db, get_db_connection, _set_setting


class VenueGuardPhase9TestCase(unittest.TestCase):
    def setUp(self):
        # Create a fresh isolated temporary database for each test
        self._test_db_dir = tempfile.mkdtemp(prefix="vg_test_")
        self._test_db_path = os.path.join(self._test_db_dir, "test_venue_crowd.db")

        # Override SQLITE_PATH in app module to use isolated test DB
        self._original_sqlite_path = app_module.SQLITE_PATH
        app_module.SQLITE_PATH = self._test_db_path

        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

        # Initialize fresh database schema
        init_db()
        from app import set_guard_password
        set_guard_password('guard123')
        _set_setting("emergency_mode", "0")
        _set_setting("is_registration_active", "1")
        _set_setting("event_status", "ACTIVE")

    def tearDown(self):
        # Restore original SQLITE_PATH
        app_module.SQLITE_PATH = self._original_sqlite_path
        # Remove temp directory
        try:
            shutil.rmtree(self._test_db_dir, ignore_errors=True)
        except Exception:
            pass

    def test_fast_registration_optional_address(self):
        """Test registration without providing address (address is optional)."""
        data = {
            'language': 'en',
            'primary_name': 'Rohan Sharma',
            'mobile': '9876543299',
            'age': '26',
            'group_count': '1',
            'address': ''  # Address is optional
        }
        res = self.client.post('/register', data=data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Rohan Sharma', res.data)
        self.assertIn(b'VG-VIS-', res.data)
        self.assertIn(b'OFFICIAL DIGITAL VISITOR ID PASS', res.data)

    def test_four_status_verification_engine(self):
        """Test GREEN, ORANGE, GREY, and RED verification engine responses."""
        # 1. Register visitor
        data = {
            'language': 'en',
            'primary_name': 'Devika Rao',
            'mobile': '9822334455',
            'age': '30',
            'group_count': '2',
            'address': 'MG Road'
        }
        reg_res = self.client.post('/register', data=data, follow_redirects=False)
        self.assertEqual(reg_res.status_code, 302, "Registration should redirect to pass page")
        location = reg_res.headers.get('Location', '')
        self.assertIn('/pass/', location, f"Expected redirect to /pass/REG-xxx, got: {location}")
        reg_code = location.split('/')[-1]

        # Authenticate guard
        self.client.post('/guard/login', data={'pin': 'guard123'})

        # STATUS 1: GREEN (Valid Registration)
        v1 = self.client.get(f'/api/verify/{reg_code}').get_json()
        self.assertEqual(v1['result_color'], 'GREEN')
        self.assertEqual(v1['status'], 'VALID')
        self.assertTrue(v1['is_valid'])
        self.assertFalse(v1['is_already_checked_in'])
        self.assertIn('VG-VIS-', v1['reg']['visitor_id'])

        # Check-in visitor
        ci_res = self.client.post(f'/api/check-in/{reg_code}').get_json()
        self.assertTrue(ci_res['success'])

        # STATUS 2: ORANGE (Already Scanned / Duplicate Detection)
        v2 = self.client.get(f'/api/verify/{reg_code}').get_json()
        self.assertEqual(v2['result_color'], 'ORANGE')
        self.assertEqual(v2['status'], 'ALREADY_SCANNED')
        self.assertTrue(v2['is_already_checked_in'])

        # STATUS 3: GREY (Cancelled Registration)
        # Cancel registration directly in database
        conn = get_db_connection()
        conn.cursor().execute("UPDATE registrations SET status = 'CANCELLED' WHERE reg_code = ?", (reg_code,))
        conn.commit()
        conn.close()

        v3 = self.client.get(f'/api/verify/{reg_code}').get_json()
        self.assertEqual(v3['result_color'], 'GREY')
        self.assertEqual(v3['status'], 'CANCELLED')
        self.assertFalse(v3['is_valid'])

        # STATUS 4: RED (Fake / Non-existent QR)
        v4 = self.client.get('/api/verify/FAKE-QR-NONEXISTENT').get_json()
        self.assertEqual(v4['result_color'], 'RED')
        self.assertEqual(v4['status'], 'INVALID')
        self.assertFalse(v4['is_valid'])

    def test_admin_event_management_and_visitor_controls(self):
        """Test Admin event configuration update and visitor cancel/delete actions."""
        # Authenticate Admin
        with self.client.session_transaction() as sess:
            sess['is_admin'] = True

        # 1. Update event details
        update_data = {
            'event_title': 'Grand City Festival 2026',
            'event_date': '2026-12-15',
            'event_time': '10:00 AM - 08:00 PM',
            'event_location': 'Central Stadium Complex',
            'max_capacity': '2500',
            'expected_population': '5000',
            'registration_open': '1'
        }
        res_ev = self.client.post('/api/admin/event/update', data=update_data, follow_redirects=True)
        self.assertEqual(res_ev.status_code, 200)

        # Verify reflected in public crowd status / event config
        from app import get_event_config
        cfg = get_event_config()
        self.assertEqual(cfg['event_name'], 'Grand City Festival 2026')
        self.assertEqual(cfg['event_venue'], 'Central Stadium Complex')
        self.assertEqual(cfg['event_capacity'], '2500')

        # 2. Register visitor and test cancel API
        reg_data = {
            'language': 'en',
            'primary_name': 'Vikram Malhotra',
            'mobile': '9844556677',
            'age': '45',
            'group_count': '1'
        }
        self.client.post('/register', data=reg_data)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM registrations WHERE mobile = '9844556677'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        vis_id = row['id']
        conn.close()

        # Admin cancels registration
        cancel_res = self.client.post(f'/api/admin/visitors/{vis_id}/cancel', follow_redirects=True)
        self.assertEqual(cancel_res.status_code, 200)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM registrations WHERE id = ?", (vis_id,))
        row_after = cursor.fetchone()
        self.assertEqual(row_after['status'], 'CANCELLED')
        conn.close()

    def test_admin_guard_accounts_management(self):
        """Test Admin creation and management of multi-guard accounts."""
        with self.client.session_transaction() as sess:
            sess['is_admin'] = True

        # Create new guard account (using 'gate_id' field — should be accepted as alias)
        guard_data = {
            'username': 'guard_gate_north',
            'full_name': 'Inspector Verma',
            'gate_id': 'exit_a',
            'password': 'GatePassword2026!'
        }
        create_res = self.client.post('/api/admin/guard-accounts/create', data=guard_data, follow_redirects=True)
        self.assertEqual(create_res.status_code, 200, f"Create guard failed: {create_res.get_data(as_text=True)}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM guard_accounts WHERE username = 'guard_gate_north'")
        guard = cursor.fetchone()
        self.assertIsNotNone(guard)
        self.assertEqual(guard['full_name'], 'Inspector Verma')
        conn.close()


if __name__ == '__main__':
    unittest.main()
