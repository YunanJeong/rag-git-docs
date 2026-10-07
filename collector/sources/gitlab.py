"""GitLab 그룹과 하위 그룹의 리포에서 md 를 받는다."""

from __future__ import annotations

import json
import os
import urllib.parse

from collector.sources._http import get, get_pages
from collector.sources.types import Repo, md_files


def _api() -> tuple[str, dict[str, str]]:
    base = os.environ.get("GITLAB_URL", "https://gitlab.com").rstrip("/")
    return f"{base}/api/v4", {"PRIVATE-TOKEN": os.environ["GITLAB_TOKEN"]}


def list_repos() -> list[Repo]:
    api, headers = _api()
    group = urllib.parse.quote(os.environ["GITLAB_GROUP"], safe="")
    url = f"{api}/groups/{group}/projects?include_subgroups=true&archived=false&per_page=100"
    return [
        Repo(str(p["id"]), p["path_with_namespace"], p.get("default_branch"), p["http_url_to_repo"])
        for p in get_pages(url, headers)
    ]


def git_auth() -> tuple[str, str]:
    """git 이 HTTPS 로 받을 때 쓸 (사용자 이름, 비밀번호). 토큰에는 read_repository 스코프가 필요하다."""
    return "oauth2", os.environ["GITLAB_TOKEN"]


def list_md(repo: Repo) -> dict[str, str]:
    api, headers = _api()
    ref = urllib.parse.quote(repo.branch, safe="")
    url = (
        f"{api}/projects/{repo.id}/repository/tree"
        f"?ref={ref}&recursive=true&per_page=100&pagination=keyset"
    )
    return md_files(get_pages(url, headers), "id")


def fetch(repo: Repo, sha: str) -> bytes:
    # 경로 대신 blob SHA 로 받는다. 경로를 URL 인코딩하면 한글이나 공백에서 틀리기 쉽다.
    api, headers = _api()
    return get(f"{api}/projects/{repo.id}/repository/blobs/{sha}/raw", headers)[0]


def last_commit_date(repo: Repo, path: str) -> str:
    """파일을 마지막으로 바꾼 커밋의 날짜(YYYY-MM-DD). 기록이 없으면 빈 문자열."""
    api, headers = _api()
    ref = urllib.parse.quote(repo.branch, safe="")
    p = urllib.parse.quote(path, safe="")
    commits = json.loads(get(f"{api}/projects/{repo.id}/repository/commits?ref_name={ref}&path={p}&per_page=1", headers)[0])
    return commits[0]["committed_date"][:10] if commits else ""
