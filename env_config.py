from pathlib import Path


ENV_FILE = Path(__file__).resolve().parent / ".env"


def _parse_env_line(line: str):
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None, None

    if stripped.startswith("export "):
        stripped = stripped[7:].strip()

    if "=" not in stripped:
        return None, None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()

    if value and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]

    return key, value


def load_zlibrary_env(env_path: Path | None = None) -> dict[str, str]:
    """Load Z-Library credentials from a project-local .env file."""
    env_path = env_path or ENV_FILE
    config = {
        "email": "",
        "password": "",
        "remix_userid": "",
        "remix_userkey": "",
    }

    if not env_path.exists():
        return config

    with env_path.open("r", encoding="utf-8") as env_file:
        for line in env_file:
            key, value = _parse_env_line(line)
            if not key:
                continue

            if key == "ZLIBRARY_EMAIL":
                config["email"] = value
            elif key == "ZLIBRARY_PASSWORD":
                config["password"] = value
            elif key == "ZLIBRARY_REMIX_USERID":
                config["remix_userid"] = value
            elif key == "ZLIBRARY_REMIX_USERKEY":
                config["remix_userkey"] = value

    return config
