"""데이터 변환 > 정리: 데이터 표준화, 문자 정리, 필터."""
from pydantic import BaseModel

from app.domains.pipelines.transforms.base import Transform, TransformContext, TransformResult
from app.domains.pipelines.transforms.registry import register


@register
class StandardizeData(Transform):
    name = "standardize_data"
    input_kinds = ("dataset",)
    output_kind = "dataset"

    class Params(BaseModel):
        pass

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO


@register
class CleanText(Transform):
    name = "clean_text"
    input_kinds = ("dataset",)
    output_kind = "dataset"

    class Params(BaseModel):
        columns: list[str] = []

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO


@register
class Filter(Transform):
    name = "filter"
    input_kinds = ("dataset",)
    output_kind = "dataset"

    class Params(BaseModel):
        condition: str

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO
