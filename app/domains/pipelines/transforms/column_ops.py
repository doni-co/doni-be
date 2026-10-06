"""데이터 변환 > 컬럼: 컬럼명 통일, 데이터 타입 통일, 컬럼 선택, 컬럼 제거, 컬럼명 표준화."""
from pydantic import BaseModel

from app.domains.pipelines.transforms.base import Transform, TransformContext, TransformResult
from app.domains.pipelines.transforms.registry import register


@register
class UnifyColumnName(Transform):
    name = "unify_column_name"
    input_kinds = ("dataset",)
    output_kind = "dataset"

    class Params(BaseModel):
        mapping: dict[str, str]  # {기존 컬럼명: 새 컬럼명}

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO


@register
class UnifyColumnType(Transform):
    name = "unify_column_type"
    input_kinds = ("dataset",)
    output_kind = "dataset"

    class Params(BaseModel):
        types: dict[str, str]  # {컬럼명: 타입}

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO


@register
class SelectColumns(Transform):
    name = "select_columns"
    input_kinds = ("dataset",)
    output_kind = "dataset"

    class Params(BaseModel):
        columns: list[str]

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO


@register
class RemoveColumns(Transform):
    name = "remove_columns"
    input_kinds = ("dataset",)
    output_kind = "dataset"

    class Params(BaseModel):
        columns: list[str]

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO


@register
class StandardizeColumnName(Transform):
    name = "standardize_column_name"
    input_kinds = ("dataset",)
    output_kind = "dataset"

    class Params(BaseModel):
        pass

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO
