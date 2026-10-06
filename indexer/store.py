"""조각과 벡터를 Qdrant 에 넣는다.

검색하는 쪽(serve.py)은 컬렉션 대신 별칭 docs 로 조회한다. 색인은 새 컬렉션을 따로
채운 뒤 별칭만 옮긴다. 그래서 색인하는 동안에도 검색은 옛 색인으로 돌고,
색인이 실패해도 옛 색인이 남는다.
"""

from __future__ import annotations

import os
import time

from qdrant_client import QdrantClient, models

ALIAS = "docs"


def client() -> QdrantClient:
    # 키를 켜지 않은 Qdrant 면 QDRANT_API_KEY 를 비워 둔다. 빈 값은 키 없이 붙는다.
    return QdrantClient(
        url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
        api_key=os.environ.get("QDRANT_API_KEY") or None,
    )


def replace(db: QdrantClient, texts: list[str], vectors: list[dict]) -> str:
    # 컬렉션 이름의 시각은 UTC 다. 끝의 Z 가 UTC 라는 표시다.
    name = f"{ALIAS}_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    db.create_collection(
        name,
        vectors_config={"dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams()},
    )
    db.upload_points(
        name,
        [models.PointStruct(id=i, vector=v, payload={"text": t}) for i, (t, v) in enumerate(zip(texts, vectors))],
        wait=True,
    )

    # 별칭을 쓰기 전에 만든 같은 이름의 실제 컬렉션이 있으면 별칭을 만들 수 없다.
    if db.collection_exists(ALIAS) and not db.get_collection_aliases(ALIAS).aliases:
        db.delete_collection(ALIAS)

    # 삭제와 생성을 한 요청으로 보내 검색이 별칭을 못 찾는 순간이 없게 한다.
    db.update_collection_aliases(
        change_aliases_operations=[
            models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=ALIAS)),
            models.CreateAliasOperation(create_alias=models.CreateAlias(collection_name=name, alias_name=ALIAS)),
        ]
    )
    for c in db.get_collections().collections:
        if c.name.startswith(f"{ALIAS}_") and c.name != name:
            db.delete_collection(c.name)
    return name
