"""GET 과 Link 헤더 페이지네이션. GitLab 과 GitHub 이 같은 방식을 쓴다."""

from __future__ import annotations

import json
import re
import urllib.request

_NEXT = re.compile(r'<([^>]+)>\s*;\s*rel="next"')


def get(url: str, headers: dict[str, str]) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read(), res.headers.get("Link", "")


def get_pages(url: str, headers: dict[str, str]) -> list[dict]:
    """rel="next" 를 따라가며 모든 페이지를 모은다."""
    out: list[dict] = []
    while url:
        body, link = get(url, headers)
        out.extend(json.loads(body))
        m = _NEXT.search(link)
        url = m.group(1) if m else ""
    return out
