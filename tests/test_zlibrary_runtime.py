import tempfile
import unittest
from pathlib import Path

from zlibrary_runtime import (
    ZLibraryAuth,
    create_zlibrary_client,
    find_pending_result_files,
    load_zlibrary_auth,
)


class ZlibraryRuntimeTests(unittest.TestCase):
    def test_load_zlibrary_auth_exchanges_email_password_for_tokens(self):
        captured_kwargs = {}

        class FakeClient:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

            def getProfile(self):
                return {"user": {"id": 42, "remix_userkey": "abc-token"}}

        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "ZLIBRARY_EMAIL=test@example.com\n"
                "ZLIBRARY_PASSWORD=secret123\n",
                encoding="utf-8",
            )

            auth = load_zlibrary_auth(env_path=env_path, client_factory=FakeClient)

        self.assertEqual(captured_kwargs, {"email": "test@example.com", "password": "secret123"})
        self.assertEqual(auth, ZLibraryAuth(remix_userid="42", remix_userkey="abc-token"))

    def test_load_zlibrary_auth_uses_existing_tokens_without_login(self):
        class FailingClient:
            def __init__(self, **kwargs):
                raise AssertionError("client_factory should not be called when remix tokens exist")

        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "ZLIBRARY_REMIX_USERID=12345\n"
                "ZLIBRARY_REMIX_USERKEY=token-value\n",
                encoding="utf-8",
            )

            auth = load_zlibrary_auth(env_path=env_path, client_factory=FailingClient)

        self.assertEqual(auth, ZLibraryAuth(remix_userid="12345", remix_userkey="token-value"))

    def test_create_zlibrary_client_requires_auth_and_passes_tokens(self):
        captured_kwargs = {}

        class FakeClient:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        with self.assertRaises(ValueError):
            create_zlibrary_client(ZLibraryAuth(), client_factory=FakeClient)

        client = create_zlibrary_client(
            ZLibraryAuth(remix_userid="123", remix_userkey="token"),
            client_factory=FakeClient,
        )

        self.assertIsInstance(client, FakeClient)
        self.assertEqual(captured_kwargs, {"remix_userid": "123", "remix_userkey": "token"})

    def test_find_pending_result_files_filters_processed_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            first = root_dir / "A" / "处理结果.txt"
            second = root_dir / "B" / "处理结果.txt"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_text("", encoding="utf-8")
            second.write_text("", encoding="utf-8")

            pending_files = find_pending_result_files(root_dir, processed_files={str(first)})

        self.assertEqual(pending_files, [second])


if __name__ == "__main__":
    unittest.main()
