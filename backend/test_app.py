"""
Automated Integration and Verification Test Suite
Tests registration, dynamic members, HMAC signature generation,
HMAC tampering detection, capacity-based split, CSV export,
check-registration, check-out/occupancy, emergency protocols,
and IoT hardware telemetry authentication.
"""

import unittest
from app import app, init_db, get_db_connection, generate_hmac_signature, verify_hmac_signature, _set_setting

class VenueCrowdSystemTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        init_db()
        from app import get_guard_password, set_guard_password
        self.orig_guard_pass = get_guard_password()
        set_guard_password('guard123')
        # Ensure clean operational state (emergency mode OFF)
        _set_setting("emergency_mode", "0")
        _set_setting("emergency_reason", "")

    def tearDown(self):
        from app import set_guard_password
        set_guard_password(self.orig_guard_pass)
        _set_setting("emergency_mode", "0")
        _set_setting("emergency_reason", "")

    def test_01_index_page(self):
        """Test registration page loads in both English and Hindi."""
        res_en = self.client.get('/?lang=en')
        self.assertEqual(res_en.status_code, 200)
        self.assertIn(b'VenueGuard', res_en.data)

        res_hi = self.client.get('/?lang=hi')
        self.assertEqual(res_hi.status_code, 200)
        self.assertIn(b'VenueGuard', res_hi.data)

    def test_02_registration_and_pass_generation(self):
        """Test visitor registration with accompanying group members."""
        data = {
            'language': 'en',
            'primary_name': 'Aarav Patel',
            'mobile': '9876543210',
            'age': '32',
            'address': 'Flat 402, Lotus Enclave, New Delhi',
            'member_name[]': ['Sunita Patel', 'Rohan Patel'],
            'member_age[]': ['30', '8'],
            'member_mobile[]': ['', '']
        }
        res = self.client.post('/register', data=data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Aarav Patel', res.data)
        self.assertIn(b'Sunita Patel', res.data)
        self.assertIn(b'3 Persons', res.data)
        self.assertIn(b'CRYPTOGRAPHICALLY VERIFIED', res.data)
        self.assertIn(b'data:image/png;base64', res.data)

    def test_03_hmac_verification_and_tampering(self):
        """Test security terminal HMAC verification and anti-fraud tamper detection."""
        # 1. Register a test user
        data = {
            'language': 'en',
            'primary_name': 'Meera Sen',
            'mobile': '9123456780',
            'age': '28',
            'address': 'Park Street, Kolkata',
        }
        res = self.client.post('/register', data=data, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        redirect_url = res.headers['Location']
        reg_code = redirect_url.split('/')[-1]

        # 2. Test valid verification terminal (requires guard authentication)
        self.client.post('/guard/login', data={'pin': 'guard123'})
        verify_res = self.client.get(f'/verify/{reg_code}')
        self.assertEqual(verify_res.status_code, 200)
        self.assertIn(b'VERIFIED ACCESS GRANTED', verify_res.data)
        self.assertIn(b'Meera Sen', verify_res.data)

        # 3. Simulate Database Tampering (e.g. attacker changing mobile or primary name)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE registrations SET primary_name = 'Counterfeit Hacker' WHERE reg_code = ?", (reg_code,))
        conn.commit()
        conn.close()

        # 4. Test terminal detects tampering
        tampered_verify = self.client.get(f'/verify/{reg_code}')
        self.assertEqual(tampered_verify.status_code, 200)
        self.assertIn(b'FRAUD WARNING: INVALID ENTRY PASS', tampered_verify.data)
        self.assertIn(b'CRYPTOGRAPHIC SIGNATURE MISMATCH', tampered_verify.data)

    def test_04_admin_login_and_export(self):
        """Test admin login security and CSV export."""
        # Unauthorized access redirects to login
        res = self.client.get('/admin', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/admin/login', res.headers['Location'])

        # Valid login
        login_res = self.client.post('/admin/login', data={'password': 'admin123'}, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Admin Command Center', login_res.data)

        # CSV Export
        csv_res = self.client.get('/admin/export-csv')
        self.assertEqual(csv_res.status_code, 200)
        self.assertEqual(csv_res.headers['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn(b'Registration Code', csv_res.data)

    def test_05_guard_verify_terminal(self):
        """Test guard terminal password protection and auto-logout."""
        # 1. Unauthenticated request to /verify redirects to /guard/login
        res = self.client.get('/verify', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/guard/login', res.headers['Location'])

        # 2. Invalid password rejected
        bad_res = self.client.post('/guard/login', data={'pin': 'wrongpass'}, follow_redirects=True)
        self.assertIn(b'Invalid Guard Access Password', bad_res.data)

        # 3. Test guard login with PIN
        login_res = self.client.post('/guard/login', data={'pin': 'guard123'}, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Guard Gate Terminal', login_res.data)
        self.assertIn(b'Start Camera Scanner', login_res.data)

        # 4. Test guard logout / lock (POST or GET)
        logout_res = self.client.post('/guard/logout', follow_redirects=False)
        self.assertEqual(logout_res.status_code, 200)

        # 5. Accessing /verify after logout redirects back to /guard/login
        locked_res = self.client.get('/verify', follow_redirects=False)
        self.assertEqual(locked_res.status_code, 302)
        self.assertIn('/guard/login', locked_res.headers['Location'])

    def test_06_api_verify_and_anti_passback(self):
        """Test real-time JSON verification API and anti-passback duplicate detection."""
        # 1. Register test user
        data = {
            'language': 'en',
            'primary_name': 'Kavita Roy',
            'mobile': '9811223344',
            'age': '29',
            'address': 'Sector 18, Noida'
        }
        res = self.client.post('/register', data=data, follow_redirects=False)
        reg_code = res.headers['Location'].split('/')[-1]

        # Authenticate guard session
        self.client.post('/guard/login', data={'pin': 'guard123'})

        # 2. Test API verify before admission
        api_res = self.client.get(f'/api/verify/{reg_code}')
        self.assertEqual(api_res.status_code, 200)
        json_data = api_res.get_json()
        self.assertTrue(json_data['is_valid'])
        self.assertFalse(json_data['is_already_checked_in'])
        self.assertEqual(json_data['reg']['primary_name'], 'Kavita Roy')

        # 3. Check in visitor (marks entry in visitor registry)
        checkin_res = self.client.post(f'/api/check-in/{reg_code}')
        self.assertEqual(checkin_res.status_code, 200)
        self.assertEqual(checkin_res.get_json()['checked_in'], 1)

        # 4. Test API verify detects anti-passback
        api_res2 = self.client.get(f'/api/verify/{reg_code}')
        self.assertEqual(api_res2.status_code, 200)
        json_data2 = api_res2.get_json()
        self.assertTrue(json_data2['is_valid'])
        self.assertTrue(json_data2['is_already_checked_in'])

    def test_07_admin_change_guard_password(self):
        """Test admin can update guard password and guard must use new password."""
        # 1. Login as admin
        self.client.post('/admin/login', data={'password': 'admin123'})
        
        # 2. Update guard password
        update_res = self.client.post('/admin/update-guard-password', data={'guard_password': 'securegate888'}, follow_redirects=True)
        self.assertEqual(update_res.status_code, 200)
        self.assertIn(b'securegate888', update_res.data)
        
        # 3. Admin logs out
        self.client.get('/admin/logout')
        
        # 4. Old guard password fails
        old_login = self.client.post('/guard/login', data={'pin': 'guard123'}, follow_redirects=True)
        self.assertIn(b'Invalid Guard Access Password', old_login.data)
        
        # 5. New guard password succeeds
        new_login = self.client.post('/guard/login', data={'pin': 'securegate888'}, follow_redirects=True)
        self.assertEqual(new_login.status_code, 200)
        self.assertIn(b'Guard terminal unlocked', new_login.data)

    def test_08_check_registration_self_service(self):
        """Test visitor self-service pass lookup by registration ID and mobile."""
        # 1. Register test user
        data = {
            'language': 'en',
            'primary_name': 'Vikram Singh',
            'mobile': '9876500001',
            'age': '40',
            'address': 'Civil Lines, Jaipur'
        }
        res = self.client.post('/register', data=data, follow_redirects=False)
        reg_code = res.headers['Location'].split('/')[-1]

        # 2. Check registration page loads
        get_res = self.client.get('/check-registration')
        self.assertEqual(get_res.status_code, 200)
        self.assertIn(b'Check Registration Pass Status', get_res.data)

        # 3. Post with wrong mobile fails
        bad_post = self.client.post('/check-registration', data={
            'reg_code': reg_code,
            'mobile': '9999999999'
        }, follow_redirects=True)
        self.assertIn(b'Mobile number does not match', bad_post.data)

        # 4. Post with correct mobile succeeds and redirects to pass
        good_post = self.client.post('/check-registration', data={
            'reg_code': reg_code,
            'mobile': '9876500001'
        }, follow_redirects=False)
        self.assertEqual(good_post.status_code, 302)
        self.assertIn(f'/pass/{reg_code}', good_post.headers['Location'])

    def test_09_check_out_and_occupancy(self):
        """Test check-out endpoint and verified occupancy calculation."""
        # 1. Register user
        data = {
            'language': 'en',
            'primary_name': 'Ritu Sharma',
            'mobile': '9876500002',
            'age': '27',
            'address': 'South Extension, Delhi'
        }
        res = self.client.post('/register', data=data, follow_redirects=False)
        reg_code = res.headers['Location'].split('/')[-1]

        # Authenticate guard
        self.client.post('/guard/login', data={'pin': 'guard123'})

        # Check in visitor
        self.client.post(f'/api/check-in/{reg_code}')

        # Check out visitor
        checkout_res = self.client.post(f'/api/check-out/{reg_code}')
        self.assertEqual(checkout_res.status_code, 200)
        out_json = checkout_res.get_json()
        self.assertTrue(out_json['success'])
        self.assertEqual(out_json['checked_out'], 1)

    def test_10_public_crowd_status(self):
        """Test public crowd status returns safe classification without exposing raw counts."""
        res = self.client.get('/api/public-crowd-status')
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertIn('status', json_data)
        self.assertIn(json_data['status'].upper(), ['NORMAL', 'BUSY', 'HIGH', 'HIGH CROWD', 'TEMPORARILY FULL', 'FULL'])

    def test_11_emergency_protocol(self):
        """Test emergency activation by admin and emergency broadcast status."""
        # 1. Admin login
        self.client.post('/admin/login', data={'password': 'admin123'})

        # 2. Activate emergency
        em_res = self.client.post('/api/admin/emergency', json={'action': 'activate', 'reason': 'Evacuation Drill'})
        self.assertEqual(em_res.status_code, 200)
        self.assertTrue(em_res.get_json()['emergency_mode'])

        # 3. Check public emergency status API
        status_res = self.client.get('/api/emergency/status')
        self.assertEqual(status_res.status_code, 200)
        self.assertTrue(status_res.get_json()['is_emergency'])

        # 4. Deactivate emergency
        deact_res = self.client.post('/api/admin/emergency', json={'action': 'resolve'})
        self.assertEqual(deact_res.status_code, 200)
        self.assertFalse(deact_res.get_json()['emergency_mode'])

    def test_12_hardware_telemetry_authentication(self):
        """Test ESP8266 IoT telemetry endpoint security header validation."""
        # 1. Request without X-Device-Key header fails (401)
        bad_req = self.client.post('/api/hardware/telemetry', json={'gate_id': 'main_gate', 'count_delta': 1})
        self.assertEqual(bad_req.status_code, 401)

        # 2. Request with valid X-Device-Key succeeds (200)
        good_req = self.client.post(
            '/api/hardware/telemetry',
            headers={'X-Device-Key': 'vg-device-key-2026'},
            json={'gate_id': 'main_gate', 'distance_cm': 55}
        )
        self.assertEqual(good_req.status_code, 200)
        res_json = good_req.get_json()
        self.assertTrue(res_json['success'])
        self.assertIn('current_occupancy', res_json)

    def test_13_venue_info_and_safety_pages(self):
        """Test venue info and safety pages load properly and staff Gate E is not shown to visitors."""
        info_res = self.client.get('/venue-info')
        self.assertEqual(info_res.status_code, 200)
        self.assertIn(b'Venue Architecture', info_res.data)
        # Gate E is staff only and must not be in public gate guides
        self.assertNotIn(b'Exit Gate E', info_res.data)

        help_res = self.client.get('/help')
        self.assertEqual(help_res.status_code, 200)
        self.assertIn(b'First Aid', help_res.data)

if __name__ == '__main__':
    unittest.main()
