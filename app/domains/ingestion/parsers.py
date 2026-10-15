"""순수 함수: 업로드한 정형 파일(csv, tsv, json)을 (컬럼 목록, 행 목록)으로 읽는다.
DB, 네트워크에 의존하지 않는다. 결과는 assets.service.save_rows에 그대로 넘긴다.

값은 가공하지 않는다. 정리와 타입 변환은 정제 노드(clean_text, cast_type 등)의 몫이다.
- CSV/TSV: 값은 문자열 그대로. 단 빈 칸("")은 None (cast_type이 None만 건너뛰기 때문)
- JSON: 최상위가 객체 배열이어야 하고, 값은 JSON 타입 그대로 (중첩 객체/배열 포함)
"""
import csv
import io
import json
from typing import Any

PARSEABLE_EXT = {"csv", "tsv", "json"}


class InvalidFileContent(ValueError):
    """파일은 받았지만 내용을 표로 읽을 수 없다."""


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp949"):  # cp949: 한글 엑셀의 "CSV로 저장" 기본 인코딩
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise InvalidFileContent("cannot decode file (tried utf-8, cp949)")


def _clean_headers(raw: list[str]) -> list[str]:
    """앞뒤 공백 제거, 빈 이름은 column_{위치}, 중복은 이름_2, 이름_3 ..."""
    headers: list[str] = []
    seen: set[str] = set()
    for position, cell in enumerate(raw, start=1):
        base = cell.strip() or f"column_{position}"
        name, n = base, 2
        while name in seen:
            name = f"{base}_{n}"
            n += 1
        seen.add(name)
        headers.append(name)
    return headers


def _is_blank(row: list[str]) -> bool:
    return not any(cell.strip() for cell in row)


def _parse_delimited(data: bytes, delimiter: str) -> tuple[list[str], list[dict[str, Any]]]:
    reader = csv.reader(io.StringIO(_decode(data)), delimiter=delimiter)
    try:
        header_row = next((row for row in reader if not _is_blank(row)), None)
        if header_row is None:
            raise InvalidFileContent("empty file")
        columns = _clean_headers(header_row)
        rows: list[dict[str, Any]] = []
        for row in reader:
            if _is_blank(row):
                continue
            if len(row) > len(columns):
                raise InvalidFileContent(f"row {reader.line_num}: {len(row)} fields, header has {len(columns)}")
            values = [(row[i] if i < len(row) else None) for i in range(len(columns))]
            rows.append({col: (None if value == "" else value) for col, value in zip(columns, values, strict=True)})
    except csv.Error as e:
        raise InvalidFileContent(f"invalid csv: {e}") from e
    return columns, rows


def _parse_json(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        parsed = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise InvalidFileContent(f"invalid json: {e}") from e
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise InvalidFileContent("json must be an array of objects")
    columns = list(dict.fromkeys(key for item in parsed for key in item))  # 등장 순서대로 키의 합집합
    return columns, [{col: item.get(col) for col in columns} for item in parsed]


def parse_tabular(data: bytes, ext: str) -> tuple[list[str], list[dict[str, Any]]]:
    """ext: "csv" | "tsv" | "json" (점 없이)."""
    ext = ext.lower().lstrip(".")
    if ext == "csv":
        return _parse_delimited(data, ",")
    if ext == "tsv":
        return _parse_delimited(data, "\t")
    if ext == "json":
        return _parse_json(data)
    raise ValueError(f"unsupported tabular extension: {ext}")
