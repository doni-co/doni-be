"""AI 사용: AI 서버로 행 데이터를 보내 새 컬럼을 생성한다.
네트워크 I/O가 필요해서 순수 함수가 아니다 - infrastructure.ai.client를 통해서만 호출한다."""
from pydantic import BaseModel

from app.domains.pipelines.nodes.base import Transform, TransformResult
from app.domains.pipelines.nodes.registry import register
from app.infrastructure.ai import client as ai_client


@register
class LlmColumn(Transform):
    name = "llm_column"

    class Params(BaseModel):
        prompt: str
        column_name: str

    async def run(self, inputs, params: "LlmColumn.Params") -> TransformResult:
        """다른 노드들과 달리 네트워크 호출이 있어 코루틴을 반환한다.
        use_cases/execute_node.py가 결과가 awaitable이면 await하는 방식으로 양쪽을 다 처리한다."""
        columns, rows = inputs[0]
        new_rows = await ai_client.generate_column(rows, params.prompt, params.column_name)
        return TransformResult(columns=[*columns, params.column_name], rows=new_rows)
