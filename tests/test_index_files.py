import os
import sys
from pathlib import Path

from qdrant_client import QdrantClient, models

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import index  # noqa: E402
from index import md_files, read_md  # noqa: E402
from indexer import store  # noqa: E402


class FakeEmbedder:
    def encode(self, texts):
        return [{"dense": [1.0] + [0.0] * 1023, "sparse": models.SparseVector(indices=[1], values=[1.0])} for _ in texts]


def test_skip_only_after_a_finished_run(tmp_path, monkeypatch):
    (tmp_path / "a.md").write_text("# t\n본문\n")
    db = QdrantClient(":memory:")
    monkeypatch.setattr(store, "ALIAS", "docs")
    monkeypatch.setattr(index.store, "client", lambda: db)
    monkeypatch.setattr(index, "Embedder", FakeEmbedder)
    monkeypatch.setenv("DOCS_DIR", str(tmp_path))
    monkeypatch.setenv("COLLECT_EXIT", "3")

    # 끝까지 성공한 표시가 없으면 "바뀐 것 없음" 이어도 색인한다
    assert index.main() == 0 and db.count("docs").count == 1
    assert (tmp_path / ".indexed").read_text() == store.VERSION

    # 표시가 있으면 건너뛴다
    (tmp_path / "a.md").write_text("# t\n고침\n")
    index.main()
    assert db.scroll("docs", with_payload=True)[0][0].payload["text"].endswith("본문")

    # 설정 버전이 바뀌었으면 표시가 있어도 다시 맞춘다
    monkeypatch.setattr(store, "VERSION", "다른-모델")
    index.main()
    assert db.scroll("docs", with_payload=True)[0][0].payload["text"].endswith("고침")


def test_md_files_skips_git_symlink_and_macos_meta(tmp_path):
    (tmp_path / "g/r/.git").mkdir(parents=True)
    (tmp_path / "g/r/.git/x.md").write_text("x")
    (tmp_path / "g/r/README.MD").write_text("# a")
    (tmp_path / "g/r/._README.md").write_text("meta")
    os.symlink("/etc/hostname", tmp_path / "g/r/link.md")
    assert [p.relative_to(tmp_path).as_posix() for p in md_files(tmp_path)] == ["g/r/README.MD"]


def test_read_md_strips_bom(tmp_path):
    f = tmp_path / "a.md"
    f.write_bytes(b"\xef\xbb\xbf# t\n")
    assert read_md(f) == "# t\n"
