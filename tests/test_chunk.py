import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from indexer.chunk import chunk_markdown  # noqa: E402


def test_breadcrumb_has_path_and_headings():
    chunks = chunk_markdown("# 배포\n\n## 롤백\n\n직전으로 되돌린다.\n", "a/b.md")
    assert chunks == ["[a/b.md > 배포 > 롤백]\n직전으로 되돌린다."]


def test_hash_inside_code_fence_is_not_a_heading():
    md = "# 실행\n\n```bash\n# 주석\nls\n```\n"
    chunks = chunk_markdown(md, "a.md")
    assert len(chunks) == 1 and "# 주석" in chunks[0]


def test_sibling_heading_replaces_previous():
    chunks = chunk_markdown("# A\n\n## B\n\nb\n\n## C\n\nc\n", "x.md")
    assert chunks[-1].startswith("[x.md > A > C]")
