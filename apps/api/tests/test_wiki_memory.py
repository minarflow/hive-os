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
