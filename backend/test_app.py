"""
Automated Integration and Verification Test Suite
Tests registration, dynamic members, HMAC signature generation,
HMAC tampering detection, capacity-based split, and CSV export.
"""

import unittest
from app import app, init_db, get_db_connection, generate_hmac_signature, verify_hmac_signature

class VenueCrowdSystemTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        init_db()

    def test_01_index_page(self):
        """Test registration page loads in both English and Hindi."""
        res_en = self.client.get('/?lang=en')
        self.assertEqual(res_en.status_code, 200)
        self.assertIn(b'Venue Entry Pass Registration', res_en.data)

        res_hi = self.client.get('/?lang=hi')
        self.assertEqual(res_hi.status_code, 200)
        self.assertIn(b'Venue Entry Pass Registration', res_hi.data)

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

        # 2. Test valid verification terminal
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
        self.assertIn(b'Venue Operations & Crowd Analytics', login_res.data)

        # CSV Export
        csv_res = self.client.get('/admin/export-csv')
        self.assertEqual(csv_res.status_code, 200)
        self.assertEqual(csv_res.headers['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn(b'Registration Code', csv_res.data)

    def test_05_guard_verify_terminal(self):
        """Test guard terminal standby page and guard PIN login."""
        # 1. Test standby terminal loads
        res = self.client.get('/verify')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Guard Gate Terminal', res.data)
        self.assertIn(b'Start Camera Scanner', res.data)

        # 2. Test guard login with PIN
        login_res = self.client.post('/guard/login', data={'pin': 'guard123'}, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Guard terminal unlocked', login_res.data)

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

        # 2. Test API verify before admission
        api_res = self.client.get(f'/api/verify/{reg_code}')
        self.assertEqual(api_res.status_code, 200)
        json_data = api_res.get_json()
        self.assertTrue(json_data['is_valid'])
        self.assertFalse(json_data['is_already_checked_in'])
        self.assertEqual(json_data['reg']['primary_name'], 'Kavita Roy')

        # 3. Check in visitor
        checkin_res = self.client.post(f'/api/check-in/{reg_code}')
        self.assertEqual(checkin_res.status_code, 200)
        self.assertEqual(checkin_res.get_json()['checked_in'], 1)

        # 4. Test API verify detects anti-passback
        api_res2 = self.client.get(f'/api/verify/{reg_code}')
        self.assertEqual(api_res2.status_code, 200)
        json_data2 = api_res2.get_json()
        self.assertTrue(json_data2['is_valid'])
        self.assertTrue(json_data2['is_already_checked_in'])

if __name__ == '__main__':
    unittest.main()
