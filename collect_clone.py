"""진입점 1 의 clone 방식 — 리포를 이력까지 DOCS_DIR 에 git clone 해 두고, 이후에는 fetch 로 맞춘다.

collect.py 가 COLLECT_MODE=clone 일 때 부른다. 직접 실행해도 된다.
리포 목록만 collector/sources 에서 받고, 나머지는 git 이 한다. md 는 clone 안에 그대로 있다.

api 방식과 같은 원칙을 지킨다.
- 받기에 실패한 리포는 옛 clone 을 그대로 두고, 삭제 대상에서도 뺀다.
- 기록(.manifest.json)에 있는 clone 만 지운다.
- 리포 목록이 0개로 오면 멈춘다.
- 도중에 실패하면 기록을 저장하지 않는다.

종료 코드: 0 바뀐 것 있음, 1 일부 리포 실패, 2 시작하지 못함, 3 바뀐 것 없음.
모든 리포의 커밋 해시가 지난번과 같으면 3 이다.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from cloner import git, state
from collector.sources import github, gitlab

SOURCES = {"gitlab": gitlab, "github": github}


def main() -> int:
    src = SOURCES[os.environ.get("SOURCE", "gitlab")]
    root = Path(os.environ["DOCS_DIR"])
    root.mkdir(parents=True, exist_ok=True)
    try:
        heads, dates = state.load(root)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    before = (dict(heads), dict(dates))

    repos = src.list_repos()
    if not repos and heads:
        print("리포가 0개로 왔다. 토큰 권한을 확인한다", file=sys.stderr)
        return 2

    env = git.auth_env(*src.git_auth())
    failed = 0
    for repo in repos:
        if not repo.branch:
            continue
        dest = root / repo.path
        try:
            head = git.sync(dest, repo.url, repo.branch, env)
            if head != heads.get(repo.path):
                # 커밋이 바뀐 리포만 이력을 훑어 날짜를 다시 계산한다
                prefix = f"{repo.path}/"
                fresh = {prefix + p: d for p, d in git.md_dates(dest).items()}
                for key in [k for k in dates if k.startswith(prefix)]:
                    del dates[key]
                dates.update(fresh)
        except Exception as e:
            print(f"{repo.path}: 받기 실패 ({e})", file=sys.stderr)
            failed += 1
            continue
        moved = "그대로" if head == heads.get(repo.path) else "갱신"
        heads[repo.path] = head
        print(f"{repo.path}: {head[:8]} {moved}", file=sys.stderr)

    for path in state.vanished(heads, {r.path for r in repos}):
        shutil.rmtree(root / path, ignore_errors=True)
        del heads[path]
        for key in [k for k in dates if k.startswith(f"{path}/")]:
            del dates[key]
        print(f"{path}: 리포가 사라져 clone 을 지웠다", file=sys.stderr)

    state.save(root, heads, dates)
    if failed:
        return 1
    if (heads, dates) == before:
        print("바뀐 리포가 없다", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
