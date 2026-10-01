"""진입점 1 — 소스의 md 를 DOCS_DIR 로 받는다. 두 번째 실행부터는 바뀐 것만 받는다.

도중에 실패하면 기록을 저장하지 않고 끝난다. 다음 실행이 같은 작업을 다시 한다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from collector.files import delete_doc, load_manifest, save_manifest, write_doc
from collector.manifest import changed, deleted, vanished
from sources import github, gitlab

SOURCES = {"gitlab": gitlab, "github": github}


def main() -> int:
    src = SOURCES[os.environ.get("SOURCE", "gitlab")]
    root = Path(os.environ["DOCS_DIR"])
    root.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(root)

    repos = src.list_repos()
    # 0개로 오면 모든 리포가 사라진 것으로 판정돼 전부 지워진다. 권한 문제일 때가 많다.
    if not repos and manifest:
        print("리포가 0개로 왔다. 토큰 권한을 확인한다", file=sys.stderr)
        return 2

    failed = 0
    for repo in repos:
        if not repo.branch:
            continue
        try:
            live = src.list_md(repo)
        except Exception as e:
            # 조회에 실패한 리포는 건드리지 않는다. 옛 파일과 기록이 그대로 남는다.
            print(f"{repo.path}: 목록 조회 실패 ({e})", file=sys.stderr)
            failed += 1
            continue
        known = manifest.get(repo.path, {})
        new = changed(known, live)
        for path in new:
            write_doc(root, repo.path, path, src.fetch(repo, live[path]))
        for path in deleted(known, live):
            delete_doc(root, repo.path, path)
        manifest[repo.path] = live
        print(f"{repo.path}: md {len(live)}개, 새로 받음 {len(new)}개", file=sys.stderr)

    for path in vanished(manifest, {r.path for r in repos}):
        for rel in manifest.pop(path):
            delete_doc(root, path, rel)
        print(f"{path}: 리포가 사라져 문서를 지웠다", file=sys.stderr)

    save_manifest(root, manifest)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
