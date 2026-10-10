"""데이터 변환 > 컬럼: 컬럼명 변경, 데이터 타입 캐스팅, 컬럼 선택, 컬럼 제거, 컬럼명 표준화.
순수 함수로 두어 DB/엔진에 의존하지 않는다. rows: AssetRow.data 목록, columns: Asset.schema_def 컬럼 목록."""
import re
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.domains.pipelines.nodes.base import Rows, Transform, TransformResult
from app.domains.pipelines.nodes.registry import register


def _require_columns(columns: Sequence[str], used: Sequence[str]) -> None:
    known = set(columns)
    for name in used:
        if name not in known:
            raise ValueError(f"unknown column: {name}")


# --- 컬럼명 변경 (Rename Columns) ---

def rename_columns(rows: Rows, columns: Sequence[str], params: "RenameColumns.Params") -> tuple[list[str], Rows]:
    _require_columns(columns, list(params.mapping))
    new_columns = [params.mapping.get(c, c) for c in columns]
    new_rows = [{params.mapping.get(k, k): v for k, v in row.items()} for row in rows]
    return new_columns, new_rows


@register
class RenameColumns(Transform):
    name = "rename_columns"

    class Params(BaseModel):
        mapping: dict[str, str] = Field(min_length=1)  # {기존 컬럼명: 새 컬럼명}

    def run(self, inputs, params: "RenameColumns.Params") -> TransformResult:
        columns, rows = inputs[0]
        new_columns, new_rows = rename_columns(rows, columns, params)
        return TransformResult(columns=new_columns, rows=new_rows)


# --- 데이터 타입 캐스팅 (Cast Type) ---

_CASTERS = {
    "string": str,
    "integer": int,
    "float": float,
    "boolean": lambda v: str(v).strip().lower() in {"true", "1", "y", "yes"},
}


def cast_type(rows: Rows, columns: Sequence[str], params: "CastType.Params") -> Rows:
    _require_columns(columns, list(params.types))
    result: Rows = []
    for i, row in enumerate(rows):
        new_row = dict(row)
        for col, type_name in params.types.items():
            value = new_row.get(col)
            if value is None:
                continue
            try:
                new_row[col] = _CASTERS[type_name](value)
            except (ValueError, TypeError) as e:
                raise ValueError(f"row {i}: cannot cast column '{col}' to {type_name}: {value!r}") from e
        result.append(new_row)
    return result


@register
class CastType(Transform):
    name = "cast_type"

    class Params(BaseModel):
        types: dict[str, Literal["string", "integer", "float", "boolean"]] = Field(min_length=1)

    def run(self, inputs, params: "CastType.Params") -> TransformResult:
        columns, rows = inputs[0]
        return TransformResult(columns=columns, rows=cast_type(rows, columns, params))


# --- 컬럼 선택 (Select Columns) ---

def select_columns(rows: Rows, columns: Sequence[str], params: "SelectColumns.Params") -> tuple[list[str], Rows]:
    _require_columns(columns, params.columns)
    new_rows = [{c: row.get(c) for c in params.columns} for row in rows]
    return list(params.columns), new_rows


@register
class SelectColumns(Transform):
    name = "select_columns"

    class Params(BaseModel):
        columns: list[str] = Field(min_length=1)

    def run(self, inputs, params: "SelectColumns.Params") -> TransformResult:
        columns, rows = inputs[0]
        new_columns, new_rows = select_columns(rows, columns, params)
        return TransformResult(columns=new_columns, rows=new_rows)


# --- 컬럼 제거 (Drop Columns) ---

def drop_columns(rows: Rows, columns: Sequence[str], params: "DropColumns.Params") -> tuple[list[str], Rows]:
    _require_columns(columns, params.columns)
    keep = [c for c in columns if c not in set(params.columns)]
    new_rows = [{c: row.get(c) for c in keep} for row in rows]
    return keep, new_rows


@register
class DropColumns(Transform):
    name = "drop_columns"

    class Params(BaseModel):
        columns: list[str] = Field(min_length=1)

    def run(self, inputs, params: "DropColumns.Params") -> TransformResult:
        columns, rows = inputs[0]
        new_columns, new_rows = drop_columns(rows, columns, params)
        return TransformResult(columns=new_columns, rows=new_rows)


# --- 컬럼명 표준화 (Normalize Column Names) ---
# ex. "입찰 금액" -> "입찰금액" (공백/특수문자 제거, 한글은 유지)

_NORMALIZE_PATTERN = re.compile(r"[^\w가-힣]+")


def _normalize_name(name: str) -> str:
    return _NORMALIZE_PATTERN.sub("", name.strip())


def normalize_column_names(rows: Rows, columns: Sequence[str]) -> tuple[list[str], Rows]:
    mapping = {c: _normalize_name(c) for c in columns}
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("normalization produced duplicate column names")
    new_columns = [mapping[c] for c in columns]
    new_rows = [{mapping[k]: v for k, v in row.items()} for row in rows]
    return new_columns, new_rows


@register
class NormalizeColumnNames(Transform):
    name = "normalize_column_names"

    class Params(BaseModel):
        pass

    def run(self, inputs, params: "NormalizeColumnNames.Params") -> TransformResult:
        columns, rows = inputs[0]
        new_columns, new_rows = normalize_column_names(rows, columns)
        return TransformResult(columns=new_columns, rows=new_rows)
