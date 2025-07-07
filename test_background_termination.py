#!/usr/bin/env python3
"""
Test script to validate background task termination functionality
"""

import json
import subprocess
import sys
import time
import threading
from pathlib import Path

def test_background_task_termination():
    """Test the background task termination functionality"""
    print("🧪 Testing Background Task Termination")
    print("=" * 50)
    
    # Start the MCP server
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = Path(__file__).parent
    
    print(f"📂 Server path: {server_path}")
    print(f"🔒 Safe root: {safe_root}")
    
    try:
        # Start server process
        server_proc = subprocess.Popen(
            [sys.executable, str(server_path), "--saferoot", str(safe_root), "--debug"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        def read_stderr():
            """Read and print server debug output"""
            while True:
                line = server_proc.stderr.readline()
                if not line:
                    break
                print(f"🔧 DEBUG: {line.strip()}")
        
        # Start stderr reader thread
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()
        
        # Send initialize message
        print("\n📤 Sending initialize...")
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "termination-test", "version": "1.0"}}
        }
        server_proc.stdin.write(json.dumps(init_msg) + "\n")
        server_proc.stdin.flush()
        
        # Read response
        response = server_proc.stdout.readline()
        if response:
            resp_data = json.loads(response)
            print(f"✅ Server initialized")
        
        # Test 1: Start a long-running background task that's easy to terminate
        print("\n🧪 Test 1: Normal background task termination")
        test1_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "for i in {1..30}; do echo \"Long task $i\"; sleep 1; done",
                    "background": True
                }
            }
        }
        server_proc.stdin.write(json.dumps(test1_msg) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        if response:
            resp_data = json.loads(response)
            content_text = resp_data["result"]["content"][0]["text"]
            task_id = content_text.split("ID: ")[1].split("\n")[0]
            print(f"🆔 Task ID: {task_id}")
            
            # Wait a moment for task to start
            time.sleep(2)
            
            # Check task status
            status_msg = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "task_status",
                    "arguments": {"task_id": task_id}
                }
            }
            server_proc.stdin.write(json.dumps(status_msg) + "\n")
            server_proc.stdin.flush()
            
            response = server_proc.stdout.readline()
            if response:
                resp_data = json.loads(response)
                print(f"📊 Task status before termination: running")
            
            # Now terminate the task
            print(f"🛑 Terminating task {task_id}...")
            terminate_msg = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "task_terminate",
                    "arguments": {"task_id": task_id}
                }
            }
            server_proc.stdin.write(json.dumps(terminate_msg) + "\n")
            server_proc.stdin.flush()
            
            response = server_proc.stdout.readline()
            if response:
                resp_data = json.loads(response)
                print(f"🛑 Termination response: {resp_data['result']['content'][0]['text']}")
            
            # Check task status after termination
            time.sleep(1)
            status_msg2 = {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "task_status",
                    "arguments": {"task_id": task_id}
                }
            }
            server_proc.stdin.write(json.dumps(status_msg2) + "\n")
            server_proc.stdin.flush()
            
            response = server_proc.stdout.readline()
            if response:
                resp_data = json.loads(response)
                content = resp_data["result"]["content"][0]["text"]
                if "terminated" in content:
                    print("✅ Task successfully terminated")
                else:
                    print(f"❌ Task termination may have failed: {content}")
        
        # Test 2: Start a task that's harder to kill (ignores SIGTERM)
        print("\n🧪 Test 2: Hard-to-kill background task")
        test2_msg = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "trap 'echo \"Ignoring SIGTERM\"' TERM; for i in {1..60}; do echo \"Stubborn task $i\"; sleep 1; done",
                    "background": True
                }
            }
        }
        server_proc.stdin.write(json.dumps(test2_msg) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        if response:
            resp_data = json.loads(response)
            content_text = resp_data["result"]["content"][0]["text"]
            task_id2 = content_text.split("ID: ")[1].split("\n")[0]
            print(f"🆔 Stubborn Task ID: {task_id2}")
            
            # Wait a moment for task to start
            time.sleep(2)
            
            # Try to terminate the stubborn task
            print(f"🛑 Attempting to terminate stubborn task {task_id2}...")
            terminate_msg2 = {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "task_terminate",
                    "arguments": {"task_id": task_id2}
                }
            }
            server_proc.stdin.write(json.dumps(terminate_msg2) + "\n")
            server_proc.stdin.flush()
            
            response = server_proc.stdout.readline()
            if response:
                resp_data = json.loads(response)
                print(f"🛑 Stubborn termination response: {resp_data['result']['content'][0]['text']}")
            
            # Check if it actually terminated after a few seconds
            time.sleep(3)
            status_msg3 = {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "task_status",
                    "arguments": {"task_id": task_id2}
                }
            }
            server_proc.stdin.write(json.dumps(status_msg3) + "\n")
            server_proc.stdin.flush()
            
            response = server_proc.stdout.readline()
            if response:
                resp_data = json.loads(response)
                content = resp_data["result"]["content"][0]["text"]
                if "terminated" in content:
                    print("✅ Stubborn task successfully terminated")
                elif "running" in content:
                    print("⚠️ Stubborn task is still running - SIGTERM was ignored!")
                else:
                    print(f"❓ Unclear task status: {content}")
        
        # Test 3: List all background tasks
        print("\n🧪 Test 3: List all background tasks")
        list_msg = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "task_list",
                "arguments": {}
            }
        }
        server_proc.stdin.write(json.dumps(list_msg) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        if response:
            resp_data = json.loads(response)
            print(f"📋 All tasks: {resp_data['result']['content'][0]['text']}")
        
        # Shutdown
        print("\n🛑 Shutting down server...")
        shutdown_msg = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "shutdown"
        }
        server_proc.stdin.write(json.dumps(shutdown_msg) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        if response:
            print("✅ Server shutdown completed")
        
        # Send exit
        exit_msg = {"jsonrpc": "2.0", "method": "exit"}
        server_proc.stdin.write(json.dumps(exit_msg) + "\n")
        server_proc.stdin.flush()
        
        server_proc.wait(timeout=5)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if server_proc.poll() is None:
            server_proc.terminate()
            server_proc.wait()
    
    print("\n✅ Background task termination test completed!")

if __name__ == "__main__":
    test_background_task_termination()
