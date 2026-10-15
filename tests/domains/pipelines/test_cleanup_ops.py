"""DB/엔진 없이 도는 순수 로직 테스트. cleanup_ops의 순수 함수와 Params 검증을 직접 검증한다."""
import copy
import json
import time

import pytest
from pydantic import ValidationError

from app.domains.pipelines.nodes import registry
from app.domains.pipelines.nodes.base import TransformResult
from app.domains.pipelines.nodes.transform.cleanup_ops import (
    CleanText,
    Filter,
    StandardizeData,
    clean_text,
    filter_rows,
    standardize_values,
)

COLS = ["id", "type", "amount", "name"]


def rows_of(*values, col="type"):
    return [{"id": i, col: v} for i, v in enumerate(values)]


# ---------------------------------------------------------------- registry

def test_registered():
    for name in ("standardize_data", "clean_text", "filter"):
        assert name in registry.all_names()


# ----------------------------------------------- run() = execute_node가 부르는 진입점

def test_run_wrappers_return_transform_result():
    """execute_node처럼 registry에서 클래스를 찾아 Params(**dict)로 만든 뒤 run([(columns, rows)], params)로 부른다."""
    cases = [
        ("standardize_data", {"mappings": {"type": {"Veh": "Vehicle"}}}, ["Vehicle", "Truck"]),
        ("clean_text", {"columns": ["type"], "pattern": "[aeiou]"}, ["Vhcl", "Trck"]),
        ("filter", {"conditions": [{"column": "type", "op": "eq", "value": "Truck"}]}, ["Truck"]),
    ]
    for name, raw_params, expected in cases:
        node_cls = registry.get(name)
        params = node_cls.Params(**raw_params)
        rows = rows_of("Veh", "Truck") if name != "clean_text" else rows_of("Vehicle", "Truck")
        result = node_cls().run([(COLS, rows)], params)
        assert isinstance(result, TransformResult)
        assert result.columns == COLS
        assert [r["type"] for r in result.rows] == expected


def test_run_does_not_change_columns_or_input():
    rows = rows_of("Veh")
    snapshot = copy.deepcopy(rows)
    cols = list(COLS)
    StandardizeData().run([(cols, rows)], StandardizeData.Params(mappings={"type": {"Veh": "Vehicle"}}))
    assert (cols, rows) == (COLS, snapshot)


def test_functions_work_on_json_round_tripped_rows():
    """AssetRow.data는 JSONB라 json을 거친 값(str/number/bool/null/list)만 들어온다."""
    rows = json.loads(json.dumps([
        {"id": 1, "type": "Veh", "amount": "₩1,200,000원", "name": None},
        {"id": 2, "type": "Truck", "amount": "₩300원", "name": "x"},
    ]))
    mapped = standardize_values(rows, COLS, StandardizeData.Params(mappings={"type": {"Veh": "Vehicle"}}))
    cleaned = clean_text(mapped, COLS, CleanText.Params(columns=["amount"], pattern="[₩,원]"))
    kept = filter_rows(cleaned, COLS, Filter.Params(conditions=[{"column": "name", "op": "is_not_null"}]))
    assert [r["type"] for r in cleaned] == ["Vehicle", "Truck"]
    assert [r["amount"] for r in cleaned] == ["1200000", "300"]
    assert [r["id"] for r in kept] == [2]


# ------------------------------------------------------- standardize_values

def sd(**kw):
    return StandardizeData.Params(**kw)


def test_standardize_maps_variants():
    rows = rows_of("Veh", "Vhc", "Vehicle", "Truck")
    out = standardize_values(rows, COLS, sd(mappings={"type": {"Veh": "Vehicle", "Vhc": "Vehicle"}}))
    assert [r["type"] for r in out] == ["Vehicle", "Vehicle", "Vehicle", "Truck"]  # 미매칭은 유지


def test_standardize_keeps_none_and_non_text():
    out = standardize_values(rows_of(None, 5), COLS, sd(mappings={"type": {"5": "x"}}))
    assert [r["type"] for r in out] == [None, 5]


def test_standardize_exact_match_by_default():
    out = standardize_values(rows_of("veh", " Veh"), COLS, sd(mappings={"type": {"Veh": "Vehicle"}}))
    assert [r["type"] for r in out] == ["veh", " Veh"]


def test_standardize_ignore_case_and_trim():
    params = sd(mappings={"type": {"Veh": "Vehicle"}}, ignore_case=True, trim=True)
    out = standardize_values(rows_of("veh", " VEH ", "Veh"), COLS, params)
    assert [r["type"] for r in out] == ["Vehicle"] * 3


def test_standardize_no_chaining():
    out = standardize_values(rows_of("A"), COLS, sd(mappings={"type": {"A": "B", "B": "C"}}))
    assert out[0]["type"] == "B"


def test_standardize_does_not_mutate_input():
    rows = rows_of("Veh")
    snapshot = copy.deepcopy(rows)
    standardize_values(rows, COLS, sd(mappings={"type": {"Veh": "Vehicle"}}))
    assert rows == snapshot


def test_standardize_is_idempotent():
    params = sd(mappings={"type": {"Veh": "Vehicle"}})
    once = standardize_values(rows_of("Veh"), COLS, params)
    assert standardize_values(once, COLS, params) == once


def test_standardize_collision_after_normalization_is_error():
    with pytest.raises(ValidationError):
        sd(mappings={"type": {"Veh": "A", "veh": "B"}}, ignore_case=True)


def test_standardize_same_target_collision_is_ok():
    sd(mappings={"type": {"Veh": "A", "veh": "A"}}, ignore_case=True)


def test_standardize_empty_mapping_is_error():
    with pytest.raises(ValidationError):
        sd(mappings={})
    with pytest.raises(ValidationError):
        sd(mappings={"type": {}})


def test_standardize_unknown_column_is_error_even_without_rows():
    with pytest.raises(ValueError, match="unknown column: nope"):
        standardize_values([], COLS, sd(mappings={"nope": {"a": "b"}}))


# --------------------------------------------------------------- clean_text

def ct(**kw):
    return CleanText.Params(**kw)


def test_clean_text_notion_example():
    out = clean_text(rows_of("₩1,200,000원", col="amount"), COLS, ct(columns=["amount"], pattern="[₩,원]"))
    assert out[0]["amount"] == "1200000"
    assert isinstance(out[0]["amount"], str)  # 숫자 변환은 UnifyColumnType 책임


def test_clean_text_replacement_is_literal():
    out = clean_text(rows_of("a-b", col="name"), COLS, ct(columns=["name"], pattern="-", replacement="\\1"))
    assert out[0]["name"] == "a\\1b"


def test_clean_text_skips_none():
    out = clean_text(rows_of(None, col="name"), COLS, ct(columns=["name"], pattern="x"))
    assert out[0]["name"] is None


def test_clean_text_non_text_value_is_error():
    with pytest.raises(ValueError, match="not text"):
        clean_text(rows_of(10, col="amount"), COLS, ct(columns=["amount"], pattern="0"))


def test_clean_text_requires_columns():
    with pytest.raises(ValidationError):
        ct(columns=[], pattern="x")
    with pytest.raises(ValidationError):
        CleanText.Params(pattern="x")  # 기본값 없음


def test_clean_text_pattern_limits():
    with pytest.raises(ValidationError):
        ct(columns=["name"], pattern="a" * 201)
    with pytest.raises(ValidationError):
        ct(columns=["name"], pattern="")


@pytest.mark.parametrize("pattern", [r"(?=a)b", r"(a)\1", "(unclosed"])
def test_clean_text_unsupported_or_invalid_pattern(pattern):
    with pytest.raises(ValidationError):
        ct(columns=["name"], pattern=pattern)


def test_clean_text_redos_pattern_finishes_fast():
    started = time.perf_counter()
    clean_text(rows_of("a" * 5000 + "!", col="name"), COLS, ct(columns=["name"], pattern=r"(a+)+$"))
    assert time.perf_counter() - started < 1


def test_clean_text_unknown_column_is_error():
    with pytest.raises(ValueError, match="unknown column"):
        clean_text([], COLS, ct(columns=["nope"], pattern="x"))


# -------------------------------------------------------------- filter_rows

def flt(*conditions, **kw):
    return Filter.Params(conditions=list(conditions), **kw)


def cond(column, op, value=None, **kw):
    return {"column": column, "op": op, "value": value, **kw}


def test_filter_palantir_scenario_not_null_with_empty_string():
    rows = [{"order_id": "A"}, {"order_id": ""}, {"order_id": None}, {"order_id": "B"}]
    cols = ["order_id"]
    params = flt({"column": "order_id", "op": "is_not_null", "treat_empty_string_as_null": True})
    assert [r["order_id"] for r in filter_rows(rows, cols, params)] == ["A", "B"]
    plain = flt({"column": "order_id", "op": "is_not_null"})
    assert [r["order_id"] for r in filter_rows(rows, cols, plain)] == ["A", "", "B"]


def test_filter_comparisons():
    rows = [{"id": i, "amount": a} for i, a in enumerate([1, 5, 10, None])]
    cols = COLS

    def ids(op, value):
        return [r["id"] for r in filter_rows(rows, cols, flt(cond("amount", op, value)))]

    assert ids("eq", 5) == [1]
    assert ids("ne", 5) == [0, 2]          # null 행은 ne에서도 제외
    assert ids("gt", 5) == [2]
    assert ids("gte", 5) == [1, 2]
    assert ids("lt", 5) == [0]
    assert ids("lte", 5) == [0, 1]
    assert ids("in", [1, 10]) == [0, 2]
    assert ids("not_in", [1, 10]) == [1]   # null 행은 not_in에서도 제외


def test_filter_int_float_mix_allowed():
    rows = [{"amount": 5}]
    assert filter_rows(rows, COLS, flt(cond("amount", "eq", 5.0))) == rows


def test_filter_string_ops():
    rows = rows_of("apple", "banana", None, col="name")
    contains = [r["name"] for r in filter_rows(rows, COLS, flt(cond("name", "contains", "an")))]
    starts = [r["name"] for r in filter_rows(rows, COLS, flt(cond("name", "starts_with", "ap")))]
    ends = [r["name"] for r in filter_rows(rows, COLS, flt(cond("name", "ends_with", "na")))]
    assert (contains, starts, ends) == (["banana"], ["apple"], ["banana"])


def test_filter_drop_mode_keeps_rows_where_condition_is_false_or_null():
    rows = [{"amount": 1}, {"amount": 10}, {"amount": None}]
    out = filter_rows(rows, COLS, flt(cond("amount", "gt", 5), mode="drop"))
    assert out == [{"amount": 1}, {"amount": None}]  # null 행은 조건이 False라서 남는다


def test_filter_all_vs_any():
    rows = [{"type": "a", "amount": 1}, {"type": "a", "amount": 9}, {"type": "b", "amount": 9}]
    both = [cond("type", "eq", "a"), cond("amount", "gt", 5)]
    assert filter_rows(rows, COLS, flt(*both, match="all")) == [rows[1]]
    assert filter_rows(rows, COLS, flt(*both, match="any")) == rows


def test_filter_nested_group():
    rows = [{"type": "a", "amount": 1}, {"type": "b", "amount": 9}, {"type": "c", "amount": 9}]
    params = flt(
        cond("amount", "gt", 5),
        {"match": "any", "conditions": [cond("type", "eq", "a"), cond("type", "eq", "b")]},
    )
    assert filter_rows(rows, COLS, params) == [rows[1]]


def test_filter_type_mismatch_is_error():
    with pytest.raises(ValueError, match="cast the column type first"):
        filter_rows([{"amount": "100"}], COLS, flt(cond("amount", "gt", 50)))


def test_filter_type_error_not_hidden_by_other_conditions():
    rows = [{"type": "x", "amount": "100"}]
    params = flt(cond("type", "eq", "y"), cond("amount", "gt", 50), match="all")
    with pytest.raises(ValueError):
        filter_rows(rows, COLS, params)


def test_filter_string_op_on_non_text_value_is_error():
    with pytest.raises(ValueError, match="not text"):
        filter_rows([{"name": 5}], COLS, flt(cond("name", "contains", "x")))


def test_filter_does_not_mutate_input():
    rows = [{"amount": 1}]
    snapshot = copy.deepcopy(rows)
    out = filter_rows(rows, COLS, flt(cond("amount", "eq", 1)))
    out[0]["amount"] = 99
    assert rows == snapshot


def test_filter_unknown_column_is_error_even_without_rows():
    with pytest.raises(ValueError, match="unknown column: nope"):
        filter_rows([], COLS, flt(cond("nope", "is_null")))


def test_filter_unknown_column_inside_group_is_error():
    group = {"conditions": [cond("nope", "is_null")]}
    with pytest.raises(ValueError, match="unknown column: nope"):
        filter_rows([], COLS, flt(group))


# ------------------------------------------------------ filter Params 검증

@pytest.mark.parametrize("bad", [
    cond("amount", "eq"),                                      # value 필수
    cond("amount", "is_null", 1),                              # value 금지
    cond("amount", "in", 5),                                   # list 필요
    cond("amount", "in", []),                                  # 비어있지 않은 list
    cond("name", "contains", 5),                               # str 필요
    cond("amount", "eq", 1, treat_empty_string_as_null=True),  # 옵션은 null 연산자 전용
    cond("amount", "regex", "x"),                              # 알 수 없는 연산자
])
def test_filter_invalid_condition(bad):
    with pytest.raises(ValidationError):
        flt(bad)


def test_filter_requires_conditions():
    with pytest.raises(ValidationError):
        flt()


def test_filter_depth_limit():
    leaf = cond("amount", "is_null")
    ok = {"conditions": [{"conditions": [leaf]}]}              # 리프 깊이 3
    flt(ok)
    too_deep = {"conditions": [{"conditions": [{"conditions": [leaf]}]}]}  # 리프 깊이 4
    with pytest.raises(ValidationError):
        flt(too_deep)


def test_filter_condition_count_limit():
    flt(*[cond("amount", "is_null")] * 50)
    with pytest.raises(ValidationError):
        flt(*[cond("amount", "is_null")] * 51)


def test_filter_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        flt({"column": "amount", "op": "is_null", "extra": 1})
    with pytest.raises(ValidationError):
        Filter.Params(condition="amount > 1")  # 구 스키마(문자열 식)는 더 이상 받지 않는다
