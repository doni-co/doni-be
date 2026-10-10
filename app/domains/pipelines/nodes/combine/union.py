"""데이터 통합 (Union)."""
from pydantic import BaseModel

from app.domains.pipelines.nodes.base import Rows, Transform, TransformResult
from app.domains.pipelines.nodes.registry import register


def union_rows(left_columns: list[str], left_rows: Rows, right_columns: list[str], right_rows: Rows) -> tuple[list[str], Rows]:
    columns = list(dict.fromkeys([*left_columns, *right_columns]))
    rows = [{c: row.get(c) for c in columns} for row in (*left_rows, *right_rows)]
    return columns, rows


@register
class Union(Transform):
    name = "union"
    input_count = 2

    class Params(BaseModel):
        pass

    def run(self, inputs, params: "Union.Params") -> TransformResult:
        (left_columns, left_rows), (right_columns, right_rows) = inputs[0], inputs[1]
        columns, rows = union_rows(left_columns, left_rows, right_columns, right_rows)
        return TransformResult(columns=columns, rows=rows)
