"""소스가 내놓는 것의 정의. 벤더 이름이 나오지 않는다.

md 선별이 여기 있는 이유 — type/mode 값은 git 객체 모델을 그대로 노출한 것이라
GitLab 과 GitHub 가 글자까지 같다. 껍데기만 다르지 같은 git 이다.
"""

from __future__ import annotations

from dataclasses import dataclass

# blob 으로 오지만 내용이 파일이 아닌 것들
_NOT_A_FILE = ("120000", "160000")  # 심링크, 서브모듈


@dataclass
class Repo:
    """수집 대상 하나. id 는 소스가 뒤 호출에 쓰는 값이고 형태는 벤더마다 다르다."""

    id: str
    path: str
    default_branch: str | None = None


@dataclass
class Entry:
    path: str
    sha: str


def md_entries(items: list[dict], sha_key: str) -> list[Entry]:
    """트리 항목에서 실제로 내려받을 md 만 남긴다.

    SHA 필드 이름만 벤더가 다르다 (GitLab 은 "id", GitHub 은 "sha").
    """
    out: list[Entry] = []
    for item in items:
        if item.get("type") != "blob" or item.get("mode") in _NOT_A_FILE:
            continue
        path = item.get("path", "")
        if not path.lower().endswith(".md"):
            continue
        out.append(Entry(path=path, sha=item[sha_key]))
    return out
