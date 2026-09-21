
import os
import json
import requests
from .tools import run_shell_command, read_file, write_file, list_files

class MiniCodePilot:
    def __init__(self, workspace):
        self.workspace = workspace
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("Missing OPENROUTER_API_KEY in environment variables.")
        self.history = []

    def run_task(self, task, max_iterations=5):
        self.history.append({"role": "user", "content": task})
        system_prompt = """You are MiniCodePilot, an AI coding harness.
You have access to tools: run_shell_command, read_file, write_file, list_files.
Reply in JSON with a 'tool' field and 'args' field. If finished, set 'tool' to 'complete'."""
        
        for i in range(max_iterations):
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": "google/gemini-pro",
                        "messages": [{"role": "system", "content": system_prompt}] + self.history
                    }
                )
                if response.status_code != 200:
                    return f"API Error: {response.text}"
                
                msg = response.json()['choices'][0]['message']['content']
                self.history.append({"role": "assistant", "content": msg})
                
                # very basic parse
                try:
                    action = json.loads(msg)
                    tool = action.get('tool')
                    if tool == 'complete':
                        return "Task Completed successfully."
                    elif tool == 'write_file':
                        res = write_file(f"{self.workspace}/{action['args']['path']}", action['args']['content'])
                    elif tool == 'run_shell_command':
                        res = run_shell_command(action['args']['cmd'], cwd=self.workspace)
                    else:
                        res = "Unknown tool"
                except json.JSONDecodeError:
                    res = "Error: Please respond in valid JSON format."
                
                self.history.append({"role": "user", "content": f"Tool Result: {res}"})
            except Exception as e:
                return f"Execution error: {str(e)}"
                
        return "Max iterations reached without completion."
