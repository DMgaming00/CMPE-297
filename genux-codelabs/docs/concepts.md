# Concepts

## Two separate decisions

1. **What may the model generate?** Static, declarative, open-ended, or a hybrid.
2. **How does the UI reach the user?** Your own event stream (AG-UI over SSE, a custom stream), or a third-party host that mounts your UI (MCP Apps).

A *representation* (A2UI, OpenUI Lang, JSON Render spec) is not a *transport* (AG-UI, SSE) and not a *host contract* (MCP Apps). Mixing them up is the most common mistake in this space. Here: the capstone carries declarative specs over AG-UI state and calls tools over MCP.

## UX modes

| Mode | Flow | Use when | Cost |
|---|---|---|---|
| Static | User → app → pre-built component → UI | the screen is known | every new screen is code |
| Declarative | Model → spec → validation → registry → UI | layouts vary but components are known | catalog design and maintenance |
| Open-ended | Model → HTML/code → checks → sandbox → UI | the request needs behaviour no catalog entry has | security surface, tokens, latency, variance |
| Mixed | per-region choice | real apps | needs a planner and a degrade path |

Rule of thumb used by the capstone planner: pick the **least powerful mode that satisfies the request**; degrade open-ended → declarative → static, never upward.

## Validation vs authorization

Valid JSON proves syntax. It does not prove the component is allowed, the props are safe, the action exists, or the tool call is permitted. Each of those is a separate check in this repo (`validateSpec`, strict props, `allowedActions`, `allowedTools`, host allowlist).

## Fail safe, then recover

Errors are *results*, not crashes. A rejected `render_ui` spec becomes an `Error:` tool message listing the issues; the model sees it and corrects itself (`apps/harness`, prompt "Invalid UI"). A dropped stream is shown as an error, never as a complete-looking truncated result.

## Streaming

- OpenUI Lang: re-parse on every chunk; forward references let `root = ...` paint the shell first.
- A2UI: structure (`updateComponents`) and state (`updateDataModel`) arrive as separate messages; unresolved child ids render as skeletons.
- AG-UI: typed events; text and tool args stream as deltas; state as snapshot + JSON Patch.
- Open-ended HTML: shown as raw source while streaming, executed only after the stream ends.

## Why a mock model

`ScriptedModel` is a state machine over the transcript. It reads tool results and reacts to errors, so it exercises the same loop a real LLM would, deterministically and offline. A real model is a drop-in `ChatModel` (`OpenAICompatibleModel`).
