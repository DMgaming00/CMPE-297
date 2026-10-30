# Security: Threat Model and Red-Team Review

Scope: the five agents, the shared guardrails, the local MCP servers, the Toolbox
configurations and the container. Each threat below lists the control and the test
that checks it. Residual risks are stated plainly.

## Trust boundaries
1. **User → model.** User text may contain prompt injection.
2. **Tool data → model.** Web pages, repository files, tickets, product descriptions
   and CLI output are untrusted data.
3. **Model → tools.** The model's tool arguments are untrusted. Every consequential
   control sits **after** this boundary, in code.
4. **Agent → subprocess.** Gemini CLI, git and MCP servers.
5. **Agent → database.** Through MCP only.

## Threats, controls and evidence

| Threat | Agent | Control | Evidence (test) |
|---|---|---|---|
| Command / shell injection | B | argv lists only (`create_subprocess_exec`); prompt is one argv element; no `shell=True` anywhere outside the deliberately vulnerable fixture | `test_prompt_with_shell_metacharacters_stays_one_argument`; `grep -rn "shell=True" agents adk_shared` finds only rule text and comments |
| Malicious repository URL / SSRF | B | `https` only; host allowlist; no credentials, ports, query, fragment, `%`, `\`, whitespace; exactly owner/repo; no leading `-`; `--` before URL | 26 cases in `test_rejects_unsafe_urls` |
| Git option and transport abuse | B | `protocol.allow=never` + `https.allow=always`, `core.hooksPath=/dev/null`, `core.symlinks=false`, no submodules, no redirects, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_TERMINAL_PROMPT=0`, LFS skipped | `test_clone_argv_is_hardened_and_option_terminated` |
| Repo-supplied CLI configuration / instructions | B | Untrusted folder (no `--skip-trust`), so Gemini CLI ignores workspace settings (observed in 0.66.0); `.gemini/` and `GEMINI.md` deleted; `--approval-mode plan` | `test_strip_untrusted_config`, end-to-end fake-CLI test (`gemini_md_present=False`) |
| Secrets exposure to subprocesses | B, C, E | Environment allowlists for the Gemini CLI, git and MCP servers (DB passwords and GitHub tokens are withheld) | `test_subprocess_environments_do_not_leak_secrets`, `secret_visible=False` |
| Runaway process / resource exhaustion | B | Process-group SIGKILL on timeout; capped, incrementally drained pipes; repo file/size limits; concurrency semaphore | `test_timeout_kills_process_group`, `test_output_is_capped_without_deadlock`, `test_repository_size_limit` |
| Unsafe temporary files | B, D | `mkdtemp` private dirs removed in `finally`; D style checks run in memory (no temp files) | `test_clone_strips_config_and_always_cleans_up`, `test_clone_failure_is_reported_and_cleaned` |
| Path traversal | D | Workspace loader resolves paths and requires `is_relative_to(root)`; `.py` only; filename regex; size limit; symlink escapes blocked | `test_workspace_loading_blocks_path_traversal` |
| Executing reviewed code | D | Code is parsed with `ast`, never imported or executed | `test_reviewed_code_is_never_executed` |
| Prompt injection to suppress findings | D | Models can't remove high-confidence P0/P1 static findings; LLM findings must quote real code | `test_model_cannot_remove_high_confidence_p0_static_finding`, `test_hallucinated_llm_findings_are_dropped` |
| SQL injection | C, E | All SQLite and PostgreSQL statements parameterised; dynamic SQL built only from fixed fragments; Toolbox exposes no raw-SQL tool | `test_search_is_parameterised_against_sql_injection`; Toolbox placeholder tests |
| Accidental / injected purchases | E | ADK tool confirmation enforced by callback for `place_order` and `cancel_order`; quote must be prepared in-session; two-phase quote → place | `test_purchase_requires_confirmation_and_binds_identity`, `test_rejected_confirmation_places_nothing`, `test_fabricated_quote_is_blocked_before_confirmation` |
| Destructive ticket writes | C | Confirmation for all 5 write tools; no delete tool; state machine; audit comment on every change | `test_reads_run_freely_but_writes_need_approval`, `test_status_state_machine_and_audit_trail` |
| Cross-user order access (IDOR) | E | `IdentityBinder` overwrites `user_id`; every query scoped; uniform `NOT_FOUND`; production identity from a verified ID token (`authServices`) | `test_user_isolation_for_quotes_and_orders`, `test_user_scoped_tools_take_identity_from_verified_token` |
| Oversell / double order | E | Atomic conditional decrement, `CHECK (quantity >= 0)`, idempotent quote consumption | `test_concurrent_orders_for_last_unit_never_oversell`, `test_place_order_is_idempotent` |
| Excessive permissions | C, E | Narrow business tools; least-privilege DB roles (`commerce_app`, `bug_app`: no DELETE or DDL); GitHub MCP read-only filter + `X-MCP-Readonly` | `test_github_mcp_filter_is_read_only`; schema GRANTs |
| Secrets in source / config | all | `.env` ignored; `.env.example` placeholders only; Toolbox credentials via `${ENV}` | `test_no_plaintext_credentials`, `test_env_example_contains_only_placeholders` |
| Secrets in logs / model context | B, all | `redact_secrets` on CLI output and tool logs; strings truncated in logs; MCP servers log to stderr (stdout is the protocol channel) | `test_redaction` |
| Malformed model output | A, D | Pydantic `output_schema`; deterministic stages validate and degrade gracefully | `test_malformed_specialist_output_is_ignored` |
| Untrusted data in prompts | A, C, D, E | Prompts label tool data as untrusted; listings are wrapped as data; the CLI user focus is fenced and control characters stripped | `test_prompt_wraps_focus_as_data_and_strips_control_chars` |

## Residual risks (accepted, documented)
1. **`adk web` is an unauthenticated development server.** Use `adk api_server` behind
   Cloud Run IAM in production. The Dockerfile defaults to `api_server`.
2. **The local identity mapping (E) isn't authentication.** It maps the ADK Web user to
   a demo customer. Production identity comes from Toolbox-verified Google ID tokens.
3. **The local MCP servers trust their single caller.** stdio has no auth channel. They
   are spawned only by the ADK process.
4. **Gemini CLI still reads untrusted repository content.** It can't execute or edit
   (approval mode, untrusted folder), but a malicious repo can try to mislead the
   analysis. Results are presented as untrusted output with verified and unverified
   path markers. For hostile multi-tenant input, run B in a sandbox job with egress
   limits, and consider `GEMINI_CLI_SANDBOX=true`.
5. **Prompt injection can still degrade answer quality** (wrong recommendations), even
   though it can't trigger purchases, writes or identity changes.
6. **No rate limiting or per-user quotas** are implemented. Rely on Cloud Run / API
   Gateway limits in production.
7. **Static analysis (D) is heuristic.** It gives no guarantee that vulnerabilities are
   absent.
8. **The production Toolbox SQL wasn't executed in this environment.** See
   [TESTING.md](TESTING.md#production-toolbox-verification).

## Reporting
See the repository [SECURITY.md](../SECURITY.md).
