#!/usr/bin/env python3
"""
Focused test for background task termination with long-running tasks
"""

import json
import subprocess
import sys
import time
import threading
from pathlib import Path

def test_termination_focused():
    """Test termination with actually long-running tasks"""
    print("🎯 Focused Background Task Termination Test")
    print("=" * 55)
    
    # Start the MCP server
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = Path(__file__).parent
    
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
        
        # Initialize
        init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        server_proc.stdin.write(json.dumps(init_msg) + "\n")
        server_proc.stdin.flush()
        response = server_proc.stdout.readline()
        print("✅ Server initialized")
        
        # Test 1: Long running task that should be terminable
        print("\n🧪 Test 1: Long running sleep task")
        task_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "sleep 60",  # Simple 60 second sleep
                    "background": True
                }
            }
        }
        server_proc.stdin.write(json.dumps(task_msg) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        resp_data = json.loads(response)
        content_text = resp_data["result"]["content"][0]["text"]
        task_id = content_text.split("ID: ")[1].split("\n")[0]
        print(f"🆔 Sleep Task ID: {task_id}")
        
        # Wait a moment, then check it's running
        time.sleep(2)
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
        resp_data = json.loads(response)
        status_content = resp_data["result"]["content"][0]["text"]
        if "running" in status_content:
            print("✅ Task is running - ready for termination test")
            
            # Now terminate it
            print("🛑 Terminating sleep task...")
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
            resp_data = json.loads(response)
            terminate_result = resp_data["result"]["content"][0]["text"]
            print(f"🛑 Termination result: {terminate_result}")
            
            # Check status after termination
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
            resp_data = json.loads(response)
            final_status = resp_data["result"]["content"][0]["text"]
            
            if "terminated" in final_status:
                print("✅ SUCCESS: Task was properly terminated!")
            else:
                print(f"❌ FAILED: Task termination didn't work: {final_status}")
        else:
            print(f"❌ Task isn't running as expected: {status_content}")
        
        # Test 2: Stubborn task that ignores SIGTERM
        print("\n🧪 Test 2: Stubborn task (ignores SIGTERM)")
        stubborn_msg = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "trap 'echo Ignoring SIGTERM; sleep 1' TERM; sleep 60",
                    "background": True
                }
            }
        }
        server_proc.stdin.write(json.dumps(stubborn_msg) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        resp_data = json.loads(response)
        content_text = resp_data["result"]["content"][0]["text"]
        stubborn_id = content_text.split("ID: ")[1].split("\n")[0]
        print(f"🆔 Stubborn Task ID: {stubborn_id}")
        
        # Wait a moment, then try to terminate
        time.sleep(2)
        print("🛑 Attempting to terminate stubborn task...")
        terminate_stubborn = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "task_terminate",
                "arguments": {"task_id": stubborn_id}
            }
        }
        server_proc.stdin.write(json.dumps(terminate_stubborn) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        resp_data = json.loads(response)
        stubborn_result = resp_data["result"]["content"][0]["text"]
        print(f"🛑 Stubborn termination result: {stubborn_result}")
        
        # Wait for force kill to take effect
        time.sleep(7)  # Wait longer than the 5 second timeout
        status_stubborn = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "task_status",
                "arguments": {"task_id": stubborn_id}
            }
        }
        server_proc.stdin.write(json.dumps(status_stubborn) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        resp_data = json.loads(response)
        stubborn_final = resp_data["result"]["content"][0]["text"]
        
        if "terminated" in stubborn_final:
            print("✅ SUCCESS: Stubborn task was force-killed!")
        else:
            print(f"❌ FAILED: Stubborn task survived force kill: {stubborn_final}")
        
        # Shutdown
        shutdown_msg = {"jsonrpc": "2.0", "id": 99, "method": "shutdown"}
        server_proc.stdin.write(json.dumps(shutdown_msg) + "\n")
        server_proc.stdin.flush()
        server_proc.stdout.readline()
        
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
    
    print("\n✅ Focused termination test completed!")

if __name__ == "__main__":
    test_termination_focused()
