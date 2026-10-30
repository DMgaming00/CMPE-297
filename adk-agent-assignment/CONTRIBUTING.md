# Contributing

## Development setup
```bash
./scripts/setup.sh          # or: python3 -m venv .venv && pip install -e ".[dev]"
source .venv/bin/activate
make check                  # compile + ruff + pytest (no credentials required)
```

## Ground rules
* **Keep the guardrails in code.** New consequential tools must go through
  `adk_shared.guardrails.ConfirmationGate`, and user-scoped tools must take identity
  from the session (`IdentityBinder`) or from Toolbox `authServices`, never from a
  model argument.
* **Keep backends interchangeable.** A new tool for agent C or E needs the same name and
  arguments in the local MCP server and in the Toolbox YAML.
  `tests/test_toolbox_configs.py` enforces this.
* **Use parameterised SQL only.** Never format user values into SQL.
* **Never use `shell=True`.** Subprocesses take argv lists, with timeouts and filtered
  environments.
* **Label test doubles.** Tests that replace Gemini or the Gemini CLI must say so. Don't
  claim real execution in docs unless it happened.
* Demo data must be fictional (`example.com` emails).
* After changing `data/demo/*.json`, run `python scripts/seed_demo_data.py --postgres`.

## Pull requests
Include tests, update the affected agent README, and run `make check`.
