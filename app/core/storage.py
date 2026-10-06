"""원천 파일 저장소 접근. 지금은 로컬/NAS 마운트, 나중에 S3/MinIO로 교체 가능.
도메인 코드는 이 함수들을 통해서만 파일에 접근한다 (경로를 직접 열지 않는다)."""
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings

_ROOT = Path(settings.storage_root)


def _resolve(key: str) -> Path:
    p = (_ROOT / key).resolve()
    if not p.is_relative_to(_ROOT.resolve()):  # path traversal 방지
        raise ValueError("invalid storage key")
    return p


def save(key: str, fileobj: BinaryIO) -> str:
    p = _resolve(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("wb") as f:
        while chunk := fileobj.read(1024 * 1024):
            f.write(chunk)
    return key


def open_file(key: str) -> BinaryIO:
    return _resolve(key).open("rb")


def exists(key: str) -> bool:
    return _resolve(key).exists()
