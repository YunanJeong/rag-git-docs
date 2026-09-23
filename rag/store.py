"""Qdrant 저장과 검색.

dense 와 sparse 를 named vector 로 함께 저장하고, 검색 시 둘을 각각 돌린 뒤
RRF(Reciprocal Rank Fusion) 로 순위를 합친다.
"""

from __future__ import annotations

import os
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
    """같은 조각이면 항상 같은 ID. 재색인해도 중복 포인트가 쌓이지 않는다.

    Qdrant 는 point ID 로 부호 없는 정수 또는 UUID 만 받는다. 해시 hexdigest 를
    그대로 넣으면 400 이 떨어지므로 uuid5 로 만든다.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_path}#{chunk_index}"))


def _to_sparse(weights: dict[int, float]) -> models.SparseVector:
    return models.SparseVector(indices=list(weights.keys()), values=list(weights.values()))


class Store:
    def __init__(self, url: str | None = None, collection: str | None = None) -> None:
        self.collection = collection or os.environ.get("QDRANT_COLLECTION", "docs")
        self.client = QdrantClient(url=url or os.environ.get("QDRANT_URL", "http://localhost:6333"))

    def recreate_collection(self, dim: int = 1024) -> None:
        """있으면 지우고 새로 만든다.

        매번 통째로 다시 만들기 때문에 삭제된 문서의 조각이 남는 문제가 아예 없다.
        증분 색인을 하지 않는 대신 얻는 단순함이다.
        """
        self.client.recreate_collection(
            collection_name=self.collection,
            vectors_config={DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)},
            sparse_vectors_config={SPARSE: models.SparseVectorParams()},
        )

    def upsert(self, chunks, dense_vecs, sparse_vecs, batch_size: int = 64) -> None:
        points = [
            models.PointStruct(
                id=_point_id(c.doc_path, c.chunk_index),
                vector={DENSE: d, SPARSE: _to_sparse(s)},
                payload={
                    "doc_path": c.doc_path,
                    "chunk_index": c.chunk_index,
                    "heading_path": c.heading_path,
                    "text": c.text,
                },
            )
            for c, d, s in zip(chunks, dense_vecs, sparse_vecs)
        ]
        for i in range(0, len(points), batch_size):
            self.client.upsert(collection_name=self.collection, points=points[i : i + batch_size])

    def search(
        self,
        dense_vec: list[float],
        sparse_vec: dict[int, float],
        top_k: int = 5,
        prefetch: int = 20,
    ) -> list[Hit]:
        result = self.client.query_points(
            collection_name=self.collection,
            prefetch=[
                models.Prefetch(query=dense_vec, using=DENSE, limit=prefetch),
                models.Prefetch(query=_to_sparse(sparse_vec), using=SPARSE, limit=prefetch),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
        return [
            Hit(
                score=p.score,
                doc_path=p.payload.get("doc_path", ""),
                heading_path=p.payload.get("heading_path", []),
                text=p.payload.get("text", ""),
            )
            for p in result.points
        ]

    def count(self) -> int:
        return self.client.count(collection_name=self.collection, exact=True).count
