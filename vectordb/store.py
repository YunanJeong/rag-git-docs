"""Qdrant 저장과 검색.

dense 와 sparse 를 named vector 로 함께 저장하고, 검색 시 둘을 각각 돌린 뒤
RRF(Reciprocal Rank Fusion) 로 순위를 합친다.

검색은 별칭(alias) 으로 한다. 색인은 새 컬렉션을 채운 뒤 별칭만 옮기므로,
색인하는 동안에도 검색은 옛 색인으로 계속 돈다.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

DENSE = "dense"
SPARSE = "sparse"


@dataclass
class Hit:
    score: float
    doc_path: str
    heading_path: list[str]
    text: str


def _point_id(doc_path: str, chunk_index: int) -> str:
    """Qdrant 는 point ID 로 부호 없는 정수 또는 UUID 만 받는다."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_path}#{chunk_index}"))


def _to_sparse(weights: dict[int, float]) -> models.SparseVector:
    return models.SparseVector(indices=list(weights.keys()), values=list(weights.values()))


class Store:
    def __init__(self) -> None:
        # QDRANT_API_KEY 가 비어 있으면 None 으로 바꿔 인증 헤더를 아예 안 보낸다
        self.alias = os.environ.get("QDRANT_COLLECTION", "docs")
        self.client = QdrantClient(
            url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
            api_key=os.environ.get("QDRANT_API_KEY") or None,
        )

    def replace(self, chunks, dense_vecs, sparse_vecs, dim: int, batch_size: int = 64) -> str:
        """새 컬렉션을 채우고 별칭을 옮긴 뒤 옛 컬렉션을 지운다. 새 컬렉션 이름을 돌려준다.

        채우다 실패하면 새 컬렉션만 지운다. 별칭은 옛 색인을 그대로 가리킨다.
        """
        name = f"{self.alias}_{time.strftime('%Y%m%d_%H%M%S')}"
        self.client.create_collection(
            collection_name=name,
            vectors_config={DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)},
            sparse_vectors_config={SPARSE: models.SparseVectorParams()},
        )
        points = [
            models.PointStruct(
                id=_point_id(c.doc_path, c.chunk_index),
                vector={DENSE: d, SPARSE: _to_sparse(s)},
                payload={"doc_path": c.doc_path, "heading_path": c.heading_path, "text": c.text},
            )
            for c, d, s in zip(chunks, dense_vecs, sparse_vecs)
        ]
        try:
            for i in range(0, len(points), batch_size):
                self.client.upsert(collection_name=name, points=points[i : i + batch_size])
        except Exception:
            self.client.delete_collection(name)
            raise

        # 별칭 삭제와 생성을 한 요청에 담는다. Qdrant 가 한 번에 적용하므로
        # 검색이 별칭을 못 찾는 순간이 없다.
        self.client.update_collection_aliases(
            change_aliases_operations=[
                models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=self.alias)),
                models.CreateAliasOperation(
                    create_alias=models.CreateAlias(collection_name=name, alias_name=self.alias)
                ),
            ]
        )
        for c in self.client.get_collections().collections:
            if c.name.startswith(f"{self.alias}_") and c.name != name:
                self.client.delete_collection(c.name)
        return name

    def search(self, dense_vec: list[float], sparse_vec: dict[int, float], top_k: int = 5) -> list[Hit]:
        result = self.client.query_points(
            collection_name=self.alias,
            prefetch=[
                models.Prefetch(query=dense_vec, using=DENSE, limit=20),
                models.Prefetch(query=_to_sparse(sparse_vec), using=SPARSE, limit=20),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
        return [
            Hit(
                score=p.score,
                doc_path=p.payload["doc_path"],
                heading_path=p.payload["heading_path"],
                text=p.payload["text"],
            )
            for p in result.points
        ]

    def count(self) -> int:
        return self.client.count(collection_name=self.alias, exact=True).count
