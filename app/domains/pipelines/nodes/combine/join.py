"""데이터 결합 (Join)."""
from typing import Literal

from pydantic import BaseModel

from app.domains.pipelines.nodes.base import Rows, Transform, TransformResult
from app.domains.pipelines.nodes.registry import register


def join_rows(
    left_columns: list[str], left_rows: Rows,
    right_columns: list[str], right_rows: Rows,
    left_key: str, right_key: str, how: Literal["inner", "left"],
) -> tuple[list[str], Rows]:
    if left_key not in left_columns:
        raise ValueError(f"unknown left column: {left_key}")
    if right_key not in right_columns:
        raise ValueError(f"unknown right column: {right_key}")

    right_index: dict[object, list[dict]] = {}
    for row in right_rows:
        right_index.setdefault(row.get(right_key), []).append(row)

    merged_columns = list(dict.fromkeys([*left_columns, *right_columns]))
    result: Rows = []
    for left_row in left_rows:
        matches = right_index.get(left_row.get(left_key), [])
        if matches:
            for right_row in matches:
                result.append({**right_row, **left_row})  # 왼쪽 값이 우선
        elif how == "left":
            result.append({**{c: None for c in right_columns}, **left_row})
    return merged_columns, result


@register
class Join(Transform):
    name = "join"
    input_count = 2

    class Params(BaseModel):
        left_key: str
        right_key: str
        how: Literal["inner", "left"] = "inner"

    def run(self, inputs, params: "Join.Params") -> TransformResult:
        (left_columns, left_rows), (right_columns, right_rows) = inputs[0], inputs[1]
        columns, rows = join_rows(left_columns, left_rows, right_columns, right_rows,
                                   params.left_key, params.right_key, params.how)
        return TransformResult(columns=columns, rows=rows)
