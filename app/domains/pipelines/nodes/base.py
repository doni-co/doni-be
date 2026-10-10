"""노드가 실행하는 작업 전체(메뉴의 데이터 변환/결합/통합/AI 사용을 모두 포함하는 상위 개념)의
공통 인터페이스. 이 "Transform"은 메뉴의 "데이터 변환" 카테고리보다 넓은 코드 용어다."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel

Rows = list[dict[str, Any]]


@dataclass
class TransformContext:
    """실행 시 주입되는 의존성 (storage, ai_client 모듈 등을 쓸 때 참고용으로 둔다)."""
    session: Any = None


@dataclass
class TransformResult:
    columns: list[str]
    rows: Rows


class Transform(ABC):
    name: ClassVar[str]              # registry 키 = PipelineNode.kind 값과 매칭
    input_count: ClassVar[int] = 1   # 몇 개의 입력 Asset을 받는지 (join/union은 2 이상)

    class Params(BaseModel):
        pass

    @abstractmethod
    def run(self, inputs: list[tuple[list[str], Rows]], params: BaseModel) -> TransformResult:
        """순수 함수로 구현할 것: DB/네트워크에 의존하지 않고, (columns, rows) 입력을 받아
        (columns, rows) 결과를 반환한다. 같은 입력이면 항상 같은 결과를 내야 한다(멱등).
        입력/출력 로드·저장은 use_cases/execute_node.py가 담당하며 여기서는 하지 않는다."""
