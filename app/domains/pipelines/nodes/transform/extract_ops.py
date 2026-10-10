"""데이터 변환 > 추출: PDF/이미지에서 텍스트 추출, 엑셀에서 JSON 추출, 배열 펼치기,
위치 보존 배열 펼치기, 구조 필드 추출. MediaSet(비정형) -> Dataset(정형)으로 바꾸는 노드들.

PDF/이미지 추출은 AI 서버 호출(네트워크 I/O)이 필요해서 다른 노드들처럼 완전한 순수 함수로
둘 수 없다 - run()이 직접 infrastructure.ai.client를 호출한다. 그 외(배열/구조체 관련)는 순수 함수다.
"""
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field

from app.domains.pipelines.nodes.base import Rows, Transform, TransformResult
from app.domains.pipelines.nodes.registry import register
from app.infrastructure.ai import client as ai_client
from app.infrastructure.storage import garage


# --- PDF에서 텍스트 추출 ---
# 원본은 media_set Asset이므로 Transform.run()의 inputs 규약(columns, rows)과는 다르게,
# use_cases/execute_node.py가 media_set일 때는 원본 Asset의 storage_key를 직접 넘겨준다.

@register
class ExtractTextFromPdf(Transform):
    name = "extract_text_from_pdf"
    input_count = 1  # media_set Asset 1개

    class Params(BaseModel):
        pass

    async def run_media(self, storage_key: str, params: "ExtractTextFromPdf.Params") -> TransformResult:
        """media_set 입력 전용 실행 경로. base.Transform.run()과 시그니처가 다르므로
        use_cases/execute_node.py가 kind in {pdf, image} 추출 노드일 때 이쪽을 호출한다."""
        url = garage.presigned_url(storage_key)
        text = await ai_client.extract_text_from_image(url)  # PDF도 같은 AI 엔드포인트 사용 (서버가 내부 분기)
        return TransformResult(columns=["text"], rows=[{"text": text}])

    def run(self, inputs, params):
        raise NotImplementedError("media_set 입력은 run_media()를 사용한다")


# --- 이미지에서 텍스트 추출 ---

@register
class ExtractTextFromImage(Transform):
    name = "extract_text_from_image"
    input_count = 1

    class Params(BaseModel):
        pass

    async def run_media(self, storage_key: str, params: "ExtractTextFromImage.Params") -> TransformResult:
        url = garage.presigned_url(storage_key)
        text = await ai_client.extract_text_from_image(url)
        return TransformResult(columns=["text"], rows=[{"text": text}])

    def run(self, inputs, params):
        raise NotImplementedError("media_set 입력은 run_media()를 사용한다")


# --- 엑셀에서 JSON 추출 ---
# 엑셀도 media_set으로 분류되므로 run_media()를 쓴다. 실제 파싱(openpyxl 등)은 TODO.

@register
class ExtractJsonFromExcel(Transform):
    name = "extract_json_from_excel"
    input_count = 1

    class Params(BaseModel):
        sheet_name: str | None = None

    async def run_media(self, storage_key: str, params: "ExtractJsonFromExcel.Params") -> TransformResult:
        raise NotImplementedError("엑셀 파싱(openpyxl 등) 연결 대기 중")

    def run(self, inputs, params):
        raise NotImplementedError("media_set 입력은 run_media()를 사용한다")


# --- 배열 펼치기 (Explode Array) ---

def explode_array(rows: Rows, columns: Sequence[str], column: str) -> Rows:
    if column not in columns:
        raise ValueError(f"unknown column: {column}")
    result: Rows = []
    for row in rows:
        values = row.get(column)
        if not isinstance(values, list):
            raise ValueError(f"column '{column}' is not an array")
        for v in values:
            new_row = dict(row)
            new_row[column] = v
            result.append(new_row)
    return result


@register
class ExplodeArray(Transform):
    name = "explode_array"

    class Params(BaseModel):
        column: str

    def run(self, inputs, params: "ExplodeArray.Params") -> TransformResult:
        columns, rows = inputs[0]
        return TransformResult(columns=columns, rows=explode_array(rows, columns, params.column))


# --- 위치 보존 배열 펼치기 (Explode Array with Position) ---

def explode_array_with_position(rows: Rows, columns: Sequence[str], column: str, position_column: str) -> tuple[list[str], Rows]:
    if column not in columns:
        raise ValueError(f"unknown column: {column}")
    if position_column in columns:
        raise ValueError(f"position column '{position_column}' already exists")
    result: Rows = []
    for row in rows:
        values = row.get(column)
        if not isinstance(values, list):
            raise ValueError(f"column '{column}' is not an array")
        for i, v in enumerate(values):
            new_row = dict(row)
            new_row[column] = v
            new_row[position_column] = i
            result.append(new_row)
    return [*columns, position_column], result


@register
class ExplodeArrayWithPosition(Transform):
    name = "explode_array_with_position"

    class Params(BaseModel):
        column: str
        position_column: str = "position"

    def run(self, inputs, params: "ExplodeArrayWithPosition.Params") -> TransformResult:
        columns, rows = inputs[0]
        new_columns, new_rows = explode_array_with_position(rows, columns, params.column, params.position_column)
        return TransformResult(columns=new_columns, rows=new_rows)


# --- 구조 필드 추출 (Extract Struct Fields) ---

def extract_struct_fields(rows: Rows, columns: Sequence[str], column: str, fields: Sequence[str]) -> tuple[list[str], Rows]:
    if column not in columns:
        raise ValueError(f"unknown column: {column}")
    new_rows: Rows = []
    for row in rows:
        struct_value: dict[str, Any] = row.get(column) or {}
        new_row = dict(row)
        for f in fields:
            new_row[f] = struct_value.get(f)
        new_rows.append(new_row)
    return [*columns, *[f for f in fields if f not in columns]], new_rows


@register
class ExtractStructFields(Transform):
    name = "extract_struct_fields"

    class Params(BaseModel):
        column: str
        fields: list[str] = Field(min_length=1)

    def run(self, inputs, params: "ExtractStructFields.Params") -> TransformResult:
        columns, rows = inputs[0]
        new_columns, new_rows = extract_struct_fields(rows, columns, params.column, params.fields)
        return TransformResult(columns=new_columns, rows=new_rows)
