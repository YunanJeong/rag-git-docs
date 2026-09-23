"""소스 계층에서 네트워크 없이 도는 부분만 본다.

md 선별과 Link 헤더 파싱 둘 다 GitLab·GitHub 공용이라, 여기서 깨지면 양쪽이 같이 깨진다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sources._http import parse_next_link  # noqa: E402
from sources.types import md_entries  # noqa: E402


def _blob(path, sha, mode="100644", key="id"):
    return {"type": "blob", "mode": mode, "path": path, key: sha}


def test_md_entries_skips_symlink():
    items = [_blob("docs/a.md", "aaa"), _blob("docs/link.md", "bbb", mode="120000")]
    paths = [e.path for e in md_entries(items, "id")]
    assert paths == ["docs/a.md"], f"심링크가 걸러지지 않았다: {paths}"


def test_md_entries_skips_submodule():
    items = [_blob("docs/a.md", "aaa"), _blob("vendor/sub.md", "bbb", mode="160000")]
    paths = [e.path for e in md_entries(items, "id")]
    assert paths == ["docs/a.md"], f"서브모듈이 걸러지지 않았다: {paths}"


def test_md_entries_skips_tree():
    items = [{"type": "tree", "mode": "040000", "path": "docs", "id": "ccc"}]
    assert md_entries(items, "id") == [], "디렉터리가 파일로 잡혔다"


def test_md_entries_skips_non_markdown():
    items = [_blob("a.png", "1"), _blob("b.txt", "2"), _blob("c.md", "3")]
    paths = [e.path for e in md_entries(items, "id")]
    assert paths == ["c.md"], f"md 가 아닌 파일이 들어왔다: {paths}"


def test_md_entries_accepts_uppercase_extension():
    paths = [e.path for e in md_entries([_blob("README.MD", "1")], "id")]
    assert paths == ["README.MD"], f"대문자 확장자를 놓쳤다: {paths}"


def test_md_entries_reads_github_sha_key():
    """GitLab 은 'id', GitHub 은 'sha'. 필드 이름만 다르고 판정은 같다."""
    items = [_blob("docs/a.md", "deadbeef", key="sha")]
    entries = md_entries(items, "sha")
    assert entries[0].sha == "deadbeef", f"GitHub SHA 필드를 못 읽었다: {entries}"


def test_parse_next_link_extracts_url():
    header = '<https://example.com/api?page=2>; rel="next", <https://example.com/api?page=9>; rel="last"'
    assert parse_next_link(header) == "https://example.com/api?page=2", "next URL 추출 실패"


def test_parse_next_link_returns_none_on_last_page():
    header = '<https://example.com/api?page=1>; rel="prev"'
    assert parse_next_link(header) is None, "next 가 없는데 URL 이 나왔다"


def test_parse_next_link_handles_missing_header():
    assert parse_next_link("") is None, "빈 헤더에서 None 이 아니다"
