"""진입점 1 — 소스의 리포에서 문서를 DOCS_DIR 로 모은다. 방식은 COLLECT_MODE 로 고른다.

  api   (기본) md 만 API 로 받는다                        → collect_api.py, collector/
  clone        리포를 이력까지 통째로 git clone 해 둔다    → collect_clone.py, cloner/

어느 방식이든 index.py 와의 약속은 같다. DOCS_DIR 아래 <그룹>/<리포>/<리포 안 경로> 에 md 가 있고,
.manifest.json 의 dates 에 문서별 마지막 커밋일이 있다. 두 방식은 같은 DOCS_DIR 을 쓰지 않는다.

종료 코드: 0 바뀐 것 있음, 1 일부 리포 실패, 2 시작하지 못함, 3 바뀐 것 없음.
3 이면 색인을 다시 할 필요가 없다.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    mode = os.environ.get("COLLECT_MODE", "api")
    if mode == "api":
        from collect_api import main as run
    elif mode == "clone":
        from collect_clone import main as run
    else:
        print(f"COLLECT_MODE 는 api 또는 clone 이다: {mode}", file=sys.stderr)
        return 2
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
