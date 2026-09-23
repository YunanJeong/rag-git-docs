"""텍스트를 벡터로 바꾼다. bge-m3 로컬 실행.

dense 와 sparse 를 한 번의 추론으로 함께 낸다.
- dense  : 1024개 실수로 된 의미 좌표. 표현이 달라도 뜻이 같으면 가까이 놓인다.
- sparse : 단어 하나가 축 하나인 희소 벡터. 고유명사·에러코드처럼 정확히 일치해야
           하는 토큰을 잡는다. dense 는 kr-mum 과 kr-sum 을 구별하지 못한다.
"""

from __future__ import annotations

DIM = 1024


class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self.model_name = model_name
        self._model = None

    def _load(self):
        # import 만으로 2.3GB 를 올리지 않도록 첫 encode 때 로딩한다.
        if self._model is None:
            from FlagEmbedding import BGEM3FlagModel

            self._model = BGEM3FlagModel(self.model_name, use_fp16=True)
        return self._model

    def encode(
        self, texts: list[str], batch_size: int = 8
    ) -> tuple[list[list[float]], list[dict[int, float]]]:
        model = self._load()
        out = model.encode(
            texts,
            batch_size=batch_size,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense = [[float(x) for x in v] for v in out["dense_vecs"]]
        # lexical_weights 의 키가 문자열로 온다. Qdrant sparse 인덱스는 정수여야 하므로
        # 여기서 변환하지 않으면 저장 시점에 터진다.
        sparse = [{int(k): float(v) for k, v in w.items()} for w in out["lexical_weights"]]
        return dense, sparse
