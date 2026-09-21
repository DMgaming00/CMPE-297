
import json
import os
import subprocess

def run_experiment():
    # 1. Run Baseline
    with open('config.json', 'w') as f:
        json.dump({'lr': 0.01}, f)
    
    print("Running Baseline...")
    subprocess.run(['python', 'src/train.py'])
    
    with open('metrics.json', 'r') as f:
        baseline_metrics = json.load(f)
    
    # 2. Agent proposes change (Mock LLM response for demonstration)
    print("Agent proposes changing lr to 0.05")
    with open('config.json', 'w') as f:
        json.dump({'lr': 0.05}, f)
        
    print("Running New Experiment...")
    subprocess.run(['python', 'src/train.py'])
    
    with open('metrics.json', 'r') as f:
        new_metrics = json.load(f)
        
    # 3. Accept/Reject logic
    if new_metrics['score'] > baseline_metrics['score']:
        print("Experiment Accepted! Score improved.")
    else:
        print("Experiment Rejected! Rolling back config.json.")
        with open('config.json', 'w') as f:
            json.dump({'lr': 0.01}, f)

if __name__ == '__main__':
    run_experiment()
