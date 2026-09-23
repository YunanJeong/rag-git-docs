"""진입점 1 — DOCS_DIR 아래의 md 를 전량 색인한다.

매번 컬렉션을 새로 만들고 처음부터 다시 넣는다. 증분 색인을 하지 않는다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from rag.chunk import chunk_markdown
from rag.embed import DIM, Embedder
from rag.store import Store

EXCLUDE = (".git/", "node_modules/", ".venv/")


def collect(docs_dir: Path) -> list[Path]:
    out = []
    for p in sorted(docs_dir.rglob("*.md")):
        rel = p.relative_to(docs_dir).as_posix()
        if any(rel.startswith(x) or f"/{x}" in f"/{rel}" for x in EXCLUDE):
            continue
        out.append(p)
    return out


def main() -> int:
    docs_dir = os.environ.get("DOCS_DIR")
    if not docs_dir:
        print("환경변수 DOCS_DIR 이 필요하다", file=sys.stderr)
        return 2
    root = Path(docs_dir).expanduser().resolve()
    if not root.is_dir():
        print(f"디렉터리가 아니다: {root}", file=sys.stderr)
        return 2

    files = collect(root)
    if not files:
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
        cs = chunk_markdown(text, rel)
        chunks.extend(cs)
        print(f"  {rel} → 조각 {len(cs)}개", file=sys.stderr)

    print(f"파일 {len(files)}개, 조각 {len(chunks)}개. 임베딩 시작", file=sys.stderr)
    embedder = Embedder(os.environ.get("EMBED_MODEL", "BAAI/bge-m3"))
    dense, sparse = embedder.encode([c.text for c in chunks])

    store = Store()
    store.recreate_collection(dim=DIM)
    store.upsert(chunks, dense, sparse)

    print(f"색인 완료. 컬렉션 포인트 {store.count()}개", file=sys.stderr)
    if failed:
        print(f"디코드 실패 {len(failed)}개: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
