"""텍스트를 bge-m3 로 dense 와 sparse 벡터로 바꾼다.

dense 는 뜻이 비슷한 것을, sparse 는 글자가 정확히 같은 것을 찾는다.
region-a1 과 region-a2 처럼 한 글자 다른 식별자는 sparse 만 구별한다.
"""

from __future__ import annotations

import threading

from FlagEmbedding import BGEM3FlagModel
from qdrant_client import models


class Embedder:
    def __init__(self) -> None:
        # 기본값 512 토큰이면 긴 한국어 조각의 뒷부분이 잘려 임베딩에서 빠진다.
        self.model = BGEM3FlagModel("BAAI/bge-m3", passage_max_length=2048)
        # encode 가 호출마다 모델 가중치를 장치로 다시 옮긴다.
        # 두 스레드가 동시에 옮기면 프로세스가 세그폴트로 죽어서, 한 번에 하나만 돌린다.
        self.lock = threading.Lock()

    def encode(self, texts: list[str]) -> list[dict]:
        with self.lock:
            # 기본 배치는 256 이라, 긴 조각이 섞이면 중간 계산값이 수 GB 로 커져 OOM 이 난다.
            # CPU 추론은 배치를 키워도 빨라지지 않으므로 작게 둔다.
            out = self.model.encode(texts, batch_size=8, return_dense=True, return_sparse=True)
        return [
            {
                "dense": d.tolist(),
                "sparse": models.SparseVector(
                    indices=[int(k) for k in s], values=[float(v) for v in s.values()]
                ),
            }
            for d, s in zip(out["dense_vecs"], out["lexical_weights"])
        ]
