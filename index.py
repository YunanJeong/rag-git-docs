"""진입점 2 — DOCS_DIR 의 md 를 전부 잘라 임베딩하고 Qdrant 에 넣는다."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from indexer import store
from indexer.chunk import chunk_markdown
from indexer.embed import Embedder


def main() -> int:
    root = Path(os.environ["DOCS_DIR"])
    texts = [
        c
        for f in sorted(root.rglob("*.md"))
        for c in chunk_markdown(f.read_text(encoding="utf-8"), f.relative_to(root).as_posix())
    ]
    # 비어 있으면 멀쩡한 색인을 빈 색인으로 바꾸게 된다.
    if not texts:
        print(f"md 가 없다: {root}", file=sys.stderr)
        return 2

    print(f"조각 {len(texts)}개 임베딩", file=sys.stderr)
    name = store.replace(store.client(), texts, Embedder().encode(texts))
    print(f"완료: {store.ALIAS} → {name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
