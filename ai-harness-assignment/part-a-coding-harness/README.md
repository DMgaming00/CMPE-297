# Part A: MiniCodePilot

**Author:** Dev Mulchandani

## Description
MiniCodePilot is a custom AI coding harness built from scratch. It uses the OpenRouter API (specifically configured for models like `google/gemini-pro`) to execute natural language coding tasks autonomously.

## Architecture
The system consists of two primary components:
1. **Tools (`src/tools.py`):** Provides a sandboxed environment for the agent to execute shell commands, read/write files, and list directory contents safely.
2. **Agent Loop (`src/agent.py`):** Maintains the conversation history, injects tool schemas via the system prompt, parses the LLM's JSON responses, executes the requested tools, and feeds the results back into the context window.

## Usage
1. Ensure your `OPENROUTER_API_KEY` is set in the root `.env` file.
2. Run the agent using the provided demo script:
   ```bash
   cd ../
   make demo-a
   ```

## Safety Features
The agent operates exclusively within a designated workspace and uses a strict iteration cap to prevent infinite loops.
