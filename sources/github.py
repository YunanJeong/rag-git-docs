"""GitHub. GitLab 과 흐름은 같고 URL·필드·페이지네이션만 다르다.

공개 계정이라도 토큰이 필요하다. 인증 없이는 시간당 60회라 리포 몇 개에서 막힌다.
"""

from __future__ import annotations

import os
import urllib.parse

from sources._http import get, get_json, get_pages
from sources.types import Entry, Repo, md_entries

NAME = "github"
REQUIRED_ENV = ("GITHUB_TOKEN", "GITHUB_OWNER")

def _conf() -> tuple[str, str, dict[str, str]]:
    """GITHUB_API 는 Enterprise Server 용이다. 그쪽은 https://<호스트>/api/v3 형태다."""
    api = os.environ.get("GITHUB_API", "https://api.github.com").rstrip("/")
    owner = urllib.parse.quote(os.environ.get("GITHUB_OWNER", ""), safe="")
    headers = {
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    return api, owner, headers


def check() -> str:
    api, owner, headers = _conf()
    get(f"{api}/users/{owner}", headers)
    return os.environ.get("GITHUB_OWNER", "")


def list_repos() -> list[Repo]:
    """계정의 공개 리포 목록.

    GitLab 과 달리 archived 를 서버에서 못 거른다. 페이지를 전부 모은 뒤에 거르므로
    페이지 경계는 영향받지 않는다. fork 도 뺀다 — 남의 문서를 내 것으로 색인하게 된다.
    """
    api, owner, headers = _conf()
    url = f"{api}/users/{owner}/repos?per_page=100&type=owner&sort=full_name"
    return [
        Repo(id=r["full_name"], path=r["full_name"], default_branch=r.get("default_branch"))
        for r in get_pages(url, headers)
        if not r.get("archived") and not r.get("fork")
    ]


def list_md(repo: Repo) -> list[Entry]:
    """트리는 한 번에 온다. 페이지네이션이 없는 대신 잘릴 수 있다.

    GitHub 은 트리가 너무 크면 truncated=true 를 붙여 앞부분만 준다. 이걸 안 보면
    "파일이 사라졌다" 로 읽혀 멀쩡한 문서가 삭제 대상이 된다.
    """
    api, _owner, headers = _conf()
    ref = urllib.parse.quote(repo.default_branch or "", safe="")
    data = get_json(f"{api}/repos/{repo.id}/git/trees/{ref}?recursive=1", headers)
    if data.get("truncated"):
        raise RuntimeError("트리가 잘려서 왔다(truncated). 이 리포는 건너뛴다")
    return md_entries(data.get("tree", []), "sha")


def fetch(repo: Repo, sha: str) -> bytes:
    """blob 을 raw 로 받는다. Accept 를 안 바꾸면 base64 가 든 JSON 이 온다."""
    api, _owner, headers = _conf()
    raw = {**headers, "Accept": "application/vnd.github.raw"}
    body, _link = get(f"{api}/repos/{repo.id}/git/blobs/{sha}", raw)
    return body
