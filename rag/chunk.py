"""마크다운 문서 하나를 검색 단위 조각으로 자른다.

임베딩 모델도 Qdrant 도 import 하지 않는다. 덕분에 이 파일의 테스트는 모델 2.3GB 를
받지 않고, DB 를 띄우지 않고 돈다. 토큰 수가 아니라 글자 수로 자르는 것도 같은 이유다 —
토크나이저를 쓰면 모델에 묶인다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 코드펜스 여는/닫는 줄. ``` 또는 ~~~ 로 시작하며 앞에 공백이 3칸까지 허용된다.
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*)$")


@dataclass
class Chunk:
    doc_path: str
    chunk_index: int
    heading_path: list[str] = field(default_factory=list)
    text: str = ""


@dataclass
class _Section:
    heading_path: list[str]
    lines: list[str]


def _split_sections(text: str) -> list[_Section]:
    """헤더를 만날 때마다 새 섹션을 연다. 코드펜스 안의 '#' 은 헤더가 아니다."""
    sections: list[_Section] = []
    stack: list[str] = []  # 현재 위치의 헤딩 경로. 인덱스 = 레벨-1
    current = _Section(heading_path=[], lines=[])
    fence: str | None = None  # 열려 있는 펜스 마커. None 이면 코드블록 밖

    for line in text.splitlines():
        m_fence = _FENCE.match(line)
        if m_fence:
            marker = m_fence.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                # 닫는 펜스는 여는 것과 같은 문자이고 길이가 같거나 길어야 한다
                fence = None
            current.lines.append(line)
            continue

        if fence is None:
            m_head = _HEADING.match(line)
            if m_head:
                if current.lines:
                    sections.append(current)
                level = len(m_head.group(1))
                title = m_head.group(2).strip()
                stack = stack[: level - 1]
                # 레벨을 건너뛴 문서(h1 다음 h3)에서도 경로 길이를 맞춘다
                while len(stack) < level - 1:
                    stack.append("")
                stack.append(title)
                current = _Section(heading_path=list(stack), lines=[])
                continue

        current.lines.append(line)

    if current.lines:
        sections.append(current)
    return sections


def _split_long(lines: list[str], max_chars: int) -> list[str]:
    """섹션 본문을 빈 줄(단락) 경계로 나눈다. 펜스는 절대 중간에서 자르지 않는다."""
    blocks: list[str] = []  # 단락 또는 코드블록 하나
    buf: list[str] = []
    fence: str | None = None

    for line in lines:
        m_fence = _FENCE.match(line)
        if m_fence:
            marker = m_fence.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            buf.append(line)
            continue

        if fence is None and not line.strip():
            if buf:
                blocks.append("\n".join(buf))
                buf = []
            continue

        buf.append(line)

    if buf:
        blocks.append("\n".join(buf))

    # 단락을 max_chars 를 넘지 않는 선에서 다시 뭉친다
    out: list[str] = []
    cur = ""
    for block in blocks:
        if not cur:
            cur = block
        elif len(cur) + len(block) + 2 <= max_chars:
            cur = f"{cur}\n\n{block}"
        else:
            out.append(cur)
            cur = block
    if cur:
        out.append(cur)
    return out


def chunk_markdown(text: str, doc_path: str, max_chars: int = 1200) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in _split_sections(text):
        for body in _split_long(section.lines, max_chars):
            if not body.strip():
                continue
            # 브레드크럼. 조각만 떼어 놓으면 맥락이 없어 임베딩 품질이 떨어진다.
            crumb = " > ".join([doc_path, *(h for h in section.heading_path if h)])
            chunks.append(
                Chunk(
                    doc_path=doc_path,
                    chunk_index=len(chunks),
                    heading_path=[h for h in section.heading_path if h],
                    text=f"[{crumb}]\n{body}",
                )
            )
    return chunks
