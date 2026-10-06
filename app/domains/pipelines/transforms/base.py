"""Transform 공통 인터페이스. 데이터 변환/결합/통합/AI 사용 메뉴의 모든 노드가 이걸 구현한다."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel


@dataclass
class TransformContext:
    """실행 시 주입되는 의존성. storage/ai_client 모듈과 session을 담아 넘긴다."""
    session: Any = None


@dataclass
class TransformResult:
    output_kind: str   # "dataset" | "media_set"
    output_ref: int     # 결과로 생성된 Dataset/MediaSet id
    meta: dict[str, Any] = field(default_factory=dict)


class Transform(ABC):
    name: ClassVar[str]              # registry 키 = PipelineNode.kind 값과 매칭
    input_kinds: ClassVar[tuple[str, ...]]
    output_kind: ClassVar[str]

    class Params(BaseModel):
        pass

    @abstractmethod
    async def run(
        self, inputs: list[int], params: BaseModel, ctx: TransformContext
    ) -> TransformResult:
        """멱등하게 작성: 같은 입력 id + 같은 params면 같은 결과, 재실행해도 안전해야 한다.
        주의: 이 메서드 안에서 media/datasets의 테이블을 직접 쿼리하지 말고,
        반드시 app.domains.media.service / app.domains.datasets.service 함수만 호출할 것
        (나중에 pipelines를 별도 서버로 분리할 때 이 규칙이 지켜져 있어야 함)."""
