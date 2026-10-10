"""데이터 변환 > 값 정리: 값 통일(Map Values), 문자 정리(Regex Replace), 필터(Filter).

변환 로직은 엔진(pandas/polars/DuckDB 등)에 의존하지 않는 순수 함수로 두었다.
    rows: list[dict]  (행 목록),  columns: 컬럼명 목록 (Asset.schema_def의 키)
입력을 변경하지 않고 새 리스트를 반환하므로, 같은 입력 + 같은 params면 항상 같은 결과다.
오류는 전부 ValueError이고, use_cases/execute_node.py가 str(e)를 NodeRun.error에 기록한다.

(팀원이 cleanup_ops.py로 구현한 로직을 새 nodes/base.py의 동기 Transform.run() 인터페이스에
맞춰 연결했다. 순수 함수 본문은 원안 그대로이고, run()만 load/save 없이 바로 결과를 반환하도록
완성했다.)
"""
from collections.abc import Sequence
from typing import Any, Literal

import re2
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domains.pipelines.nodes.base import Rows, Transform, TransformResult
from app.domains.pipelines.nodes.registry import register


def _require_columns(columns: Sequence[str], used: Sequence[str]) -> None:
    known = set(columns)
    for name in used:
        if name not in known:
            raise ValueError(f"unknown column: {name}")


# ---------------------------------------------------------------------------
# 값 통일 (Map Values)
# ---------------------------------------------------------------------------

def _match_key(value: str, trim: bool, ignore_case: bool) -> str:
    if trim:
        value = value.strip()
    if ignore_case:
        value = value.casefold()
    return value


def map_values(rows: Rows, columns: Sequence[str], params: "MapValues.Params") -> Rows:
    _require_columns(columns, list(params.mappings))
    lookups = {
        col: {_match_key(k, params.trim, params.ignore_case): v for k, v in mapping.items()}
        for col, mapping in params.mappings.items()
    }
    result: Rows = []
    for row in rows:
        new_row = dict(row)
        for col, lookup in lookups.items():
            value = new_row.get(col)
            if isinstance(value, str):  # None/비문자열은 그대로 둔다. 매핑은 원래 값 기준 1회만 조회(연쇄 없음).
                new_row[col] = lookup.get(_match_key(value, params.trim, params.ignore_case), value)
        result.append(new_row)
    return result


@register
class MapValues(Transform):
    name = "map_values"

    class Params(BaseModel):
        mappings: dict[str, dict[str, str]] = Field(min_length=1)  # {컬럼명: {원래값: 새값}}
        ignore_case: bool = False  # 비교에만 적용, 값 자체는 바꾸지 않는다
        trim: bool = False         # 비교 시 앞뒤 공백 무시

        @model_validator(mode="after")
        def _validate(self) -> "MapValues.Params":
            for col, mapping in self.mappings.items():
                if not mapping:
                    raise ValueError(f"mapping for column '{col}' is empty")
                seen: dict[str, str] = {}
                for key, new in mapping.items():
                    norm = _match_key(key, self.trim, self.ignore_case)
                    if norm in seen and seen[norm] != new:
                        raise ValueError(
                            f"column '{col}': '{key}' collides with another key after normalization "
                            f"but maps to a different value"
                        )
                    seen[norm] = new
            return self

    def run(self, inputs, params: "MapValues.Params") -> TransformResult:
        columns, rows = inputs[0]
        return TransformResult(columns=columns, rows=map_values(rows, columns, params))


# ---------------------------------------------------------------------------
# 문자 정리 (Regex Replace)
# ---------------------------------------------------------------------------

def regex_replace(rows: Rows, columns: Sequence[str], params: "RegexReplace.Params") -> Rows:
    _require_columns(columns, params.columns)
    compiled = re2.compile(params.pattern)
    replacement = params.replacement
    result: Rows = []
    for i, row in enumerate(rows):
        new_row = dict(row)
        for col in params.columns:
            value = new_row.get(col)
            if value is None:
                continue
            if not isinstance(value, str):
                raise ValueError(  # noqa: TRY004 - 모든 오류를 ValueError로 통일 (모듈 docstring 참고)
                    f"row {i}: column '{col}' is not text ({type(value).__name__}); "
                    "regex_replace only supports text columns"
                )
            new_row[col] = compiled.sub(lambda _m: replacement, value)  # 치환 문자열은 리터럴로 취급
        result.append(new_row)
    return result


@register
class RegexReplace(Transform):
    name = "regex_replace"

    class Params(BaseModel):
        columns: list[str] = Field(min_length=1)
        pattern: str = Field(min_length=1, max_length=200)
        replacement: str = ""

        @field_validator("pattern")
        @classmethod
        def _check_pattern(cls, v: str) -> str:
            try:
                re2.compile(v)
            except re2.error as e:
                raise ValueError(
                    f"invalid or unsupported pattern (RE2: lookaround/backreference not allowed): {e}"
                ) from None
            return v

    def run(self, inputs, params: "RegexReplace.Params") -> TransformResult:
        columns, rows = inputs[0]
        return TransformResult(columns=columns, rows=regex_replace(rows, columns, params))


# ---------------------------------------------------------------------------
# 필터 (Filter)
# ---------------------------------------------------------------------------

Op = Literal[
    "is_null", "is_not_null", "eq", "ne", "gt", "gte", "lt", "lte",
    "in", "not_in", "contains", "starts_with", "ends_with",
]
_NULL_OPS = {"is_null", "is_not_null"}
_STRING_OPS = {"contains", "starts_with", "ends_with"}
_MAX_DEPTH = 3         # Params = 1단계
_MAX_CONDITIONS = 50


class Condition(BaseModel):
    model_config = {"extra": "forbid"}

    column: str
    op: Op
    value: Any = None
    treat_empty_string_as_null: bool = False  # is_null / is_not_null 에서만 허용

    @model_validator(mode="after")
    def _validate(self) -> "Condition":
        if self.op in _NULL_OPS:
            if self.value is not None:
                raise ValueError(f"op '{self.op}' does not take a value")
        else:
            if self.value is None:
                raise ValueError(f"op '{self.op}' requires a value")
            if self.treat_empty_string_as_null:
                raise ValueError("treat_empty_string_as_null is only allowed with is_null / is_not_null")
        if self.op in ("in", "not_in") and not (isinstance(self.value, list) and self.value):
            raise ValueError(f"op '{self.op}' requires a non-empty list")
        if self.op in _STRING_OPS and not isinstance(self.value, str):
            raise ValueError(f"op '{self.op}' requires a string value")
        return self


class ConditionGroup(BaseModel):
    model_config = {"extra": "forbid"}

    match: Literal["all", "any"] = "all"
    conditions: list["Condition | ConditionGroup"] = Field(min_length=1)


ConditionGroup.model_rebuild()


def _walk(items: Sequence["Condition | ConditionGroup"], depth: int):
    """리프 Condition과 그 깊이를 순회한다."""
    for item in items:
        if isinstance(item, ConditionGroup):
            yield from _walk(item.conditions, depth + 1)
        else:
            yield item, depth


def _kind(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def _comparable(actual: Any, expected: Any, column: str, row_index: int, op: str) -> None:
    if _kind(actual) != _kind(expected):
        raise ValueError(
            f"row {row_index}: column '{column}' ({_kind(actual)}) cannot be compared "
            f"with {_kind(expected)} using '{op}'; cast the column type first"
        )


def _eval_condition(cond: Condition, row: dict[str, Any], row_index: int) -> bool:
    value = row.get(cond.column)
    op = cond.op
    if op in _NULL_OPS:
        is_null = value is None or (cond.treat_empty_string_as_null and value == "")
        return is_null if op == "is_null" else not is_null
    if value is None:  # SQL과 동일: null은 어떤 비교도 만족하지 않는다 (ne / not_in 포함)
        return False
    if op in _STRING_OPS:
        if not isinstance(value, str):
            raise ValueError(f"row {row_index}: column '{cond.column}' is not text for '{op}'")
        if op == "contains":
            return cond.value in value
        return value.startswith(cond.value) if op == "starts_with" else value.endswith(cond.value)
    if op in ("in", "not_in"):
        for item in cond.value:
            _comparable(value, item, cond.column, row_index, op)
        found = value in cond.value
        return found if op == "in" else not found
    _comparable(value, cond.value, cond.column, row_index, op)
    if op == "eq":
        return value == cond.value
    if op == "ne":
        return value != cond.value
    if op == "gt":
        return value > cond.value
    if op == "gte":
        return value >= cond.value
    if op == "lt":
        return value < cond.value
    return value <= cond.value  # lte


def _eval_items(match: str, items: Sequence["Condition | ConditionGroup"], row: dict[str, Any], i: int) -> bool:
    # 단락 평가를 하지 않는다: 타입 오류가 행 순서/값에 따라 가려지지 않게 모든 조건을 평가한다.
    results = [
        _eval_items(item.match, item.conditions, row, i) if isinstance(item, ConditionGroup)
        else _eval_condition(item, row, i)
        for item in items
    ]
    return all(results) if match == "all" else any(results)


def filter_rows(rows: Rows, columns: Sequence[str], params: "Filter.Params") -> Rows:
    _require_columns(columns, [c.column for c, _ in _walk(params.conditions, 1)])
    keep = params.mode == "keep"
    return [
        dict(row) for i, row in enumerate(rows)
        if _eval_items(params.match, params.conditions, row, i) == keep
    ]


@register
class Filter(Transform):
    name = "filter"

    class Params(BaseModel):
        mode: Literal["keep", "drop"] = "keep"      # keep: 조건을 만족하는 행만 남김 / drop: 만족하는 행 제거
        match: Literal["all", "any"] = "all"
        conditions: list[Condition | ConditionGroup] = Field(min_length=1)

        @model_validator(mode="after")
        def _validate(self) -> "Filter.Params":
            leaves = list(_walk(self.conditions, 1))
            if len(leaves) > _MAX_CONDITIONS:
                raise ValueError(f"too many conditions (max {_MAX_CONDITIONS})")
            if any(depth > _MAX_DEPTH for _, depth in leaves):
                raise ValueError(f"condition groups nested too deeply (max depth {_MAX_DEPTH})")
            return self

    def run(self, inputs, params: "Filter.Params") -> TransformResult:
        columns, rows = inputs[0]
        return TransformResult(columns=columns, rows=filter_rows(rows, columns, params))
