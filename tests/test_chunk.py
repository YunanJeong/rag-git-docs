"""chunk.py 단위 테스트. 모델도 DB도 쓰지 않으므로 의존성 설치만으로 돈다."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.chunk import chunk_markdown  # noqa: E402

SAMPLES = Path(__file__).resolve().parent / "sample-docs"


def test_breadcrumb_prefix():
    md = "# 제목\n\n본문이다.\n"
    chunks = chunk_markdown(md, "a/b.md")
    assert len(chunks) == 1
    assert chunks[0].text.startswith("[a/b.md > 제목]\n")
    assert chunks[0].heading_path == ["제목"]


def test_nested_headings():
    md = "# 운영\n\n상위 본문.\n\n## 스케일링\n\n하위 본문.\n"
    chunks = chunk_markdown(md, "ops.md")
    assert [c.heading_path for c in chunks] == [["운영"], ["운영", "스케일링"]]
    assert chunks[1].text.startswith("[ops.md > 운영 > 스케일링]\n")


def test_hash_inside_code_fence_is_not_a_heading():
    md = "# 가이드\n\n```bash\n# 이건 셸 주석이다\necho hi\n```\n\n뒤 본문.\n"
    chunks = chunk_markdown(md, "g.md")
    # 펜스 안의 '#' 으로 섹션이 새로 열리면 안 된다
    assert all(c.heading_path == ["가이드"] for c in chunks)
    assert "# 이건 셸 주석이다" in "\n".join(c.text for c in chunks)


def test_code_fence_never_split():
    body = "\n".join(f"line {i}" for i in range(80))
    md = f"# T\n\n```\n{body}\n```\n"
    chunks = chunk_markdown(md, "c.md", max_chars=100)
    fenced = [c for c in chunks if "```" in c.text]
    assert len(fenced) == 1, "펜스가 여러 조각으로 쪼개졌다"
    assert fenced[0].text.count("```") == 2


def test_long_section_is_split_on_blank_lines():
    para = "가" * 300
    md = "# 긴섹션\n\n" + "\n\n".join([para] * 6) + "\n"
    chunks = chunk_markdown(md, "long.md", max_chars=700)
    assert len(chunks) > 1
    assert all(c.heading_path == ["긴섹션"] for c in chunks)
    # 모든 조각이 브레드크럼을 갖는다
    assert all(c.text.startswith("[long.md > 긴섹션]\n") for c in chunks)


def test_chunk_index_is_sequential():
    md = "# A\n\n본문A.\n\n# B\n\n본문B.\n\n# C\n\n본문C.\n"
    chunks = chunk_markdown(md, "x.md")
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_blank_chunks_dropped():
    md = "# 빈섹션\n\n\n\n# 내용있음\n\n본문.\n"
    chunks = chunk_markdown(md, "b.md")
    assert len(chunks) == 1
    assert chunks[0].heading_path == ["내용있음"]


def test_sample_docs_parse():
    files = sorted(SAMPLES.rglob("*.md"))
    assert files, "샘플 문서가 없다"
    for f in files:
        chunks = chunk_markdown(f.read_text(encoding="utf-8"), str(f.relative_to(SAMPLES)))
        assert chunks, f"{f} 에서 조각이 안 나왔다"
        assert all(c.text.strip() for c in chunks)
