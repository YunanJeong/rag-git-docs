"""DOCS_DIR 에 md 를 쓰고 지우며, 받은 파일을 .manifest.json 에 기록한다."""

from __future__ import annotations

import json
from pathlib import Path

# .md 로 끝나면 index.py 가 문서로 색인하므로 다른 확장자를 쓴다.
MANIFEST = ".manifest.json"


def load_manifest(root: Path) -> dict[str, dict[str, str]]:
    """리포 경로 → (파일 경로 → blob SHA). 처음 실행이면 비어 있다."""
    path = root / MANIFEST
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_manifest(root: Path, manifest: dict[str, dict[str, str]]) -> None:
    (root / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


def write_doc(root: Path, repo: str, rel: str, raw: bytes) -> None:
    dest = root / repo / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    # BOM 이 남으면 첫 줄 헤딩이 헤딩으로 인식되지 않는다.
    dest.write_bytes(raw.removeprefix(b"\xef\xbb\xbf"))


def delete_doc(root: Path, repo: str, rel: str) -> None:
    (root / repo / rel).unlink(missing_ok=True)
