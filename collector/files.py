"""디스크 반영. manifest 파일의 읽기·쓰기도 여기 있다.

받은 바이트를 md 로 놓고, 지워진 것을 치우고, 상태를 기록한다.
소스도 RAG 도 모른다.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MANIFEST = ".manifest.json"


def _safe_rel(path: str) -> str | None:
    """서버가 준 경로를 그대로 이어붙이지 않는다.

    절대경로나 '..' 가 섞여 오면 DOCS_DIR 밖에 파일을 쓰게 된다. 한글·공백·이모지는
    그대로 통과시킨다 — blob SHA 로 받으므로 인코딩 문제가 없다.
    """
    p = Path(path)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        return None
    return p.as_posix()


def load_manifest(root: Path) -> dict[str, dict[str, str]]:
    """없거나 깨졌으면 빈 것으로 본다. 전량 재수집이 되고 삭제는 0건이다."""
    try:
        data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        repos = data["repos"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    out: dict[str, dict[str, str]] = {}
    for repo, body in repos.items():
        files = body.get("files") if isinstance(body, dict) else None
        if isinstance(files, dict):
            out[repo] = {str(k): str(v) for k, v in files.items()}
    return out


def save_manifest(root: Path, manifest: dict[str, dict[str, str]]) -> None:
    data = {"repos": {r: {"files": f} for r, f in sorted(manifest.items())}}
    tmp = root / f"{MANIFEST}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, root / MANIFEST)


def write_doc(root: Path, repo: str, rel: str, raw: bytes) -> bool:
    """받은 바이트를 md 로 저장한다. 디코드 실패면 False.

    utf-8-sig 로 읽어 BOM 을 떼고 utf-8 로 쓴다. BOM 이 남으면 첫 줄이 '\\ufeff# 제목'
    이 되어 chunk.py 의 헤딩 정규식에 안 걸리고, 문서 전체가 헤딩 없는 한 덩어리가
    되면서 브레드크럼을 잃는다.
    CRLF 는 그대로 둔다 — chunk.py 가 splitlines() 를 쓰므로 문제없고, 바꾸면 SHA 는
    같은데 내용이 다른 상태가 되어 디버깅이 어려워진다.
    """
    safe = _safe_rel(rel)
    if safe is None:
        return False
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False

    dest = root / repo / safe
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.name}.tmp")
    # 같은 디렉터리에 쓰고 바꿔치기한다. 중간에 죽어도 잘린 md 가 색인되지 않는다.
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, dest)
    return True


def delete_doc(root: Path, repo: str, rel: str) -> bool:
    """md 하나를 지우고 빈 디렉터리를 정리한다. 실패하면 False.

    실패를 알려야 하는 이유 — 호출자가 manifest 에서 키를 지우면 안 되기 때문이다.
    지우면 다음 실행에서 다시 시도하지 못하고 그 파일이 영구 고아가 된다.
    """
    safe = _safe_rel(rel)
    if safe is None:
        return False
    target = root / repo / safe
    try:
        target.unlink(missing_ok=True)
    except OSError as e:
        print(f"  ! 삭제 실패: {repo}/{safe} — {e}", file=sys.stderr)
        return False
    _prune(root, target.parent)
    return True


def _prune(root: Path, leaf: Path) -> None:
    """빈 디렉터리를 root 바로 아래까지만 거슬러 올라가며 지운다."""
    cur = leaf
    while cur != root and root in cur.parents:
        try:
            cur.rmdir()
        except OSError:
            return
        cur = cur.parent
