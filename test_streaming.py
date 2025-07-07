#!/usr/bin/env python3
"""
Test script to validate streaming functionality in safe_shell_mcp.py
"""

import json
import subprocess
import sys
import time
import threading
from pathlib import Path

def test_streaming():
    """Test the streaming functionality of the MCP server"""
    print("🧪 Testing MCP Shell Server Streaming Functionality")
    print("=" * 60)
    
    # Start the MCP server
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = Path(__file__).parent.parent
    
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
            "params": {"clientInfo": {"name": "test-client", "version": "1.0"}}
        }
        server_proc.stdin.write(json.dumps(init_msg) + "\n")
        server_proc.stdin.flush()
        
        # Read response
        response = server_proc.stdout.readline()
        if response:
            resp_data = json.loads(response)
            print(f"📥 Initialize response: {resp_data}")
        
        # Test 1: Non-streaming command
        print("\n🧪 Test 1: Non-streaming command")
        test1_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "echo 'Hello World' && sleep 1 && echo 'Done'",
                    "stream": False
                }
            }
        }
        server_proc.stdin.write(json.dumps(test1_msg) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        if response:
            resp_data = json.loads(response)
            print(f"📥 Non-streaming response: {resp_data}")
        
        # Test 2: Streaming command
        print("\n🧪 Test 2: Streaming command")
        test2_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "for i in {1..5}; do echo \"Line $i\"; sleep 0.5; done",
                    "stream": True,
                    "request_id": "test-stream-123"
                }
            }
        }
        server_proc.stdin.write(json.dumps(test2_msg) + "\n")
        server_proc.stdin.flush()
        
        # Read all responses (progress updates + final result)
        print("📥 Streaming responses:")
        timeout = time.time() + 10  # 10 second timeout
        while time.time() < timeout:
            if server_proc.stdout.readable():
                response = server_proc.stdout.readline()
                if response:
                    try:
                        resp_data = json.loads(response)
                        if "method" in resp_data and resp_data["method"] == "$/progress":
                            print(f"🔄 Progress: {resp_data['params']['output']}")
                        elif "result" in resp_data:
                            print(f"✅ Final result: {resp_data}")
                            break
                        else:
                            print(f"📥 Response: {resp_data}")
                    except json.JSONDecodeError:
                        print(f"❌ Invalid JSON: {response}")
                else:
                    time.sleep(0.1)
            else:
                break
        
        # Test 3: Background task
        print("\n🧪 Test 3: Background task")
        test3_msg = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "for i in {1..3}; do echo \"Background line $i\"; sleep 1; done",
                    "background": True
                }
            }
        }
        server_proc.stdin.write(json.dumps(test3_msg) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        if response:
            resp_data = json.loads(response)
            print(f"📥 Background task response: {resp_data}")
            
            # Extract task ID if available
            if "result" in resp_data and "content" in resp_data["result"]:
                content_text = resp_data["result"]["content"][0]["text"]
                if "Background task started with ID:" in content_text:
                    task_id = content_text.split("ID: ")[1].split("\n")[0]
                    print(f"🔍 Found task ID: {task_id}")
                    
                    # Test task status
                    time.sleep(2)  # Wait a bit
                    status_msg = {
                        "jsonrpc": "2.0",
                        "id": 5,
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
                        print(f"📥 Task status: {resp_data}")
        
        # Shutdown
        print("\n🛑 Shutting down server...")
        shutdown_msg = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "shutdown"
        }
        server_proc.stdin.write(json.dumps(shutdown_msg) + "\n")
        server_proc.stdin.flush()
        
        # Wait for shutdown response
        response = server_proc.stdout.readline()
        if response:
            resp_data = json.loads(response)
            print(f"📥 Shutdown response: {resp_data}")
        
        # Send exit
        exit_msg = {"jsonrpc": "2.0", "method": "exit"}
        server_proc.stdin.write(json.dumps(exit_msg) + "\n")
        server_proc.stdin.flush()
        
        # Wait for process to end
        server_proc.wait(timeout=5)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if server_proc.poll() is None:
            server_proc.terminate()
            server_proc.wait()
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    test_streaming()
