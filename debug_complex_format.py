#!/usr/bin/env python3
"""
Enhanced debug for format string issue
"""

import traceback
import json
import subprocess
import sys
from pathlib import Path

def test_complex_command():
    """Test the complex command that fails"""
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = "/home/prabeer/DevelopmentNov"
    
    # The exact command that fails
    test_command = "echo 'Starting...'; echo 'Progress: 50% - Processing'; echo 'Done'"
    
    # Prepare messages
    init_msg = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {}
    }
    
    tool_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "run_shell",
            "arguments": {"command": test_command, "stream": True}
        }
    }
    
    try:
        # Start MCP server
        proc = subprocess.Popen(
            ["python3", str(server_path), "--saferoot", safe_root, "--debug"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send messages
        input_data = json.dumps(init_msg) + "\n" + json.dumps(tool_msg) + "\n"
        
        try:
            stdout, stderr = proc.communicate(input=input_data, timeout=20)
            
            print("STDOUT:")
            print(stdout)
            print("\nSTDERR:")
            print(stderr)
            
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            print("Process timed out!")
            print("STDOUT:")
            print(stdout)
            print("\nSTDERR:")
            print(stderr)
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_complex_command()