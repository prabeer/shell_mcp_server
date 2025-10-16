#!/usr/bin/env python3
"""
Test script to verify the task_status hanging fix
"""

import json
import subprocess
import time
from pathlib import Path

def test_task_status_robustness():
    """Test task_status command robustness with various scenarios"""
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = "/home/prabeer/DevelopmentNov"
    
    print("🧪 Testing Task Status Robustness")
    print("=" * 50)
    
    # Test 1: Normal task status
    print("1️⃣ Testing normal task status...")
    result = send_mcp_command(server_path, safe_root, "run_shell", {
        "command": "echo 'Test task'; sleep 2; echo 'Done'",
        "background": True
    })
    print(f"Background task result: {result}")
    
    # Extract task ID from result
    task_id = None
    if "Background task started with ID:" in result:
        task_id = result.split("Background task started with ID: ")[1].split("\n")[0]
        print(f"Task ID: {task_id}")
        
        # Test task status immediately
        status_result = send_mcp_command(server_path, safe_root, "task_status", {"task_id": task_id})
        print(f"Task status: {status_result}")
        
        # Test task output
        output_result = send_mcp_command(server_path, safe_root, "task_output", {"task_id": task_id})
        print(f"Task output: {output_result}")
        
        # Wait and check again
        time.sleep(3)
        final_status = send_mcp_command(server_path, safe_root, "task_status", {"task_id": task_id})
        print(f"Final status: {final_status}")
    
    # Test 2: Task list
    print("\n2️⃣ Testing task list...")
    list_result = send_mcp_command(server_path, safe_root, "task_list", {})
    print(f"Task list: {list_result}")
    
    # Test 3: Non-existent task
    print("\n3️⃣ Testing non-existent task...")
    fake_status = send_mcp_command(server_path, safe_root, "task_status", {"task_id": "fake-task-id"})
    print(f"Fake task status: {fake_status}")
    
    print("\n✅ Task status robustness tests completed!")

def send_mcp_command(server_path, safe_root, tool_name, params):
    """Send a command to MCP server and get response"""
    init_msg = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
    tool_msg = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool_name, "arguments": params}
    }
    
    try:
        proc = subprocess.Popen(
            ["python3", str(server_path), "--saferoot", safe_root],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        input_data = json.dumps(init_msg) + "\n" + json.dumps(tool_msg) + "\n"
        
        try:
            stdout, stderr = proc.communicate(input=input_data, timeout=10)
            
            # Parse responses
            responses = []
            for line in stdout.strip().split('\n'):
                if line:
                    try:
                        responses.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            
            # Return the tool response
            for response in responses:
                if "result" in response and response.get("id") == 1:
                    content = response["result"].get("content", [])
                    if content and len(content) > 0:
                        return content[0].get("text", "")
            
            return "No valid response received"
            
        except subprocess.TimeoutExpired:
            proc.kill()
            return "Command timed out"
            
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    test_task_status_robustness()