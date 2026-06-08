from hive_os_api.runner_specs import runner_spec, RUNNER_SPECS


def test_hermes_spec():
    s = runner_spec("hermes")
    assert s.spawn_argv[:2] == ["hermes", "acp"]
    assert s.home_env == "HERMES_HOME"


def test_claude_code_spec():
    s = runner_spec("claude-code")
    assert "claude-agent-acp" in " ".join(s.spawn_argv)
    assert s.home_env == "CLAUDE_CONFIG_DIR"
    assert s.binary == "claude"


def test_unknown_runner_falls_back_to_hermes():
    assert runner_spec("nope").id == "hermes"


def test_registry_has_expected_runners():
    assert set(["hermes", "claude-code"]).issubset(RUNNER_SPECS.keys())


def test_codex_spec():
    from hive_os_api.runner_specs import runner_spec
    s = runner_spec("codex")
    assert "codex-acp" in " ".join(s.spawn_argv)
    assert s.home_env == "CODEX_HOME"
    assert s.binary == "codex"
