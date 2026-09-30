"""진입점 2 — DOCS_DIR 아래의 md 를 전량 색인한다."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from vectordb.chunk import chunk_markdown
from vectordb.embed import DIM, Embedder
from vectordb.store import Store


def main() -> int:
    docs_dir = os.environ.get("DOCS_DIR")
    if not docs_dir:
        print("환경변수 DOCS_DIR 이 필요하다", file=sys.stderr)
        return 2
    root = Path(docs_dir).expanduser().resolve()
    files = sorted(root.rglob("*.md"))
    if not files:
        # 수집이 실패해 비었을 때 멀쩡한 색인을 빈 색인으로 덮어쓰지 않는다
        print(f"md 파일이 없다: {root}", file=sys.stderr)
        return 2

    chunks = []
    failed: list[str] = []
    for f in files:
        rel = f.relative_to(root).as_posix()
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"  ! 디코드 실패, 건너뜀: {rel}", file=sys.stderr)
            failed.append(rel)
            continue
        chunks.extend(chunk_markdown(text, rel))

    print(f"파일 {len(files)}개, 조각 {len(chunks)}개. 임베딩 시작", file=sys.stderr)
    dense, sparse = Embedder().encode([c.text for c in chunks])
    store = Store()
    name = store.replace(chunks, dense, sparse, dim=DIM)
    print(f"색인 완료. {store.alias} → {name}, 조각 {store.count()}개", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
