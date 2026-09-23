"""진입점 1 — 소스의 md 를 DOCS_DIR 로 모은다.

sources 와 collector 를 조립하기만 한다. 어느 벤더인지 모르고 SOURCE 와 DOCS_DIR
두 개만 안다. 벤더 환경변수는 각 소스 모듈이 자기 것을 읽는다.

blob SHA 를 manifest 에 기억해 바뀐 것만 받는다. 아끼는 것은 API 트래픽이고,
색인(index.py)은 여전히 전량이다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import sources
from collector.files import delete_doc, load_manifest, save_manifest, write_doc
from collector.manifest import changed, deleted, vanished


def main() -> int:
    docs_dir = os.environ.get("DOCS_DIR")
    if not docs_dir:
        print("환경변수 DOCS_DIR 이 필요하다", file=sys.stderr)
        return 2
    try:
        src = sources.load(os.environ.get("SOURCE", "gitlab"))
    except KeyError as e:
        # KeyError 는 str() 하면 따옴표가 붙는다. 메시지만 꺼낸다
        print(e.args[0], file=sys.stderr)
        return 2

    excluded = {x.strip() for x in os.environ.get("EXCLUDE_REPOS", "").split(",") if x.strip()}
    root = Path(docs_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    # 디스크를 건드리기 전에 확인한다. 여기서 안 걸리면 전 리포가 실패하고,
    # 최악의 경우 "대상 리포 0개" 로 읽혀 삭제 로직이 돈다.
    try:
        target = src.check()
        print(f"리포 목록 조회: {target}", file=sys.stderr)
        repos = src.list_repos()
    except Exception as e:
        print(f"대상 조회 실패: {e}", file=sys.stderr)
        return 2

    targets = [r for r in repos if r.path not in excluded]
    print(f"리포 {len(targets)}개, 제외 {len(repos) - len(targets)}개\n", file=sys.stderr)

    manifest = load_manifest(root)
    failed: list[str] = []
    active: set[str] = set()
    n_written = n_deleted = 0

    for repo in targets:
        # 조회 성공 여부와 무관하게 대상이었던 리포는 active 에 넣는다.
        # 넣지 않으면 일시 장애가 "리포가 사라졌다" 로 읽혀 문서가 통째로 날아간다.
        active.add(repo.path)
        known = manifest.get(repo.path, {})

        if not repo.default_branch:
            print(f"{repo.path}\n  ! 빈 리포, 건너뛴다", file=sys.stderr)
            continue

        print(f"{repo.path} ({repo.default_branch})", file=sys.stderr)
        try:
            entries = src.list_md(repo)
        except Exception as e:
            print(f"  ! 목록 조회 실패({e}), 건너뛴다", file=sys.stderr)
            failed.append(repo.path)
            continue

        live = {e.path: e.sha for e in entries}
        to_get = changed(known, live)
        to_del = deleted(known, live)
        print(f"  md {len(live)}개, 변경 {len(to_get)}개", file=sys.stderr)

        current = dict(known)
        for path in to_get:
            try:
                raw = src.fetch(repo, live[path])
            except Exception as e:
                print(f"  ! 내려받기 실패: {path} — {e}", file=sys.stderr)
                failed.append(f"{repo.path}/{path}")
                continue
            if not write_doc(root, repo.path, path, raw):
                print(f"  ! 디코드 실패, 건너뜀: {path}", file=sys.stderr)
                failed.append(f"{repo.path}/{path}")
                continue
            current[path] = live[path]
            n_written += 1
            print(f"  {path}", file=sys.stderr)

        for path in to_del:
            if not delete_doc(root, repo.path, path):
                failed.append(f"{repo.path}/{path}")
                continue
            # 지우는 데 성공했을 때만 manifest 에서 뺀다. 실패한 걸 빼면 다음 실행에서
            # 다시 시도하지 못하고 그 파일이 영구 고아가 된다.
            current.pop(path, None)
            n_deleted += 1
        if to_del:
            print(f"  삭제 {len(to_del)}개: {', '.join(to_del)}", file=sys.stderr)

        manifest[repo.path] = current

    for repo_path in vanished(manifest, active):
        left = dict(manifest[repo_path])
        for path in sorted(manifest[repo_path]):
            if not delete_doc(root, repo_path, path):
                failed.append(f"{repo_path}/{path}")
                continue
            left.pop(path, None)
            n_deleted += 1
        print(f"\n리포 삭제: {repo_path} (md {len(manifest[repo_path])}개)", file=sys.stderr)
        if left:
            manifest[repo_path] = left
        else:
            manifest.pop(repo_path, None)

    save_manifest(root, manifest)

    total = sum(len(f) for f in manifest.values())
    print(
        f"\n완료. 파일 {total}개, 새로 받음 {n_written}개, "
        f"삭제 {n_deleted}개, 실패 {len(failed)}개",
        file=sys.stderr,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
