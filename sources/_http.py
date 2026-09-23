"""HTTP GET, 재시도, Link 페이지네이션.

GitLab 과 GitHub 가 같은 RFC 5988 Link 헤더를 쓰기 때문에 이 파일이 공유된다.
어느 벤더인지 모르고, 헤더 dict 를 받아서 그대로 보낸다.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

TIMEOUT = 30
RETRY_DELAYS = (1, 2, 4)

_NEXT = re.compile(r'<([^>]+)>\s*;\s*rel="next"')


def parse_next_link(link_header: str) -> str | None:
    m = _NEXT.search(link_header or "")
    return m.group(1) if m else None


def get(url: str, headers: dict[str, str]) -> tuple[bytes, str]:
    """(본문, Link 헤더). 429 와 5xx 만 재시도한다.

    나머지 4xx 는 기다려도 같은 답이 온다. 404 는 특히 그렇다 — 목록을 받은 뒤
    리포가 지워지는 경쟁 상태라 다음 실행에서 목록에 없는 것으로 정리된다.
    """
    req = urllib.request.Request(url, headers=headers)
    last: Exception = RuntimeError(url)
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
                return res.read(), res.headers.get("Link", "")
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
            last = e
        except urllib.error.URLError as e:
            last = e
        if attempt < len(RETRY_DELAYS):
            time.sleep(RETRY_DELAYS[attempt])
    raise last


def get_json(url: str, headers: dict[str, str]):
    body, _ = get(url, headers)
    return json.loads(body)


def get_pages(url: str, headers: dict[str, str]) -> list[dict]:
    """rel="next" 를 따라가며 전부 모은다.

    x-total 을 보지 않는다 — GitLab 트리 API 가 1000 에 고정된 값을 주는 사례가 있다.
    방문한 URL 을 기억해 같은 페이지가 또 오면 멈춘다. next 링크를 잘못 주는 경우가
    실재해서, 이게 없으면 배치가 밤새 같은 페이지를 돈다.
    """
    out: list[dict] = []
    seen: set[str] = set()
    nxt: str | None = url
    while nxt and nxt not in seen:
        seen.add(nxt)
        body, link = get(nxt, headers)
        page = json.loads(body)
        if not page:
            break
        out.extend(page)
        nxt = parse_next_link(link)
    return out
