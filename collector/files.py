"""DOCS_DIR 에 md 를 쓰고 지우며, 받은 파일을 .manifest.json 에 기록한다."""

from __future__ import annotations

import json
from pathlib import Path

# .md 로 끝나면 index.py 가 문서로 색인하므로 다른 확장자를 쓴다.
MANIFEST = ".manifest.json"


def load_manifest(root: Path) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """(리포 경로 → (파일 경로 → blob SHA), "리포/파일" → 마지막 커밋일). 처음 실행이면 둘 다 비어 있다.

    날짜 기록이 없던 옛 기록은 dates 가 빈 채로 읽힌다. 다음 수집이 파일을 다시 받지 않고 날짜만 채운다.
    """
    path = root / MANIFEST
    if not path.exists():
        return {}, {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if "files" not in data:
        return data, {}
    return data["files"], data.get("dates", {})


def save_manifest(root: Path, manifest: dict[str, dict[str, str]], dates: dict[str, str]) -> None:
    data = {"files": manifest, "dates": dates}
    (root / MANIFEST).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def write_doc(root: Path, repo: str, rel: str, raw: bytes) -> None:
    dest = root / repo / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    # BOM 이 남으면 첫 줄 헤딩이 헤딩으로 인식되지 않는다.
    dest.write_bytes(raw.removeprefix(b"\xef\xbb\xbf"))


def delete_doc(root: Path, repo: str, rel: str) -> None:
    (root / repo / rel).unlink(missing_ok=True)
