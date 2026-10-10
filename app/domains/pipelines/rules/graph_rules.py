"""파이프라인 그래프(노드-엣지) 자체의 규칙을 검증하는 순수 함수. DB, 세션을 모른다.
입력은 노드/엣지의 id 목록뿐이라 DB 없이 단위 테스트가 가능하다."""


class PipelineValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(", ".join(errors))


def has_cycle(node_ids: set[int], edges: list[tuple[int, int]]) -> bool:
    graph: dict[int, list[int]] = {n: [] for n in node_ids}
    for src, dst in edges:
        graph.setdefault(src, []).append(dst)
    visiting, visited = set(), set()

    def dfs(n: int) -> bool:
        if n in visiting:
            return True
        if n in visited:
            return False
        visiting.add(n)
        for nxt in graph.get(n, []):
            if dfs(nxt):
                return True
        visiting.discard(n)
        visited.add(n)
        return False

    return any(dfs(n) for n in node_ids)


def validate_new_edge(node_ids: set[int], existing_edges: list[tuple[int, int]], new_edge: tuple[int, int]) -> None:
    if has_cycle(node_ids, [*existing_edges, new_edge]):
        raise PipelineValidationError(["edge would create a cycle"])
    # TODO: 노드 kind의 input_kinds/output_kind를 nodes.registry에서 조회해 입출력 타입도 검증
