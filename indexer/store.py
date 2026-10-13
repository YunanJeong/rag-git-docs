"""조각과 벡터를 Qdrant 에 넣는다. 매번 새로 생기거나 바뀐 조각만 임베딩한다.

조각의 ID 는 설정 버전·파일 경로·조각 내용으로 만든 UUID 다. 내용이 같으면 ID 가 같다.
색인할 때마다 지금 md 로 계산한 ID 와 Qdrant 에 들어 있는 ID 를 통째로 비교해, 새 ID 의 조각만 임베딩해 넣고
사라진 ID 를 지운다. 어느 파일이 바뀌었는지 수집 쪽에서 넘겨받지 않으므로, 지난 실행이 중간에 실패했어도
다음 실행이 지금 md 와 같게 맞춘다.

검색하는 쪽(serve.py)은 컬렉션 대신 별칭으로 조회하고, 색인도 그 별칭이 가리키는 컬렉션에 바로 쓴다.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable

from qdrant_client import QdrantClient, models

# 색인과 검색이 같은 값을 봐야 한다. Qdrant 하나를 여러 릴리스가 같이 쓰면 릴리스마다 다르게 준다.
ALIAS = os.environ.get("QDRANT_ALIAS", "docs")
# 모델이나 자르기 설정이 바뀌면 같은 글자도 다른 벡터가 된다. 그때 이 값을 바꾸면 모든 조각의 ID 가 달라져 전부 다시 넣는다.
VERSION = "bge-m3/passage-2048/heading-v1"
# 한 번에 임베딩해 넣는 조각 수. 전부를 메모리에 쥐지 않아 조각이 아무리 많아도 메모리가 일정하다.
BATCH = 256
_NS = uuid.uuid5(uuid.NAMESPACE_URL, "rag-git-docs/chunk")


def client() -> QdrantClient:
    # 키를 켜지 않은 Qdrant 면 QDRANT_API_KEY 를 비워 둔다. 빈 값은 키 없이 붙는다.
    return QdrantClient(
        url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
        api_key=os.environ.get("QDRANT_API_KEY") or None,
    )


def point_id(path: str, text: str) -> str:
    return str(uuid.uuid5(_NS, f"{VERSION}\n{path}\n{text}"))


def _ensure(db: QdrantClient) -> None:
    """별칭이 없으면(첫 색인) 컬렉션을 만들고 별칭을 건다."""
    if db.collection_exists(ALIAS):
        return
    # 컬렉션 이름의 시각은 UTC 다. 끝의 Z 가 UTC 라는 표시다.
    name = f"{ALIAS}_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    db.create_collection(
        name,
        vectors_config={"dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams()},
    )
    db.update_collection_aliases(
        change_aliases_operations=[
            models.CreateAliasOperation(create_alias=models.CreateAlias(collection_name=name, alias_name=ALIAS))
        ]
    )


def _existing(db: QdrantClient) -> dict[str, models.ExtendedPointId]:
    """들어 있는 조각의 ID. 벡터와 본문은 받지 않는다. 비교는 문자열로 하고, 지울 때는 원래 ID 를 쓴다."""
    out: dict[str, models.ExtendedPointId] = {}
    offset = None
    while True:
        points, offset = db.scroll(ALIAS, limit=10_000, offset=offset, with_payload=False, with_vectors=False)
        out.update((str(p.id), p.id) for p in points)
        if offset is None:
            return out


def sync(db: QdrantClient, chunks: list[tuple[str, str]], encode: Callable[[list[str]], list[dict]]) -> tuple[int, int, int]:
    """chunks 는 (파일 경로, 조각 내용). Qdrant 를 chunks 와 같게 맞추고 (넣은 수, 지운 수, 그대로 둔 수) 를 돌려준다."""
    _ensure(db)
    wanted = {point_id(path, text): (path, text) for path, text in chunks}
    have = _existing(db)
    new = [(pid, path, text) for pid, (path, text) in wanted.items() if pid not in have]
    gone = [orig for pid, orig in have.items() if pid not in wanted]

    # 넣기를 먼저 하고 지우기를 나중에 한다. 반대로 하면 고친 문서가 잠깐 검색에서 사라진다.
    for i in range(0, len(new), BATCH):
        batch = new[i : i + BATCH]
        vectors = encode([text for _, _, text in batch])
        db.upsert(
            ALIAS,
            [
                models.PointStruct(id=pid, vector=v, payload={"text": text, "path": path})
                for (pid, path, text), v in zip(batch, vectors)
            ],
            wait=True,
        )
    for i in range(0, len(gone), 10_000):
        db.delete(ALIAS, points_selector=models.PointIdsList(points=gone[i : i + 10_000]), wait=True)
    return len(new), len(gone), len(wanted) - len(new)
