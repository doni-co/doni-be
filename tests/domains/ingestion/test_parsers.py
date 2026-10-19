"""DB/스토리지 없이 도는 테스트: 정형 파일 파서(csv, tsv, json)."""
import pytest

from app.domains.ingestion.parsers import InvalidFileContent, parse_tabular


def csv_bytes(text: str, encoding: str = "utf-8") -> bytes:
    return text.encode(encoding)


# ------------------------------------------------------------------ CSV


def test_csv_basic_values_stay_strings():
    columns, rows = parse_tabular(csv_bytes("이름,금액\n홍길동,100\n"), "csv")
    assert columns == ["이름", "금액"]
    assert rows == [{"이름": "홍길동", "금액": "100"}]  # 숫자 변환은 cast_type 몫


def test_csv_cp949_korean_excel_export():
    columns, rows = parse_tabular(csv_bytes("이름,금액\n홍길동,100\n", "cp949"), "csv")
    assert columns == ["이름", "금액"]
    assert rows[0]["이름"] == "홍길동"


def test_csv_utf8_bom_is_removed():
    columns, _ = parse_tabular(b"\xef\xbb\xbf" + csv_bytes("a,b\n1,2\n"), "csv")
    assert columns == ["a", "b"]  # 첫 컬럼 이름에 BOM이 붙지 않는다


def test_csv_empty_cell_becomes_none():
    _, rows = parse_tabular(csv_bytes("a,b\n,x\n"), "csv")
    assert rows == [{"a": None, "b": "x"}]


def test_csv_values_are_not_cleaned():
    _, rows = parse_tabular(csv_bytes('금액,메모\n"₩1,200,000원", 앞 공백\n'), "csv")
    assert rows == [{"금액": "₩1,200,000원", "메모": " 앞 공백"}]  # 정리는 clean_text 몫


def test_csv_whitespace_only_cell_is_kept():
    _, rows = parse_tabular(csv_bytes("a,b\n  ,x\n"), "csv")
    assert rows[0]["a"] == "  "


def test_csv_header_cleanup_empty_and_duplicate():
    columns, rows = parse_tabular(csv_bytes(" a ,,a\n1,2,3\n"), "csv")
    assert columns == ["a", "column_2", "a_2"]
    assert rows == [{"a": "1", "column_2": "2", "a_2": "3"}]


def test_csv_three_duplicates():
    columns, _ = parse_tabular(csv_bytes("a,a,a\n1,2,3\n"), "csv")
    assert columns == ["a", "a_2", "a_3"]


def test_csv_short_row_is_padded_with_none():
    _, rows = parse_tabular(csv_bytes("a,b\n1\n"), "csv")
    assert rows == [{"a": "1", "b": None}]


def test_csv_long_row_is_an_error_with_line_number():
    with pytest.raises(InvalidFileContent, match=r"row 2: 3 fields, header has 2"):
        parse_tabular(csv_bytes("a,b\n1,2,3\n"), "csv")


def test_csv_blank_lines_are_skipped():
    _, rows = parse_tabular(csv_bytes("\na,b\n\n1,2\n , \n3,4\n"), "csv")
    assert [r["a"] for r in rows] == ["1", "3"]


def test_csv_quoted_field_with_newline_and_comma():
    _, rows = parse_tabular(csv_bytes('a,b\n"x,\ny",2\n'), "csv")
    assert rows == [{"a": "x,\ny", "b": "2"}]


def test_csv_header_only_has_columns_and_no_rows():
    columns, rows = parse_tabular(csv_bytes("a,b\n"), "csv")
    assert (columns, rows) == (["a", "b"], [])


@pytest.mark.parametrize("data", [b"", b"\n\n", b"  ,  \n"])
def test_csv_empty_file_is_an_error(data):
    with pytest.raises(InvalidFileContent, match="empty file"):
        parse_tabular(data, "csv")


def test_csv_undecodable_bytes_are_an_error():
    with pytest.raises(InvalidFileContent, match="cannot decode"):
        parse_tabular(b"\xff\xfe\x00\xff", "csv")


def test_csv_row_order_is_file_order():
    _, rows = parse_tabular(csv_bytes("n\n3\n1\n2\n"), "csv")
    assert [r["n"] for r in rows] == ["3", "1", "2"]


# ------------------------------------------------------------------ TSV


def test_tsv():
    columns, rows = parse_tabular(csv_bytes("a\tb\n1,5\t2\n"), "tsv")
    assert columns == ["a", "b"]
    assert rows == [{"a": "1,5", "b": "2"}]  # 쉼표는 구분자가 아니다


def test_extension_may_have_dot_and_uppercase():
    assert parse_tabular(csv_bytes("a\n1\n"), ".CSV")[0] == ["a"]


# ------------------------------------------------------------------ JSON


def test_json_array_of_objects_with_key_union():
    columns, rows = parse_tabular(b'[{"a":1},{"b":{"x":2}}]', "json")
    assert columns == ["a", "b"]
    assert rows == [{"a": 1, "b": None}, {"a": None, "b": {"x": 2}}]


def test_json_keeps_types_and_nested_values():
    _, rows = parse_tabular(b'[{"n":1.5,"ok":true,"tags":["a","b"],"none":null}]', "json")
    assert rows == [{"n": 1.5, "ok": True, "tags": ["a", "b"], "none": None}]


def test_json_utf8_bom_and_korean():
    columns, rows = parse_tabular(b"\xef\xbb\xbf" + '[{"이름":"홍길동"}]'.encode(), "json")
    assert (columns, rows) == (["이름"], [{"이름": "홍길동"}])


def test_json_empty_array_is_allowed():
    assert parse_tabular(b"[]", "json") == ([], [])


@pytest.mark.parametrize("data", [b'{"a":1}', b"[1,2,3]", b'[{"a":1}, 2]', b'"text"'])
def test_json_must_be_array_of_objects(data):
    with pytest.raises(InvalidFileContent, match="array of objects"):
        parse_tabular(data, "json")


def test_json_syntax_error():
    with pytest.raises(InvalidFileContent, match="invalid json"):
        parse_tabular(b"[{", "json")


def test_unsupported_extension_is_a_programming_error():
    with pytest.raises(ValueError, match="unsupported"):
        parse_tabular(b"x", "xlsx")
