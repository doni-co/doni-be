"""AI 사용: AI 서버로 데이터를 보내 새 컬럼을 생성한다. AI 서버 호출은 core.ai_client를 통해서만 한다."""
from pydantic import BaseModel

from app.core import ai_client
from app.domains.pipelines.transforms.base import Transform, TransformContext, TransformResult
from app.domains.pipelines.transforms.registry import register


@register
class LlmColumn(Transform):
    name = "llm_column"
    input_kinds = ("dataset",)
    output_kind = "dataset"

    class Params(BaseModel):
        prompt: str
        column_name: str

    async def run(self, inputs, params: "LlmColumn.Params", ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO: dataset 로드 -> ai_client.generate_column 호출 -> 결과 저장
