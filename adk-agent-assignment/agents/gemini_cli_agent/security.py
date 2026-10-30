"""Input validation and hardened argument/environment construction for Agent B.

Nothing here runs a process; it only builds safe argv lists and environments, so it is
fully unit-testable.  All subprocesses use argv lists - never ``shell=True``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from adk_shared.config import env_bool, env_str

DEFAULT_ALLOWED_HOSTS = ("github.com", "gitlab.com")
_SEGMENT = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,99})$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# Environment variables the Gemini CLI subprocess may see.  Everything else (DB passwords,
# GitHub tokens, cloud credentials for other systems) is withheld from a process that
# reads untrusted repository content.
GEMINI_ENV_ALLOWLIST = (
    "PATH", "HOME", "LANG", "LC_ALL", "TERM", "TMPDIR", "USER", "SHELL",
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_GENAI_USE_GCA",
    "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS",
    "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "NODE_EXTRA_CA_CERTS",
)
GIT_ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "TMPDIR", "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY")


class UnsafeInputError(ValueError):
    """Raised when user/model supplied input fails validation."""


@dataclass(frozen=True)
class RepoRef:
    host: str
    owner: str
    name: str

    @property
    def clone_url(self) -> str:
        return f"https://{self.host}/{self.owner}/{self.name}.git"

    @property
    def display(self) -> str:
        return f"https://{self.host}/{self.owner}/{self.name}"


def allowed_hosts() -> tuple[str, ...]:
    raw = env_str("GEMINI_CLI_ALLOWED_HOSTS")
    if not raw:
        return DEFAULT_ALLOWED_HOSTS
    return tuple(h.strip().lower() for h in raw.split(",") if h.strip())


def validate_repo_url(url: str) -> RepoRef:
    """Accept only ``https://<allowed-host>/<owner>/<repo>[.git][/]``.

    Rejects other schemes (ssh, git, file, ext::), embedded credentials, ports, query
    strings, fragments, path traversal, option-like segments and non-allow-listed hosts
    (which also prevents SSRF to internal addresses).
    """
    if not isinstance(url, str) or not url.strip():
        raise UnsafeInputError("Repository URL is required.")
    url = url.strip()
    if len(url) > 300 or any(c.isspace() or ord(c) < 32 for c in url):
        raise UnsafeInputError("Repository URL contains whitespace/control characters.")
    if "\\" in url or "%" in url:
        raise UnsafeInputError("Repository URL must not contain backslashes or encodings.")
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise UnsafeInputError("Only https:// repository URLs are allowed.")
    if parts.username or parts.password or "@" in parts.netloc:
        raise UnsafeInputError("Credentials in repository URLs are not allowed.")
    if parts.port is not None or ":" in parts.netloc:
        raise UnsafeInputError("Custom ports are not allowed.")
    host = (parts.hostname or "").lower()
    if host not in allowed_hosts():
        raise UnsafeInputError(f"Host '{host}' is not allowed. Allowed: "
                               f"{', '.join(allowed_hosts())}.")
    if parts.query or parts.fragment:
        raise UnsafeInputError("Query strings and fragments are not allowed.")
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) != 2:
        raise UnsafeInputError("Expected https://<host>/<owner>/<repo>.")
    owner, name = segments
    if name.endswith(".git"):
        name = name[:-4]
    for segment in (owner, name):
        if not _SEGMENT.fullmatch(segment) or segment in {".", ".."} or ".." in segment:
            raise UnsafeInputError(f"Invalid owner/repository name: {segment!r}.")
    return RepoRef(host=host, owner=owner, name=name)


def validate_ref(ref: str | None) -> str | None:
    if ref is None or not str(ref).strip():
        return None
    ref = str(ref).strip()
    if not _REF.fullmatch(ref) or ".." in ref or ref.endswith((".lock", "/")) or "//" in ref:
        raise UnsafeInputError("Invalid branch/tag name.")
    return ref


def build_clone_argv(repo: RepoRef, dest: str, ref: str | None = None,
                     git_bin: str = "git") -> list[str]:
    """Hardened shallow clone.  ``--`` stops option injection via URL/dest."""
    argv = [
        git_bin,
        "-c", "protocol.allow=never", "-c", "protocol.https.allow=always",
        "-c", "core.symlinks=false",        # no symlinks pointing outside the clone
        "-c", "core.hooksPath=/dev/null",   # never run hooks
        "-c", "core.fsmonitor=false",
        "-c", "submodule.recurse=false",
        "-c", "http.followRedirects=false",
        "clone", "--depth", "1", "--single-branch", "--no-tags", "--quiet",
    ]
    if ref:
        argv += ["--branch", ref]
    return [*argv, "--", repo.clone_url, dest]


def build_gemini_argv(prompt: str, cli_bin: str | None = None,
                      model: str | None = None) -> list[str]:
    """Headless, read-only Gemini CLI invocation (verified against gemini-cli 0.66.0).

    * ``--prompt``: non-interactive mode.  The prompt is ONE argv element: no shell parsing.
    * ``--output-format json``: machine-readable ``{session_id, response, stats, error}``.
    * ``--approval-mode plan``: read-only tools only.  The cloned repo is never marked
      trusted (no ``--skip-trust``), so Gemini CLI also ignores workspace settings and
      falls back to approval mode "default", where non-interactive tool approvals fail
      closed.
    """
    argv = [cli_bin or env_str("GEMINI_CLI_PATH", "gemini"), "--prompt", prompt,
            "--output-format", "json", "--approval-mode", "plan"]
    model = model or env_str("GEMINI_CLI_MODEL")
    if model:
        if not _MODEL.fullmatch(model):
            raise UnsafeInputError("Invalid Gemini CLI model name.")
        argv += ["--model", model]
    if env_bool("GEMINI_CLI_SANDBOX"):
        argv.append("--sandbox")
    return argv


def filtered_env(allowlist: tuple[str, ...], extra: dict[str, str] | None = None
                 ) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in allowlist}
    if extra:
        env.update(extra)
    return env


def gemini_env() -> dict[str, str]:
    return filtered_env(GEMINI_ENV_ALLOWLIST, {"NO_COLOR": "1"})


def git_env() -> dict[str, str]:
    return filtered_env(GIT_ENV_ALLOWLIST, {
        "GIT_TERMINAL_PROMPT": "0",      # never prompt for credentials
        "GIT_CONFIG_NOSYSTEM": "1",      # ignore /etc/gitconfig
        "GIT_CONFIG_GLOBAL": os.devnull,  # ignore ~/.gitconfig (insteadOf, helpers, hooks)
        "GIT_LFS_SKIP_SMUDGE": "1",      # do not download LFS blobs
        "GIT_ASKPASS": "",
        "SSH_ASKPASS": "",
    })
