# Part B: DeepSeek Harness Plugins

**Author:** Dev Mulchandani

## Description
This module contains customizations and original plugins built for the DeepSeek Harness. Specifically, it features plugins architected using the Cordis framework (TypeScript).

## Included Plugins
1. **Second Brain (`plugins/second-brain/`)**
   - Implements a SQLite-backed memory retrieval system.
   - Registers methods like `save_note` and `search_notes` into the Cordis Context.
2. **Project Health (`plugins/project-health/`)**
   - *Skeleton structure ready for Git analysis and repository statistics.*

## Installation
DeepSeek Harness plugins require a Node.js environment. Navigate to the plugin directories to inspect the `package.json` and `index.ts` files, which define the Cordis service parameters and dependencies.

## Usage
Run the mock integration demonstration:
```bash
cd ../
make demo-b
```
