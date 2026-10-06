from pydantic import BaseModel

from app.domains.pipelines.transforms.base import Transform, TransformContext, TransformResult
from app.domains.pipelines.transforms.registry import register


@register
class Join(Transform):
    name = "join"
    input_kinds = ("dataset", "dataset")
    output_kind = "dataset"

    class Params(BaseModel):
        left_key: str
        right_key: str
        how: str = "inner"

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO
