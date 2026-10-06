"""AI 서버 호출 경계. transform 코드는 이 함수를 통해서만 AI 서버와 통신한다."""
import httpx

from app.core.config import settings


async def generate_column(dataset_rows: list[dict], prompt: str, column_name: str) -> list[dict]:
    """행 단위 데이터를 AI 서버로 보내고, column_name 컬럼이 추가된 결과를 받는다."""
    async with httpx.AsyncClient(base_url=settings.ai_server_url, timeout=60) as client:
        resp = await client.post(
            "/generate-column",
            json={"rows": dataset_rows, "prompt": prompt, "column_name": column_name},
        )
        resp.raise_for_status()
        return resp.json()["rows"]
