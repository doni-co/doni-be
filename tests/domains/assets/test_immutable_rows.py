"""[파일]/[파이프라인빌더]의 데이터는 갱신하지 않는다: 한 Asset에는 행을 한 번만 저장할 수 있다."""
import pytest

from app.domains.assets import service
from app.models.asset import Asset, AssetRow


class FakeSession:
    def __init__(self):
        self.assets = {1: Asset(id=1, name="a.csv"), 2: Asset(id=2, name="b.csv")}
        self.rows = []

    async def get(self, model, obj_id):
        return self.assets.get(obj_id)

    def add(self, obj):
        if isinstance(obj, AssetRow):
            self.rows.append(obj)

    async def commit(self):
        pass


async def test_rows_can_be_saved_once():
    session = FakeSession()
    await service.save_rows(session, 1, ["a"], [{"a": 1}, {"a": 2}])
    assert session.assets[1].row_count == 2
    assert session.assets[1].schema_def == {"columns": ["a"]}
    assert [r.row_idx for r in session.rows] == [0, 1]


async def test_saving_again_is_rejected_and_keeps_existing_data():
    session = FakeSession()
    await service.save_rows(session, 1, ["a"], [{"a": 1}])
    with pytest.raises(ValueError, match="immutable"):
        await service.save_rows(session, 1, ["x"], [{"x": 9}, {"x": 9}])
    assert session.assets[1].row_count == 1
    assert session.assets[1].schema_def == {"columns": ["a"]}
    assert len(session.rows) == 1


async def test_empty_result_is_also_final():
    """행이 0개인 결과도 저장된 것으로 본다(row_count=0). 다시 저장할 수 없다."""
    session = FakeSession()
    await service.save_rows(session, 1, ["a"], [])
    with pytest.raises(ValueError, match="immutable"):
        await service.save_rows(session, 1, ["a"], [{"a": 1}])


async def test_other_assets_are_independent():
    session = FakeSession()
    await service.save_rows(session, 1, ["a"], [{"a": 1}])
    await service.save_rows(session, 2, ["a"], [{"a": 1}])  # 같은 내용이어도 별개의 Asset


async def test_unknown_asset():
    with pytest.raises(ValueError, match="not found"):
        await service.save_rows(FakeSession(), 99, ["a"], [])
