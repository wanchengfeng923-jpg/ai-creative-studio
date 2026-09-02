from __future__ import annotations

import unittest
import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from creative_studio.auth import (
    AuthDataError,
    hash_password,
    new_token,
    normalize_username,
    token_digest,
    validate_password,
    verify_password,
    AuthError,
    AuthRateLimitError,
    AuthService,
)
from creative_studio.repository import StudioRepository
from creative_studio.auth_cli import main as auth_cli_main


class AuthHelpersTests(unittest.TestCase):
    def test_normalize_username_lowercases_and_accepts_allowed_characters(self):
        self.assertEqual(normalize_username("User.Name-1"), "user.name-1")

    def test_normalize_username_rejects_invalid_length_and_characters(self):
        for value in ("ab", "a" * 65, "bad name", "ümlaut"):
            with self.assertRaises(AuthDataError):
                normalize_username(value)

    def test_normalize_username_rejects_surrounding_whitespace(self):
        with self.assertRaises(AuthDataError):
            normalize_username(" user ")

    def test_validate_password_requires_minimum_length_and_string_value(self):
        validate_password("0123456789ab")
        for value in ("short", "", None):  # type: ignore[arg-type]
            with self.assertRaises(AuthDataError):
                validate_password(value)  # type: ignore[arg-type]

    def test_hash_password_round_trips_and_uses_encoded_format(self):
        encoded = hash_password("correct horse battery staple")
        self.assertTrue(verify_password("correct horse battery staple", encoded))
        self.assertFalse(verify_password("wrong horse battery staple", encoded))
        parts = encoded.split("$")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "pbkdf2_sha256")
        self.assertTrue(parts[1].isdigit())
        self.assertTrue(parts[2])
        self.assertTrue(parts[3])

    def test_verify_password_rejects_unknown_format_without_raising(self):
        self.assertFalse(verify_password("password", "unexpected-format"))

    def test_verify_password_rejects_unexpected_iteration_count_without_hashing(self):
        encoded = "pbkdf2_sha256$1$YWJjZGVmZ2hpamtsbW5vcA$YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXo"
        with patch("creative_studio.auth.hashlib.pbkdf2_hmac") as pbkdf2_hmac:
            self.assertFalse(verify_password("correct horse battery staple", encoded))
        pbkdf2_hmac.assert_not_called()

    def test_new_token_is_url_safe_and_unique(self):
        tokens = {new_token() for _ in range(32)}
        self.assertEqual(len(tokens), 32)
        for token in tokens:
            self.assertRegex(token, r"^[A-Za-z0-9_-]+$")

    def test_token_digest_is_stable_sha256_hex(self):
        token = new_token()
        digest = token_digest(token)
        self.assertEqual(len(digest), 64)
        self.assertRegex(digest, r"^[0-9a-f]+$")
        self.assertEqual(digest, token_digest(token))


class AuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = StudioRepository(Path(self.tmp.name) / "auth.db")
        self.service = AuthService(self.repo)
        self.admin = self.service.init_admin("admin", "correct horse battery staple")

    def tearDown(self):
        self.tmp.cleanup()

    def test_login_success_and_session_csrf(self):
        result = self.service.login("ADMIN", "correct horse battery staple", "127.0.0.1", "test")
        self.assertEqual(result.user["role"], "admin")
        context = self.service.authenticate_session(result.session_token, result.csrf_token)
        self.assertIsNotNone(context)
        self.assertEqual(context.user["username"], "admin")
        self.service.logout(result.session_token, self.admin["id"])
        self.assertIsNone(self.service.authenticate_session(result.session_token))

    def test_failed_logins_are_generic_and_lock(self):
        for _ in range(4):
            with self.assertRaises(AuthError) as raised:
                self.service.login("admin", "wrong password value", "ip")
            self.assertEqual(str(raised.exception), "用户名或密码错误")
        with self.assertRaises(AuthRateLimitError):
            self.service.login("admin", "wrong password value", "ip")

    def test_admin_can_manage_users_but_not_admin_role(self):
        user = self.service.create_user(self.admin["id"], "member", "member password value")
        self.assertEqual(user["role"], "user")
        with self.assertRaises(AuthError):
            self.service.set_user_active(self.admin["id"], self.admin["id"], False)
        self.service.set_user_active(self.admin["id"], user["id"], False)
        with self.assertRaises(AuthError):
            self.service.login("member", "member password value", "ip")

    def test_cli_reads_stdin_without_printing_password(self):
        db = Path(self.tmp.name) / "cli.db"
        with patch("sys.stdin", io.StringIO("cli password value\n")), patch("sys.stdout", new_callable=io.StringIO) as out:
            code = auth_cli_main(["init-admin", "--username", "cliadmin", "--password-stdin", "--database", str(db)])
        self.assertEqual(code, 0)
        self.assertNotIn("cli password value", out.getvalue())
        with patch("sys.stdin", io.StringIO("cli password value\n")):
            self.assertNotEqual(auth_cli_main(["init-admin", "--username", "cliadmin", "--password-stdin", "--database", str(db)]), 0)


if __name__ == "__main__":
    unittest.main()
