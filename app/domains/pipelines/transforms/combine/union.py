from pydantic import BaseModel

from app.domains.pipelines.transforms.base import Transform, TransformContext, TransformResult
from app.domains.pipelines.transforms.registry import register


@register
class Union(Transform):
    name = "union"
    input_kinds = ("dataset", "dataset")
    output_kind = "dataset"

    class Params(BaseModel):
        pass

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO
