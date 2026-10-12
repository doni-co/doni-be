"""전체 노드 카탈로그. PipelineNode.kind 문자열 <-> 실제 Transform 클래스를 연결한다.
이 파일 하나만 보면 메뉴에 노출되는 기능 전체를 파악할 수 있다."""
from app.domains.pipelines.nodes.base import Transform

_REGISTRY: dict[str, type[Transform]] = {}


def register(cls: type[Transform]) -> type[Transform]:
    _REGISTRY[cls.name] = cls
    return cls


def get(name: str) -> type[Transform]:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(f"unknown transform: {name}") from None


def all_names() -> list[str]:
    return sorted(_REGISTRY)
