"""GitLab. URL 모양과 필드 이름만 안다. 자기 환경변수는 자기가 읽는다."""

from __future__ import annotations

import os
import urllib.parse

from sources._http import get, get_pages
from sources.types import Entry, Repo, md_entries

NAME = "gitlab"
REQUIRED_ENV = ("GITLAB_TOKEN", "GITLAB_GROUP")


def _conf() -> tuple[str, str, dict[str, str]]:
    token = os.environ.get("GITLAB_TOKEN", "")
    group = urllib.parse.quote(os.environ.get("GITLAB_GROUP", ""), safe="")
    base = os.environ.get("GITLAB_URL", "https://gitlab.com").rstrip("/")
    return base, group, {"PRIVATE-TOKEN": token}


def check() -> str:
    """디스크를 건드리기 전에 토큰과 대상을 확인하고, 사람이 읽을 대상 이름을 돌려준다.

    여기서 안 걸러지면 모든 리포가 실패하고, 최악의 경우 "대상 리포 0개" 로 읽혀
    삭제 로직이 돈다.
    """
    base, group, headers = _conf()
    get(f"{base}/api/v4/groups/{group}", headers)
    return f"{os.environ.get('GITLAB_GROUP', '')} (하위 그룹 포함)"


def list_repos() -> list[Repo]:
    """그룹의 프로젝트 목록. 하위 그룹까지 포함한다.

    archived=false 를 서버에서 건다. 받아와서 거르면 페이지마다 개수가 달라져
    keyset 경계가 어긋난다.
    """
    base, group, headers = _conf()
    url = (
        f"{base}/api/v4/groups/{group}/projects"
        "?include_subgroups=true&archived=false&per_page=100&order_by=id&sort=asc"
    )
    return [
        Repo(id=str(p["id"]), path=p["path_with_namespace"], default_branch=p.get("default_branch"))
        for p in get_pages(url, headers)
    ]


def list_md(repo: Repo) -> list[Entry]:
    base, _, headers = _conf()
    ref = urllib.parse.quote(repo.default_branch or "", safe="")
    url = (
        f"{base}/api/v4/projects/{repo.id}/repository/tree"
        f"?ref={ref}&recursive=true&pagination=keyset&per_page=100"
    )
    return md_entries(get_pages(url, headers), "id")


def fetch(repo: Repo, sha: str) -> bytes:
    """경로가 아니라 blob SHA 로 받는다.

    files/:path/raw 는 경로를 URL 인코딩해야 해서 한글·공백·'#' 이 든 경로에서
    사고가 난다. SHA 는 16진수라 그 문제가 없다.
    """
    base, _, headers = _conf()
    body, _link = get(f"{base}/api/v4/projects/{repo.id}/repository/blobs/{sha}/raw", headers)
    return body
