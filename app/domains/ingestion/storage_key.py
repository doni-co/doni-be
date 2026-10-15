"""순수 함수: 업로드 파일의 저장 키와 표시 이름을 만든다. DB, 네트워크, 파일 시스템에 의존하지 않는다.

[파일]의 데이터는 절대 갱신하지 않는다. 같은 이름을 다시 올리면 새 파일로 저장한다.
    저장 키(내부):  report.pdf -> uploads/{owner_id}/report_v1.pdf, 다시 올리면 report_v2.pdf
                    archive.tar.gz -> uploads/{owner_id}/archive.tar_v1.gz, README -> README_v1
    표시 이름(사용자): report.pdf, 다시 올리면 "report (2).pdf", 그다음 "report (3).pdf"
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


def build_display_name(filename: str, version: int) -> str:
    """사용자에게 보이는 이름. 처음(1)은 그대로, 같은 이름의 두 번째부터 "이름 (2).확장자"."""
    if version < 1:
        raise ValueError("version must be >= 1")
    name = safe_filename(filename)
    if version == 1:
        return name
    stem, ext = _split_ext(name)
    return f"{stem} ({version}){ext}"


def build_storage_key(owner_id: int, filename: str, version: int) -> str:
    if version < 1:
        raise ValueError("version must be >= 1")
    stem, ext = _split_ext(safe_filename(filename))
    return f"uploads/{owner_id}/{stem}_v{version}{ext}"
