import sys
from pathlib import Path

import pytest
from qdrant_client import QdrantClient, models

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from indexer import store  # noqa: E402


class FakeEncoder:
    """임베딩한 조각을 기록하는 가짜 모델. 진짜 모델 없이 '무엇을 다시 임베딩했나' 만 본다."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def __call__(self, texts: list[str]) -> list[dict]:
        self.seen += texts
        return [
            {"dense": [1.0] + [0.0] * 1023, "sparse": models.SparseVector(indices=[1], values=[1.0])} for _ in texts
        ]


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(store, "ALIAS", "docs")
    return QdrantClient(":memory:")


def stored(db) -> set[tuple[str, str]]:
    points, _ = db.scroll("docs", limit=1000, with_payload=True)
    return {(p.payload["path"], p.payload["text"]) for p in points}


A = [("g/r/a.md", "a1"), ("g/r/a.md", "a2")]
B = [("g/r/b.md", "b1")]


def test_first_run_creates_collection_and_inserts_everything(db):
    enc = FakeEncoder()
    assert store.sync(db, A + B, enc) == (3, 0, 0)
    assert "docs" in {a.alias_name for a in db.get_aliases().aliases}, "검색은 별칭으로 하므로 별칭이 있어야 한다"
    assert stored(db) == set(A + B)


def test_changed_file_reembeds_only_its_chunks_and_drops_old_ones(db):
    store.sync(db, A + B, FakeEncoder())
    enc = FakeEncoder()
    changed = [("g/r/a.md", "a1 고침")]
    assert store.sync(db, changed + B, enc) == (1, 2, 1)
    assert enc.seen == ["a1 고침"], "바뀌지 않은 b.md 는 다시 임베딩하지 않는다"
    assert stored(db) == set(changed + B)


def test_deleted_file_chunks_are_removed(db):
    store.sync(db, A + B, FakeEncoder())
    enc = FakeEncoder()
    assert store.sync(db, B, enc) == (0, 2, 1)
    assert enc.seen == []
    assert stored(db) == set(B)


def test_nothing_changed_embeds_nothing(db):
    store.sync(db, A + B, FakeEncoder())
    enc = FakeEncoder()
    assert store.sync(db, A + B, enc) == (0, 0, 3)
    assert enc.seen == []


def test_version_change_reembeds_everything(db, monkeypatch):
    store.sync(db, A + B, FakeEncoder())
    monkeypatch.setattr(store, "VERSION", "다른-모델")
    enc = FakeEncoder()
    assert store.sync(db, A + B, enc) == (3, 3, 0)
    assert sorted(enc.seen) == ["a1", "a2", "b1"]
    assert stored(db) == set(A + B)


def test_old_sequential_ids_are_replaced(db):
    # 증분 이전 색인은 0, 1, 2… 순번 ID 였다. 첫 증분 실행에서 전부 새 ID 로 바뀌어야 한다
    store.sync(db, [], FakeEncoder())
    db.upsert(
        "docs",
        [
            models.PointStruct(
                id=0, vector=FakeEncoder()(["x"])[0], payload={"text": "옛 조각"}
            )
        ],
    )
    assert store.sync(db, B, FakeEncoder()) == (1, 1, 0)
    assert stored(db) == set(B)


def test_batches_are_bounded(db, monkeypatch):
    monkeypatch.setattr(store, "BATCH", 2)
    calls: list[int] = []

    def enc(texts):
        calls.append(len(texts))
        return FakeEncoder()(texts)

    store.sync(db, [("p.md", f"c{i}") for i in range(5)], enc)
    assert calls == [2, 2, 1], "조각을 한 번에 다 임베딩하지 않는다"
