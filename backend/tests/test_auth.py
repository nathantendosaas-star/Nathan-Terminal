import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.auth.router import hash_password

class PasswordAuthTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"APP_PASSWORD_HASH": hash_password("a-long-test-password-123"), "AUTH_SECRET_KEY": "test-secret-key-that-is-at-least-32-chars"})
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def test_login_returns_valid_token_and_protects_api(self):
        denied = self.client.get("/api/v1/overview")
        self.assertEqual(denied.status_code, 401)
        login = self.client.post("/api/v1/auth/login", json={"password": "a-long-test-password-123"})
        self.assertEqual(login.status_code, 200)
        token = login.json()["access_token"]
        allowed = self.client.get("/api/v1/overview", headers={"Authorization": "Bearer " + token})
        self.assertEqual(allowed.status_code, 200)
        status = self.client.get("/api/v1/auth/status", headers={"Authorization": "Bearer " + token})
        self.assertTrue(status.json()["authenticated"])

    def test_wrong_password_is_rejected(self):
        response = self.client.post("/api/v1/auth/login", json={"password": "wrong-password"})
        self.assertEqual(response.status_code, 401)

    def test_tampered_token_is_rejected(self):
        response = self.client.get("/api/v1/overview", headers={"Authorization": "Bearer invalid.token"})
        self.assertEqual(response.status_code, 401)

if __name__ == "__main__":
    unittest.main()
