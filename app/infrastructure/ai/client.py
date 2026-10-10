"""AI 서버 호출 경계. transform(특히 '이미지에서 텍스트 추출' 등)은 이 함수를 통해서만 AI 서버와 통신한다."""
import httpx

from app.core.config import settings


async def extract_text_from_image(image_url: str) -> str:
    """Garage presigned URL을 AI 서버에 넘기고, LLM이 추출한 텍스트를 받는다."""
    async with httpx.AsyncClient(base_url=settings.ai_server_url, timeout=120) as client:
        resp = await client.post("/extract-text", json={"image_url": image_url})
        resp.raise_for_status()
        return resp.json()["text"]


async def generate_column(rows: list[dict], prompt: str, column_name: str) -> list[dict]:
    """행 단위 데이터를 AI 서버로 보내고, column_name 컬럼이 추가된 결과를 받는다."""
    async with httpx.AsyncClient(base_url=settings.ai_server_url, timeout=60) as client:
        resp = await client.post(
            "/generate-column", json={"rows": rows, "prompt": prompt, "column_name": column_name}
        )
        resp.raise_for_status()
        return resp.json()["rows"]
