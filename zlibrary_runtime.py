from dataclasses import dataclass
from pathlib import Path

from Zlibrary import Zlibrary
from env_config import load_zlibrary_env


@dataclass
class ZLibraryAuth:
    remix_userid: str = ""
    remix_userkey: str = ""


def load_zlibrary_auth(
    env_path: Path | None = None,
    client_factory=Zlibrary,
) -> ZLibraryAuth:
    env_path = env_path or Path(__file__).resolve().parent / ".env"
    zlibrary_account = load_zlibrary_env(env_path)

    if zlibrary_account.get("email") and zlibrary_account.get("password"):
        temp_client = client_factory(
            email=zlibrary_account["email"],
            password=zlibrary_account["password"],
        )
        profile = temp_client.getProfile()["user"]
        return ZLibraryAuth(
            remix_userid=str(profile["id"]),
            remix_userkey=profile["remix_userkey"],
        )

    return ZLibraryAuth(
        remix_userid=zlibrary_account.get("remix_userid", ""),
        remix_userkey=zlibrary_account.get("remix_userkey", ""),
    )


def create_zlibrary_client(auth: ZLibraryAuth, client_factory=Zlibrary):
    if not auth.remix_userid or not auth.remix_userkey:
        raise ValueError("缺少必要的认证信息：remix_userid 和 remix_userkey")

    return client_factory(
        remix_userid=auth.remix_userid,
        remix_userkey=auth.remix_userkey,
    )


def find_pending_result_files(root_dir: Path | str, processed_files: set[str] | list[str] | None = None) -> list[Path]:
    root_dir = Path(root_dir)
    processed_files = set(processed_files or [])
    result_files = sorted(root_dir.rglob("处理结果.txt"))
    return [result_file for result_file in result_files if str(result_file) not in processed_files]
