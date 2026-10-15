"""업로드 결과(parse_tabular)를 정제 노드가 그대로 이어받을 수 있는지 확인한다.
파이프라인에서는 source 노드의 (columns, rows)가 이후 노드의 입력이 된다."""
import pytest

from app.domains.ingestion.parsers import parse_tabular
from app.domains.pipelines.nodes.transform.cleanup_ops import (
    CleanText,
    Filter,
    StandardizeData,
    clean_text,
    filter_rows,
    standardize_values,
)
from app.domains.pipelines.nodes.transform.column_ops import (
    CastType,
    cast_type,
    normalize_column_names,
)
from app.domains.pipelines.nodes.transform.extract_ops import explode_array

BID_CSV = """입찰ID,입찰 금액,상태
A001,"₩1,200,000원",open
A002,,open
A003,"₩300,000원",closed
""".encode()


def test_csv_to_clean_cast_filter_normalize():
    columns, rows = parse_tabular(BID_CSV, "csv")
    assert [r["입찰 금액"] for r in rows] == ["₩1,200,000원", None, "₩300,000원"]

    rows = clean_text(rows, columns, CleanText.Params(columns=["입찰 금액"], pattern="[₩,원]"))
    assert [r["입찰 금액"] for r in rows] == ["1200000", None, "300000"]

    rows = cast_type(rows, columns, CastType.Params(types={"입찰 금액": "integer"}))  # 빈 칸이 None이라 실패하지 않는다
    assert [r["입찰 금액"] for r in rows] == [1200000, None, 300000]

    rows = filter_rows(rows, columns, Filter.Params(conditions=[{"column": "입찰 금액", "op": "gt", "value": 500000}]))
    assert [r["입찰ID"] for r in rows] == ["A001"]

    columns, rows = normalize_column_names(rows, columns)
    assert columns == ["입찰ID", "입찰금액", "상태"]
    assert rows == [{"입찰ID": "A001", "입찰금액": 1200000, "상태": "open"}]


def test_filter_on_text_column_without_cast_is_an_error():
    """숫자 비교 전에 cast_type이 필요하다 (필터의 타입 규칙)."""
    columns, rows = parse_tabular(BID_CSV, "csv")
    params = Filter.Params(conditions=[{"column": "입찰 금액", "op": "gt", "value": 500000}])
    with pytest.raises(ValueError, match="cast the column type first"):
        filter_rows(rows, columns, params)


def test_empty_cell_works_with_null_filters():
    columns, rows = parse_tabular(BID_CSV, "csv")
    kept = filter_rows(rows, columns, Filter.Params(conditions=[{"column": "입찰 금액", "op": "is_not_null"}]))
    assert [r["입찰ID"] for r in kept] == ["A001", "A003"]  # 옵션 없이도 빈 칸이 null로 취급된다


def test_standardize_values_on_uploaded_csv():
    columns, rows = parse_tabular(b"type\nVeh\nVhc\nTruck\n", "csv")
    params = StandardizeData.Params(mappings={"type": {"Veh": "Vehicle", "Vhc": "Vehicle"}})
    assert [r["type"] for r in standardize_values(rows, columns, params)] == ["Vehicle", "Vehicle", "Truck"]


def test_json_nested_array_goes_to_explode_array():
    columns, rows = parse_tabular(b'[{"id":1,"tags":["a","b"]},{"id":2,"tags":["c"]}]', "json")
    exploded = explode_array(rows, columns, "tags")
    assert [(r["id"], r["tags"]) for r in exploded] == [(1, "a"), (1, "b"), (2, "c")]
