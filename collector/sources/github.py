"""GitHub 계정이나 조직의 리포에서 md 를 받는다."""

from __future__ import annotations

import json
import os
import urllib.parse

from collector.sources._http import get, get_pages
from collector.sources.types import Repo, md_files


def _api() -> tuple[str, dict[str, str]]:
    api = os.environ.get("GITHUB_API", "https://api.github.com").rstrip("/")
    headers = {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }
    return api, headers


def list_repos() -> list[Repo]:
    api, headers = _api()
    owner = urllib.parse.quote(os.environ["GITHUB_OWNER"], safe="")
    repos = get_pages(f"{api}/users/{owner}/repos?per_page=100&type=owner", headers)
    # archived 는 서버에서 거를 수 없어 여기서 거른다. fork 는 남의 문서라 뺀다.
    return [
        Repo(r["full_name"], r["full_name"], r.get("default_branch"))
        for r in repos
        if not r["archived"] and not r["fork"]
    ]


def list_md(repo: Repo) -> dict[str, str]:
    api, headers = _api()
    ref = urllib.parse.quote(repo.branch, safe="")
    data = json.loads(get(f"{api}/repos/{repo.id}/git/trees/{ref}?recursive=1", headers)[0])
    # 트리가 너무 크면 앞부분만 온다. 그대로 쓰면 나머지 파일이 지워진 것으로 판정된다.
    if data["truncated"]:
        raise RuntimeError("트리가 잘려서 왔다(truncated)")
    return md_files(data["tree"], "sha")


def fetch(repo: Repo, sha: str) -> bytes:
    # Accept 를 raw 로 바꾸지 않으면 base64 가 든 JSON 이 온다.
    api, headers = _api()
    raw = {**headers, "Accept": "application/vnd.github.raw"}
    return get(f"{api}/repos/{repo.id}/git/blobs/{sha}", raw)[0]
