"""순수 함수: 업로드 파일의 저장 키를 만든다. DB, 네트워크, 파일 시스템에 의존하지 않는다.

같은 이름의 파일을 다시 올려도 원본이 덮어써지지 않도록 키에 버전 번호를 붙인다.
    report.pdf        -> uploads/{owner_id}/report_v1.pdf   (처음)
    report.pdf        -> uploads/{owner_id}/report_v2.pdf   (같은 이름을 다시 올림)
    archive.tar.gz    -> uploads/{owner_id}/archive.tar_v1.gz
    README            -> uploads/{owner_id}/README_v1
원본은 이후 재처리/추적에 쓰이므로 삭제하거나 덮어쓰지 않는다.
"""
import re


def safe_filename(filename: str) -> str:
    """클라이언트가 준 이름에서 경로를 떼고 마지막 이름만 남긴다 ("../a/b.csv", "C:\\x\\b.csv" -> "b.csv")."""
    name = re.split(r"[\\/]", filename)[-1].strip()
    if name in ("", ".", ".."):
        raise ValueError("invalid filename")
    return name


def _split_ext(name: str) -> tuple[str, str]:
    """마지막 확장자만 분리한다. 확장자가 없거나 점으로 시작하는 이름(.env)은 통째로 stem으로 본다."""
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem:
        return name, ""
    return stem, f".{ext}"


def build_storage_key(owner_id: int, filename: str, version: int) -> str:
    if version < 1:
        raise ValueError("version must be >= 1")
    stem, ext = _split_ext(safe_filename(filename))
    return f"uploads/{owner_id}/{stem}_v{version}{ext}"
