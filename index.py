"""진입점 2 — DOCS_DIR 의 md 를 전부 잘라 임베딩하고 Qdrant 에 넣는다."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from indexer import store
from indexer.chunk import chunk_markdown
from indexer.embed import Embedder


def read_md(path: Path) -> str | None:
    """UTF-8 로 읽고, 안 되면 CP949 로 읽는다. 둘 다 안 되면 None.

    한글 문서 가운데 옛 윈도우 인코딩(CP949)으로 저장된 것이 섞여 있다.
    """
    raw = path.read_bytes()
    for enc in ("utf-8", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def main() -> int:
    root = Path(os.environ["DOCS_DIR"])
    texts: list[str] = []
    skipped = 0
    for f in sorted(root.rglob("*.md")):
        rel = f.relative_to(root).as_posix()
        text = read_md(f)
        if text is None:
            # 파일 하나 때문에 색인 전체가 멈추지 않게 건너뛴다
            print(f"  ! 인코딩을 알 수 없어 건너뜀: {rel}", file=sys.stderr)
            skipped += 1
            continue
        texts.extend(chunk_markdown(text, rel))
    # 비어 있으면 멀쩡한 색인을 빈 색인으로 바꾸게 된다.
    if not texts:
        print(f"md 가 없다: {root}", file=sys.stderr)
        return 2

    print(f"조각 {len(texts)}개 임베딩", file=sys.stderr)
    name = store.replace(store.client(), texts, Embedder().encode(texts))
    print(f"완료: {store.ALIAS} → {name}, 건너뛴 파일 {skipped}개", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
