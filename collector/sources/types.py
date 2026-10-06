"""두 소스가 함께 쓰는 것. 트리의 type 과 mode 는 git 값 그대로라 GitLab 과 GitHub 이 같다."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Repo:
    id: str  # 소스가 API 호출에 쓰는 값
    path: str  # DOCS_DIR 아래 저장 경로
    branch: str | None  # 빈 리포면 None


def md_files(tree: list[dict], sha_key: str) -> dict[str, str]:
    """트리에서 .md 파일만 골라 경로와 blob SHA 로 돌려준다. 심링크와 서브모듈은 뺀다.

    이름이 ._ 로 시작하는 파일도 뺀다. macOS 가 복사할 때 만드는 메타데이터 파일이라
    확장자만 .md 이고 내용은 문서가 아니다.
    """
    return {
        t["path"]: t[sha_key]
        for t in tree
        if t["type"] == "blob"
        and t.get("mode") not in ("120000", "160000")
        and t["path"].lower().endswith(".md")
        and not t["path"].rsplit("/", 1)[-1].startswith("._")
    }
