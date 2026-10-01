"""GitLab 그룹과 하위 그룹의 리포에서 md 를 받는다."""

from __future__ import annotations

import os
import urllib.parse

from sources._http import get, get_pages
from sources.types import Repo, md_files


def _api() -> tuple[str, dict[str, str]]:
    base = os.environ.get("GITLAB_URL", "https://gitlab.com").rstrip("/")
    return f"{base}/api/v4", {"PRIVATE-TOKEN": os.environ["GITLAB_TOKEN"]}


def list_repos() -> list[Repo]:
    api, headers = _api()
    group = urllib.parse.quote(os.environ["GITLAB_GROUP"], safe="")
    url = f"{api}/groups/{group}/projects?include_subgroups=true&archived=false&per_page=100"
    return [
        Repo(str(p["id"]), p["path_with_namespace"], p.get("default_branch"))
        for p in get_pages(url, headers)
    ]


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
