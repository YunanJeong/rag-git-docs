"""진입점 2 — 질의를 임베딩해 관련 조각을 찾는다."""

from __future__ import annotations

import argparse
import os
import sys

from rag.embed import Embedder
from rag.store import Store


def main() -> int:
    parser = argparse.ArgumentParser(description="색인된 문서에서 관련 조각을 찾는다")
    parser.add_argument("query", help="찾을 내용")
    parser.add_argument("--top-k", type=int, default=int(os.environ.get("TOP_K", "5")))
    args = parser.parse_args()

    embedder = Embedder(os.environ.get("EMBED_MODEL", "BAAI/bge-m3"))
    dense, sparse = embedder.encode([args.query])

    store = Store()
    hits = store.search(dense[0], sparse[0], top_k=args.top_k)

    if not hits:
        print("결과 없음", file=sys.stderr)
        return 1

    for i, h in enumerate(hits, 1):
        crumb = " > ".join(h.heading_path) if h.heading_path else "-"
        # 조각 본문 첫 줄은 색인 때 붙인 브레드크럼이므로 떼고 보여준다
        body = h.text.split("\n", 1)[1] if "\n" in h.text else h.text
        excerpt = body.strip().replace("\n", " ")[:200]
        print(f"[{i}] score={h.score:.4f}  {h.doc_path}  ({crumb})")
        print(f"    {excerpt}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
