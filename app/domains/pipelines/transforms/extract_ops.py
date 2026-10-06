"""데이터 변환 > 추출: PDF/이미지/엑셀에서 텍스트 추출, 배열 분해, 구조체 필드 추출.
MediaSet(비정형) -> Dataset(정형)으로 바꾸는 노드들."""
from pydantic import BaseModel

from app.domains.pipelines.transforms.base import Transform, TransformContext, TransformResult
from app.domains.pipelines.transforms.registry import register


@register
class PdfExtract(Transform):
    name = "pdf_extract"
    input_kinds = ("media_set",)
    output_kind = "dataset"

    class Params(BaseModel):
        ocr_fallback: bool = True  # 복사 가능한 텍스트는 그대로, 이미지 영역만 OCR

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO


@register
class ImageTextExtract(Transform):
    name = "image_text_extract"
    input_kinds = ("media_set",)
    output_kind = "dataset"

    class Params(BaseModel):
        pass

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO


@register
class ExcelTextExtract(Transform):
    name = "excel_text_extract"
    input_kinds = ("media_set",)
    output_kind = "dataset"

    class Params(BaseModel):
        pass

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO


@register
class ArrayDecompose(Transform):
    name = "array_decompose"
    input_kinds = ("dataset",)
    output_kind = "dataset"

    class Params(BaseModel):
        column: str

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO


@register
class StructFieldExtract(Transform):
    name = "struct_field_extract"
    input_kinds = ("dataset",)
    output_kind = "dataset"

    class Params(BaseModel):
        column: str
        fields: list[str]

    async def run(self, inputs, params, ctx: TransformContext) -> TransformResult:
        raise NotImplementedError  # TODO
