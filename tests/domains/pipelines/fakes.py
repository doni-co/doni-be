"""create_step/retry_node/delete_node/execute_node이 실제로 던지는 SQLAlchemy Core
select/update/delete 문만 이해하는 아주 작은 인메모리 세션. 일반 SQL 엔진이 아니라
"이 프로젝트의 use_case들이 쓰는 where(eq/in_) + order_by(id.desc()) + values()" 패턴만 해석한다.
Postgres 전용 동작(부분 유니크 인덱스, DISTINCT ON 등)은 흉내만 내며, 실제 제약 검증은
docker-compose db + alembic upgrade head로 따로 해야 한다 — 플랜의 "검증 방법" 참고."""
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import Delete, Select, Update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList
from sqlalchemy.sql.operators import eq, in_op

from app.models.asset import Asset
from app.models.enums import NodeRunStatus
from app.models.pipeline import NodeRun, PipelineEdge, PipelineNode

_MODELS_BY_TABLE = {m.__tablename__: m for m in (PipelineNode, PipelineEdge, NodeRun, Asset)}


def _row_matches(obj, clause) -> bool:
    if isinstance(clause, BooleanClauseList):
        return all(_row_matches(obj, c) for c in clause.clauses)
    if isinstance(clause, BinaryExpression):
        col_name = clause.left.key
        value = getattr(obj, col_name, None)
        right = getattr(clause.right, "value", clause.right)
        if clause.operator is eq:
            return value == right
        if clause.operator is in_op:
            return value in right
    raise NotImplementedError(f"FakeSession이 해석 못 하는 조건: {clause}")


@dataclass
class _FakeScalars:
    rows: list

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


@dataclass
class _FakeResult:
    rows: list = field(default_factory=list)
    rowcount: int = 0

    def scalars(self):
        return _FakeScalars(self.rows)


class FakeSession:
    """nodes/edges/runs/assets를 리스트로 들고 있는 테스트 전용 세션."""

    def __init__(self, nodes=(), edges=(), runs=(), assets=()):
        self.nodes: list[PipelineNode] = list(nodes)
        self.edges: list[PipelineEdge] = list(edges)
        self.runs: list[NodeRun] = list(runs)
        self.assets: list[Asset] = list(assets)
        self._pending: list = []
        self._next_id = {
            PipelineNode: max((n.id for n in self.nodes), default=0) + 1,
            PipelineEdge: max((e.id for e in self.edges), default=0) + 1,
            NodeRun: max((r.id for r in self.runs), default=0) + 1,
        }
        self.deleted: list = []

    def _table_by_model(self, model):
        return {PipelineNode: self.nodes, PipelineEdge: self.edges, NodeRun: self.runs, Asset: self.assets}[model]

    def _table_by_name(self, table_name):
        return self._table_by_model(_MODELS_BY_TABLE[table_name])

    def add(self, obj):
        self._pending.append(obj)

    def add_all(self, objs):
        self._pending.extend(objs)

    async def flush(self):
        for obj in self._pending:
            model = type(obj)
            if getattr(obj, "id", None) is None and model in self._next_id:
                obj.id = self._next_id[model]
                self._next_id[model] += 1
            if isinstance(obj, NodeRun) and obj.created_at is None:
                obj.created_at = datetime.now(UTC)  # 실제로는 DB server_default=now() + refresh()가 채움
            table = self._table_by_model(model)
            if obj not in table:
                table.append(obj)
        self._pending = []

    async def commit(self):
        # 노드당 PENDING/RUNNING 1개 제한(부분 유니크 인덱스)을 느슨하게 흉내낸다.
        pending_runs = [o for o in self._pending if isinstance(o, NodeRun)]
        for run in pending_runs:
            if run.status in (NodeRunStatus.PENDING, NodeRunStatus.RUNNING):
                clash = [
                    r for r in self.runs
                    if r.node_id == run.node_id and r.status in (NodeRunStatus.PENDING, NodeRunStatus.RUNNING)
                ]
                if clash:
                    self._pending = []
                    raise IntegrityError("ix_node_runs_one_active_per_node", {}, Exception())
        await self.flush()

    async def rollback(self):
        self._pending = []

    async def refresh(self, obj):
        pass

    async def get(self, model, obj_id):
        for obj in self._table_by_model(model):
            if obj.id == obj_id:
                return obj
        return None

    async def delete(self, obj):
        self.deleted.append(obj)
        table = self._table_by_model(type(obj))
        if obj in table:
            table.remove(obj)

    async def execute(self, statement):
        if isinstance(statement, Select):
            return self._execute_select(statement)
        if isinstance(statement, Update):
            return self._execute_update(statement)
        if isinstance(statement, Delete):
            return self._execute_delete(statement)
        raise NotImplementedError(type(statement))

    def _execute_select(self, statement):
        model = statement.column_descriptions[0]["entity"]
        rows = list(self._table_by_model(model))
        if statement.whereclause is not None:
            rows = [r for r in rows if _row_matches(r, statement.whereclause)]
        if statement._order_by_clauses:  # 이 프로젝트에서 쓰는 유일한 패턴: id.desc()
            rows = sorted(rows, key=lambda r: r.id, reverse=True)
        return _FakeResult(rows=rows)

    def _execute_update(self, statement):
        rows = list(self._table_by_name(statement.table.name))
        if statement.whereclause is not None:
            rows = [r for r in rows if _row_matches(r, statement.whereclause)]
        for r in rows:
            for key, bind in (statement._values or {}).items():
                col_name = key.key if hasattr(key, "key") else key
                setattr(r, col_name, getattr(bind, "value", bind))
        return _FakeResult(rows=rows, rowcount=len(rows))

    def _execute_delete(self, statement):
        table = self._table_by_name(statement.table.name)
        rows = list(table)
        if statement.whereclause is not None:
            rows = [r for r in rows if _row_matches(r, statement.whereclause)]
        for r in rows:
            table.remove(r)
        return _FakeResult(rows=rows, rowcount=len(rows))
