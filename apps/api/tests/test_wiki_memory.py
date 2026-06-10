from datetime import datetime
from pathlib import Path

from hive_os_api import wiki_memory


def test_format_log_entry_plain():
    when = datetime(2026, 6, 9, 16, 42)
    line = wiki_memory.format_log_entry(when, "Iqbal", "Did the thing.")
    assert line == "- 16:42 · Iqbal — Did the thing."


def test_format_log_entry_with_task():
    when = datetime(2026, 6, 9, 16, 42)
    line = wiki_memory.format_log_entry(when, "Iqbal", "Did it.", task_title="Build login")
    assert line == "- 16:42 · Iqbal — Did it. ([[task: Build login]])"


def test_append_creates_file_with_heading(tmp_path: Path):
    root = tmp_path / "wiki"
    wiki_memory.append_log_entry(root, datetime(2026, 6, 9, 9, 0), "Iqbal", "First.")
    text = (root / "log.md").read_text(encoding="utf-8")
    assert "## 2026-06-09" in text
    assert "- 09:00 · Iqbal — First." in text


def test_append_newest_first_same_day(tmp_path: Path):
    root = tmp_path / "wiki"
    wiki_memory.append_log_entry(root, datetime(2026, 6, 9, 9, 0), "Iqbal", "Older.")
    wiki_memory.append_log_entry(root, datetime(2026, 6, 9, 10, 0), "Iqbal", "Newer.")
    lines = [l for l in (root / "log.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
    assert lines[0].endswith("Newer.")   # newest entry on top within the day
    assert lines[1].endswith("Older.")


def test_append_newest_day_on_top(tmp_path: Path):
    root = tmp_path / "wiki"
    wiki_memory.append_log_entry(root, datetime(2026, 6, 8, 9, 0), "Iqbal", "Yesterday.")
    wiki_memory.append_log_entry(root, datetime(2026, 6, 9, 9, 0), "Iqbal", "Today.")
    text = (root / "log.md").read_text(encoding="utf-8")
    assert text.index("## 2026-06-09") < text.index("## 2026-06-08")


def test_build_draft_prompt_lists_existing_notes():
    p = wiki_memory.build_draft_prompt([
        {"path": "auth/login.md", "content": "# Login\nUses OAuth.\n"},
        {"path": "log.md", "content": "# Project log\n"},
    ])
    assert "auth/login.md" in p
    assert "log.md" not in p            # the running log is not a reference note
    assert "json" in p.lower()          # instructs JSON output


def test_parse_note_draft_fenced_json():
    raw = 'Sure!\n```json\n{"title":"Caching","path":"perf/caching.md","body":"# Caching\\nUse Redis.","related":["perf/index.md"],"conflicts":["note says memcached"],"action":"new"}\n```\n'
    d = wiki_memory.parse_note_draft(raw)
    assert d["title"] == "Caching"
    assert d["path"] == "perf/caching.md"
    assert d["body"].startswith("# Caching")
    assert d["related"] == ["perf/index.md"]
    assert d["conflicts"] == ["note says memcached"]
    assert d["action"] == "new"
    assert d["unparsed"] is False


def test_parse_note_draft_fallback_on_garbage():
    d = wiki_memory.parse_note_draft("just some prose, no json here")
    assert d["unparsed"] is True
    assert d["body"] == "just some prose, no json here"
    assert d["action"] == "new"
    assert d["related"] == [] and d["conflicts"] == []


def test_rebuild_index_lists_notes_with_titles_and_summaries(tmp_path: Path):
    root = tmp_path / "wiki"
    (root / "auth").mkdir(parents=True)
    (root / "auth" / "jwt.md").write_text("# JWT migration\n\nMoved auth to JWT tokens.\n", encoding="utf-8")
    (root / "perf.md").write_text(
        '---\ndescription: Caching strategy for the API\n---\n# Perf\n\nbody\n', encoding="utf-8")
    wiki_memory.rebuild_index(root)
    idx = (root / "index.md").read_text(encoding="utf-8")
    assert "[JWT migration](auth/jwt.md)" in idx
    assert "Moved auth to JWT tokens." in idx
    assert "[Perf](perf.md)" in idx
    assert "Caching strategy for the API" in idx   # frontmatter description wins


def test_rebuild_index_excludes_log_index_and_graphify(tmp_path: Path):
    root = tmp_path / "wiki"
    root.mkdir()
    (root / "log.md").write_text("# Project log\n", encoding="utf-8")
    (root / "index.md").write_text("# Wiki index\n", encoding="utf-8")
    (root / "note.md").write_text("# Note\n\nKeep me.\n", encoding="utf-8")
    (root / "graphify-out").mkdir()
    (root / "graphify-out" / "GRAPH_REPORT.md").write_text("# Report\n\nnoise\n", encoding="utf-8")
    wiki_memory.rebuild_index(root)
    idx = (root / "index.md").read_text(encoding="utf-8")
    assert "note.md" in idx
    assert "log.md" not in idx
    assert "GRAPH_REPORT" not in idx
    assert "graphify-out" not in idx


def test_rebuild_index_title_falls_back_to_filename(tmp_path: Path):
    root = tmp_path / "wiki"
    root.mkdir()
    (root / "run-worker.md").write_text("no heading here, just prose.\n", encoding="utf-8")
    wiki_memory.rebuild_index(root)
    idx = (root / "index.md").read_text(encoding="utf-8")
    assert "[run worker](run-worker.md)" in idx          # slug humanized
    assert "no heading here, just prose." in idx


def test_rebuild_index_empty_wiki_writes_placeholder(tmp_path: Path):
    root = tmp_path / "wiki"
    root.mkdir()
    wiki_memory.rebuild_index(root)
    assert "_No notes yet._" in (root / "index.md").read_text(encoding="utf-8")


def test_rebuild_index_noop_when_dir_missing(tmp_path: Path):
    root = tmp_path / "nope"
    wiki_memory.rebuild_index(root)        # must not raise
    assert not (root / "index.md").exists()


def test_rebuild_index_handles_crlf_frontmatter(tmp_path: Path):
    root = tmp_path / "wiki"
    root.mkdir()
    (root / "win.md").write_text("---\r\ndescription: CRLF works\r\n---\r\n# Win\r\n", encoding="utf-8")
    wiki_memory.rebuild_index(root)
    idx = (root / "index.md").read_text(encoding="utf-8")
    assert "CRLF works" in idx
