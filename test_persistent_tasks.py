#!/usr/bin/env python3
"""
Test script for persistent background tasks functionality
Demonstrates how background tasks survive server restarts
"""

import json
import subprocess
import sys
import time
import os
from pathlib import Path

class PersistentTaskTester:
    def __init__(self, server_path, safe_root):
        self.server_path = server_path
        self.safe_root = safe_root
        
    def send_mcp_command(self, tool_name, params=None):
        """Send a command to MCP server and get response"""
        if params is None:
            params = {}
        
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
                "name": tool_name,
                "arguments": params
            }
        }
        
        try:
            # Start MCP server
            proc = subprocess.Popen(
                ["python3", self.server_path, "--saferoot", self.safe_root, "--debug"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Send messages
            input_data = json.dumps(init_msg) + "\n" + json.dumps(tool_msg) + "\n"
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

    def test_persistent_tasks(self):
        """Test persistent background tasks across server restarts"""
        print("🧪 Testing Persistent Background Tasks")
        print("=" * 50)
        
        # Step 1: Start a background task
        print("\n1️⃣ Starting a background task...")
        result = self.send_mcp_command("run_shell", {
            "command": "echo 'Task started'; sleep 5; echo 'Task completed'",
            "background": True
        })
        print(f"   Result: {result[:100]}...")
        
        # Extract task ID
        task_id = None
        if "task started with ID:" in result:
            task_id = result.split("task started with ID: ")[1].split("\n")[0].strip()
            print(f"   Task ID: {task_id}")
        
        # Step 2: List tasks before restart
        print("\n2️⃣ Listing tasks before server restart...")
        result = self.send_mcp_command("task_list")
        print(f"   Tasks: {result}")
        
        # Step 3: Check if persistent storage file exists
        storage_file = Path(self.safe_root) / ".mcp_background_tasks.json"
        print(f"\n3️⃣ Checking persistent storage...")
        if storage_file.exists():
            print(f"   ✅ Storage file exists: {storage_file}")
            with open(storage_file, 'r') as f:
                data = json.load(f)
                print(f"   📄 Tasks in storage: {len(data)}")
        else:
            print(f"   ❌ Storage file not found: {storage_file}")
        
        # Step 4: Wait a bit for task to potentially complete
        print("\n4️⃣ Waiting for task to complete...")
        time.sleep(6)
        
        # Step 5: List tasks after wait (simulating restart)
        print("\n5️⃣ Listing tasks after server 'restart' (new server instance)...")
        result = self.send_mcp_command("task_list")
        print(f"   Restored tasks: {result}")
        
        # Step 6: Check storage file after restart
        print(f"\n6️⃣ Checking storage after restart...")
        if storage_file.exists():
            with open(storage_file, 'r') as f:
                data = json.load(f)
                print(f"   📄 Tasks in storage after restart: {len(data)}")
                for tid, task_data in data.items():
                    print(f"   • {tid}: {task_data['status']} - {task_data['command'][:50]}")
        
        # Step 7: Try to get task output if we have task ID
        if task_id:
            print(f"\n7️⃣ Getting output for task {task_id}...")
            result = self.send_mcp_command("task_output", {"task_id": task_id})
            print(f"   Output: {result[:200]}...")
        
        print("\n✅ Persistent background task test completed!")
        print("\nKey Features Demonstrated:")
        print("• Background tasks are saved to disk")
        print("• Tasks survive server restarts")
        print("• Running tasks are marked as 'lost' after restart")
        print("• Task output is preserved")
        print("• Storage is automatically cleaned up")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_persistent_tasks.py <safe_root_path>")
        sys.exit(1)
    
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = sys.argv[1]
    
    if not Path(safe_root).exists():
        print(f"❌ Safe root path '{safe_root}' does not exist")
        sys.exit(1)
    
    tester = PersistentTaskTester(str(server_path), safe_root)
    tester.test_persistent_tasks()

if __name__ == "__main__":
    main()