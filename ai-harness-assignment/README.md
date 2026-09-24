# AI Agent Harness Assignment

**Author:** Dev Mulchandani

## Links to all the walkthrough Videos [Drive Link](https://drive.google.com/drive/folders/1exgV6cb_TYAXkiAo41xcQVdFacjJmm8_?usp=sharing)

## Overview
This repository contains a comprehensive suite of AI Harness projects, split into three major components:
1. **Part A (MiniCodePilot):** A custom, from-scratch AI coding harness utilizing the OpenRouter API.
2. **Part B (DeepSeek Harness Plugins):** Custom Cordis-framework plugins (Second Brain & Project Health) built for the DeepSeek Harness ecosystem.
3. **Part C (AutoResearch-MNIST):** An autonomous Machine Learning experiment tracker that uses an LLM to propose, evaluate, and roll back PyTorch model hyperparameters.

## Repository Structure
- `part-a-coding-harness/` - Contains the custom OpenRouter agent loop and sandboxed tool execution.
- `part-b-deepseek-harness/` - Contains the TypeScript Cordis plugins for DeepSeek integration.
- `part-c-autoresearch/` - Contains the PyTorch MNIST baseline and LLM optimizer script.
- `docs/` - Contains detailed assignment specifications and architectural documentation.
- `demo/` - Contains executable shell scripts for demonstrating the capabilities of all three parts.

## Setup Instructions
1. Clone this repository.
2. Run `./setup.sh` to install all necessary Python dependencies from `requirements.txt`.
3. Copy `.env.example` to `.env` and insert your API keys (e.g., `OPENROUTER_API_KEY`).
4. Run `make test` to execute the automated test suites.

## Demonstrations
Each component features a dedicated demo script:
- `make demo-a` - Executes the MiniCodePilot agent.
- `make demo-b` - Executes the DeepSeek Plugin mocks.
- `make demo-c` - Executes the ML AutoResearch pipeline.

## License
MIT License. Created by Dev Mulchandani.
