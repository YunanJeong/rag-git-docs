"""진입점 2 — DOCS_DIR 의 md 를 전부 잘라, 새로 생기거나 바뀐 조각만 임베딩해 Qdrant 를 md 와 같게 맞춘다.

수집 방식(COLLECT_MODE)은 모른다.
"""

from __future__ import annotations

import functools
import json
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
            # BOM 이 남으면 첫 줄 헤딩이 헤딩으로 인식되지 않는다. clone 방식은 수집 때 뗄 수 없어 여기서 뗀다.
            return raw.decode(enc).removeprefix("\ufeff")
        except UnicodeDecodeError:
            continue
    return None


def md_files(root: Path) -> list[Path]:
    """root 아래 .md 파일. .git 디렉터리, 심링크, ._ 로 시작하는 macOS 메타데이터 파일은 뺀다.

    clone 방식이면 DOCS_DIR 에 리포가 통째로 있어 이것들이 섞인다. 심링크는 리포 밖을 가리킬 수 있다.
    """
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            f = Path(dirpath) / name
            if name.lower().endswith(".md") and not name.startswith("._") and not f.is_symlink():
                out.append(f)
    return sorted(out)


def load_dates(root: Path) -> dict[str, str]:
    """collect.py 가 .manifest.json 에 남긴 "리포/파일" → 마지막 커밋일. 없으면 비어 있다."""
    path = root / ".manifest.json"
    return json.loads(path.read_text(encoding="utf-8")).get("dates", {}) if path.exists() else {}


def main() -> int:
    root = Path(os.environ["DOCS_DIR"])
    db = store.client()

    # 수집이 "바뀐 것 없음"(종료 코드 3)으로 끝났으면 색인을 건너뛴다.
    # 지난 색인이 중간에 실패했으면 Qdrant 가 반쯤 맞춰진 채라, 끝까지 성공했다는 표시가 있을 때만 건너뛴다.
    # 표시에 설정 버전을 적어 두어, 버전을 바꾼 날에는 문서가 그대로여도 다시 맞춘다.
    done = root / ".indexed"
    if (
        os.environ.get("COLLECT_EXIT") == "3"
        and db.collection_exists(store.ALIAS)
        and done.exists()
        and done.read_text(encoding="utf-8") == store.VERSION
    ):
        print("바뀐 문서가 없어 색인을 건너뛴다", file=sys.stderr)
        return 0
    done.unlink(missing_ok=True)

    dates = load_dates(root)
    chunks: list[tuple[str, str]] = []
    skipped = 0
    for f in md_files(root):
        rel = f.relative_to(root).as_posix()
        text = read_md(f)
        if text is None:
            # 파일 하나 때문에 색인 전체가 멈추지 않게 건너뛴다
            print(f"  ! 인코딩을 알 수 없어 건너뜀: {rel}", file=sys.stderr)
            skipped += 1
            continue
        chunks.extend((rel, c) for c in chunk_markdown(text, rel, dates.get(rel, "")))
    # 비어 있으면 들어 있는 조각이 전부 "사라진 조각"이 되어 멀쩡한 색인이 비워진다.
    if not chunks:
        print(f"md 가 없다: {root}", file=sys.stderr)
        return 2

    # 모델(2.3GB)은 새로 임베딩할 조각이 있을 때만 올린다
    embedder = functools.cache(Embedder)
    added, removed, kept = store.sync(db, chunks, lambda texts: embedder().encode(texts))
    done.write_text(store.VERSION, encoding="utf-8")
    print(f"완료: {store.ALIAS} 새 조각 {added}개, 지운 조각 {removed}개, 그대로 {kept}개, 건너뛴 파일 {skipped}개", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
