# Part C: ML AutoResearch Harness

**Author:** Dev Mulchandani

## Description
An end-to-end Machine Learning AutoResearch Harness that leverages LLMs to optimize PyTorch models autonomously. The system uses an iterative proposal-evaluation-rollback loop.

## Architecture
- **Training Baseline (`src/train.py`):** A PyTorch Convolutional Neural Network (CNN) configured for the MNIST dataset. It reads hyperparameters from `config.json` and outputs evaluation scores to `metrics.json`.
- **Optimizer Agent (`src/optimizer.py`):** The agent loop that coordinates the ML research. It runs the baseline, generates a new hyperparameter configuration, tests the new configuration, and determines whether to accept the changes or roll back to the baseline based on the composite score (`accuracy - time_penalty`).

## Usage
Execute the automated experiment tracker:
```bash
cd ../
make demo-c
```
The script will output the baseline metrics, simulate the LLM proposing a new learning rate, evaluate the new metrics, and print the acceptance/rejection decision.
