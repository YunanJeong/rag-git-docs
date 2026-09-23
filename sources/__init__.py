"""소스 하나를 골라 돌려준다.

소스 모듈은 check() / list_repos() / list_md(repo) / fetch(repo, sha) 네 함수와
NAME, REQUIRED_ENV 를 내놓는다. 구현체가 둘뿐이라 ABC 도 Protocol 도 두지 않는다.
"""

from __future__ import annotations

import os

from sources import github, gitlab

_SOURCES = {gitlab.NAME: gitlab, github.NAME: github}


def load(name: str):
    """이름으로 소스 모듈을 고른다. 환경변수가 비어 있으면 여기서 멈춘다."""
    src = _SOURCES.get(name)
    if src is None:
        raise KeyError(f"모르는 소스: {name} (가능한 값: {', '.join(sorted(_SOURCES))})")
    missing = [k for k in src.REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise KeyError(f"{name} 에 필요한 환경변수가 없다: {', '.join(missing)}")
    return src
