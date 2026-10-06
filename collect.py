"""진입점 1 — 소스의 md 를 DOCS_DIR 로 받는다. 두 번째 실행부터는 바뀐 것만 받는다.

도중에 실패하면 기록을 저장하지 않고 끝난다. 다음 실행이 같은 작업을 다시 한다.

종료 코드: 0 바뀐 것 있음, 1 일부 리포 조회 실패, 2 시작하지 못함, 3 바뀐 것 없음.
3 이면 색인을 다시 할 필요가 없다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from collector.files import delete_doc, load_manifest, save_manifest, write_doc
from collector.manifest import changed, deleted, vanished
from collector.sources import github, gitlab

SOURCES = {"gitlab": gitlab, "github": github}


def main() -> int:
    src = SOURCES[os.environ.get("SOURCE", "gitlab")]
    root = Path(os.environ["DOCS_DIR"])
    root.mkdir(parents=True, exist_ok=True)
    manifest, dates = load_manifest(root)
    # 끝에서 비교해 바뀐 게 있는지 본다. 경로·내용 해시·날짜가 모두 같으면 바뀐 것이 없다.
    before = ({repo: dict(files) for repo, files in manifest.items()}, dict(dates))

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
        # 새로 받은 파일과, 날짜를 기록하기 전에 받아 둔 파일만 날짜를 조회한다
        for path in live:
            key = f"{repo.path}/{path}"
            if path in new or key not in dates:
                dates[key] = src.last_commit_date(repo, path)
        for path in deleted(known, live):
            delete_doc(root, repo.path, path)
            dates.pop(f"{repo.path}/{path}", None)
        manifest[repo.path] = live
        print(f"{repo.path}: md {len(live)}개, 새로 받음 {len(new)}개", file=sys.stderr)

    for path in vanished(manifest, {r.path for r in repos}):
        for rel in manifest.pop(path):
            delete_doc(root, path, rel)
            dates.pop(f"{path}/{rel}", None)
        print(f"{path}: 리포가 사라져 문서를 지웠다", file=sys.stderr)

    save_manifest(root, manifest, dates)
    if failed:
        return 1
    if (manifest, dates) == before:
        print("바뀐 문서가 없다", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
