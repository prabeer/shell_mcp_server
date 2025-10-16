#!/usr/bin/env python3
"""
Test the exact failing command
"""

import json
import subprocess
from pathlib import Path

def test_exact_failing_command():
    """Test the exact command that was failing"""
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = "/home/prabeer/DevelopmentNov"
    
    # The exact failing command
    test_command = "echo 'Starting file processing simulation...'; for i in 10 20 30 40 50 60 70 80 90 100; do echo \"Progress: ${i}% - Processing data chunk\"; sleep 0.3; done; echo 'Processing complete!'"
    
    init_msg = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
    tool_msg = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "run_shell", "arguments": {"command": test_command, "stream": True}}
    }
    
    try:
        proc = subprocess.Popen(
            ["python3", str(server_path), "--saferoot", safe_root, "--debug"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        input_data = json.dumps(init_msg) + "\n" + json.dumps(tool_msg) + "\n"
        
        try:
            stdout, stderr = proc.communicate(input=input_data, timeout=15)
            print("SUCCESS - STDOUT:")
            print(stdout)
            print("\nSTDERR:")
            print(stderr)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            print("TIMEOUT - STDOUT:")
            print(stdout)
            print("\nSTDERR:")
            print(stderr)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_exact_failing_command()