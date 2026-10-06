"""md 문서를 헤딩 단위 조각으로 자른다.

조각 앞에 [파일 > 헤딩 | 수정 날짜] 한 줄을 붙인다. 조각만 떼어 놓으면 어느 문서의 어느 절인지
알 수 없어 검색 품질이 떨어진다. 날짜는 오래된 문서인지 판단하라고 붙인다.
"""

from __future__ import annotations

import re

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"^(```|~~~)")


def chunk_markdown(text: str, doc_path: str, date: str = "") -> list[str]:
    chunks: list[str] = []
    headings: list[str] = []
    body: list[str] = []
    in_fence = False
    suffix = f" | 수정 {date}" if date else ""

    def flush() -> None:
        if "".join(body).strip():
            crumb = " > ".join([doc_path, *headings])
            chunks.append(f"[{crumb}{suffix}]\n" + "\n".join(body).strip())
        body.clear()

    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            # 코드블록 안의 # 주석은 헤딩이 아니다
            flush()
            level = len(m.group(1))
            headings[level - 1 :] = [m.group(2).strip()]
        else:
            body.append(line)
    flush()
    return chunks
