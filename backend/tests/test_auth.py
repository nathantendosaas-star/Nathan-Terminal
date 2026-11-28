import os, uuid, unittest, psycopg
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.auth.router import hash_password

class PasswordAuthTests(unittest.TestCase):
    def setUp(self):
        self.schema = "test_" + uuid.uuid4().hex
        self.env = patch.dict(os.environ, {"APP_PASSWORD_HASH": hash_password("a-long-test-password-123"), "AUTH_SECRET_KEY": "test-secret-key-that-is-at-least-32-chars", "DATABASE_SCHEMA": self.schema})
        self.env.start()
        self.client = TestClient(app)
    def tearDown(self):
        self.client.close(); self.env.stop()
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            conn.execute('DROP SCHEMA IF EXISTS "' + self.schema + '" CASCADE')
    def test_login_returns_valid_token_and_protects_api(self):
        self.assertEqual(self.client.get("/api/v1/overview").status_code,401)
        login=self.client.post("/api/v1/auth/login",json={"password":"a-long-test-password-123"})
        self.assertEqual(login.status_code,200); token=login.json()["access_token"]
        self.assertEqual(self.client.get("/api/v1/overview",headers={"Authorization":"Bearer "+token}).status_code,200)
        self.assertTrue(self.client.get("/api/v1/auth/status",headers={"Authorization":"Bearer "+token}).json()["authenticated"])
    def test_wrong_password_is_rejected(self):
        self.assertEqual(self.client.post("/api/v1/auth/login",json={"password":"wrong-password"}).status_code,401)
    def test_tampered_token_is_rejected(self):
        self.assertEqual(self.client.get("/api/v1/overview",headers={"Authorization":"Bearer invalid.token"}).status_code,401)
    def test_first_run_setup_hashes_password_and_generates_secret(self):
        self.env.stop()
        with patch.dict(os.environ,{"APP_PASSWORD_HASH":"","AUTH_SECRET_KEY":"","DATABASE_SCHEMA":self.schema}):
            status=self.client.get("/api/v1/auth/status").json()
            self.assertTrue(status["setup_required"])
            response=self.client.post("/api/v1/auth/setup",json={"password":"phone-first-password-123"})
            self.assertEqual(response.status_code,200)
            self.assertNotIn("password",response.json())
            self.assertEqual(self.client.get("/api/v1/overview",headers={"Authorization":"Bearer "+response.json()["access_token"]}).status_code,200)
            self.assertEqual(self.client.post("/api/v1/auth/setup",json={"password":"another-password-123"}).status_code,401)
            stored_hash=__import__("app.auth.router",fromlist=["get_setting"]).get_setting("auth_password_hash")
            self.assertTrue(stored_hash.startswith("scrypt$"))
            self.assertNotIn("phone-first-password-123",stored_hash)
            self.assertTrue(__import__("app.auth.router",fromlist=["get_setting"]).get_setting("auth_signing_secret"))
if __name__=="__main__": unittest.main()
