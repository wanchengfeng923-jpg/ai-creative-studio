from __future__ import annotations

import unittest
from unittest.mock import patch

from creative_studio.auth import (
    AuthDataError,
    hash_password,
    new_token,
    normalize_username,
    token_digest,
    validate_password,
    verify_password,
)


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


if __name__ == "__main__":
    unittest.main()
