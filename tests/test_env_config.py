import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class EnvConfigTests(unittest.TestCase):
    def test_loads_email_and_password_from_project_env(self):
        module_path = REPO_ROOT / "env_config.py"
        self.assertTrue(module_path.exists(), "env_config.py should exist")

        module = load_module("env_config", module_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "ZLIBRARY_EMAIL=test@example.com\n"
                "ZLIBRARY_PASSWORD=secret123\n",
                encoding="utf-8",
            )

            config = module.load_zlibrary_env(env_path)

        self.assertEqual(config["email"], "test@example.com")
        self.assertEqual(config["password"], "secret123")
        self.assertEqual(config["remix_userid"], "")
        self.assertEqual(config["remix_userkey"], "")

    def test_loads_remix_tokens_from_project_env(self):
        module_path = REPO_ROOT / "env_config.py"
        self.assertTrue(module_path.exists(), "env_config.py should exist")

        module = load_module("env_config", module_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "ZLIBRARY_REMIX_USERID=12345\n"
                "ZLIBRARY_REMIX_USERKEY=token-value\n",
                encoding="utf-8",
            )

            config = module.load_zlibrary_env(env_path)

        self.assertEqual(config["email"], "")
        self.assertEqual(config["password"], "")
        self.assertEqual(config["remix_userid"], "12345")
        self.assertEqual(config["remix_userkey"], "token-value")


if __name__ == "__main__":
    unittest.main()
