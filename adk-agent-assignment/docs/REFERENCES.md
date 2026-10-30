# References and Attribution

These are the professor-provided references for each part, plus the official
documentation used to check current APIs. Reference repositories were read for
architectural understanding. **No source code was copied from them into this
repository.** Where an idea comes from a reference, [ORIGINALITY.md](ORIGINALITY.md)
says so.

## Assignment references

| Part | Reference | Type | Licence (as published) |
|---|---|---|---|
| A | Google Cloud Blog: *Build a deep research agent for lead generation with Google ADK*. https://cloud.google.com/blog/products/ai-machine-learning/build-a-deep-research-agent-with-google-adk | Article | Google Cloud blog |
| A | MagnIeeT, **leadGenerationAgentADK**. https://github.com/MagnIeeT/leadGenerationAgentADK | Reference implementation | Apache-2.0 headers in source |
| B | Derrick Wong, *Combine ADK, Gemini CLI and Cloud Run* (Medium). https://medium.com/@derrickchwong/combine-adk-gemini-cli-and-cloud-run-c5dea5118853 | Article | — |
| B | derrickchwong, **gemini-cli-on-adk**. https://github.com/derrickchwong/gemini-cli-on-adk | Reference implementation | Apache-2.0 headers in source |
| C | Google Cloud Blog: *Tools make an agent: from zero to assistant with ADK*. https://cloud.google.com/blog/topics/developers-practitioners/tools-make-an-agent-from-zero-to-assistant-with-adk | Article | Google Cloud blog |
| C | google/adk-samples, **software-bug-assistant**. https://github.com/google/adk-samples/tree/main/python/agents/software-bug-assistant | Official sample | Apache-2.0 |
| D | Google Codelab: *ADK Code Reviewer Assistant*. https://codelabs.developers.google.com/adk-code-reviewer-assistant/instructions | Codelab | Google Codelabs |
| D | ayoisio, **adk-code-review-assistant**. https://github.com/ayoisio/adk-code-review-assistant | Reference implementation | Apache-2.0 (LICENSE file) |
| E | Google Codelab: *Sports agent with ADK, MCP Toolbox and AlloyDB*. https://codelabs.developers.google.com/codelabs/sports-agent-adk-mcp-alloydb | Codelab | Google Codelabs |
| E | mtoscano84, **sports-agent-adk-mcp-alloydb**. https://github.com/mtoscano84/sports-agent-adk-mcp-alloydb/ | Reference implementation | — |

> Note (checked 2026-10-29): the `software-bug-assistant` path on the `main` branch of
> `google/adk-samples` currently returns 404 after a repository restructure. The design
> summary in ORIGINALITY.md is based on the Google Cloud article and the sample as
> published there.

## Technical documentation used to verify current APIs (2026-10-29/30)
* Google ADK Python 2.13.0, read from the installed package source: agents,
  `McpToolset`, `ToolboxToolset`, tool confirmation, the agent loader, `adk eval`, and
  `adk deploy cloud_run`. Docs: https://google.github.io/adk-docs/
* Gemini API models page (current model IDs and Gemini 2.5 access status):
  https://ai.google.dev/gemini-api/docs/models
* Gemini CLI 0.66.0 `--help` (headless `--prompt`, `--output-format json`,
  `--approval-mode plan`, untrusted-folder behaviour observed directly):
  https://github.com/google-gemini/gemini-cli
* MCP Python SDK 2.3.0 (`mcp.server.mcpserver.MCPServer`, stdio client, tool
  annotations): https://github.com/modelcontextprotocol/python-sdk
* MCP Toolbox for Databases v1.15.0 docs (manifest `kind/name/type` format,
  `authServices`, optional parameters, Cloud Run deployment, container image):
  https://github.com/googleapis/mcp-toolbox
* GitHub remote MCP server: https://github.com/github/github-mcp-server
* AlloyDB for PostgreSQL: https://cloud.google.com/alloydb/docs
* Cloud Run: https://cloud.google.com/run/docs

## Third-party libraries
google-adk, google-genai, mcp, toolbox-adk, pydantic, python-dotenv and pycodestyle,
plus pytest, pytest-asyncio, ruff and PyYAML for development. Each is used under its own
licence, and none is vendored into the repository.

## Data
All demo data (customers, stores, products, orders, tickets, people, companies in
fixtures) is fictional. Emails use the reserved `example.com` domain.
