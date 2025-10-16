#!/usr/bin/env python3
"""
Debug format string issue in streaming output
"""

import json
import subprocess
import sys
from pathlib import Path

def test_format_issue():
    """Test the specific command that causes format string issues"""
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = "/home/prabeer/DevelopmentNov"
    
    # Test command with percentage
    test_command = "echo 'Progress: 50% complete'"
    
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
        stdout, stderr = proc.communicate(input=input_data, timeout=15)
        
        print("STDOUT:")
        print(stdout)
        print("\nSTDERR:")
        print(stderr)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_format_issue()