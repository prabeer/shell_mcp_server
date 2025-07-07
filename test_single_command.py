#!/usr/bin/env python3
"""
Test script to validate specific command execution issues with chmod and similar commands
"""

import json
import subprocess
import sys
import time
import threading
from pathlib import Path

def test_single_commands():
    """Test single commands that should complete quickly"""
    print("🧪 Testing Single Command Execution Issues")
    print("=" * 50)
    
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
        
        # Initialize
        init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        server_proc.stdin.write(json.dumps(init_msg) + "\n")
        server_proc.stdin.flush()
        response = server_proc.stdout.readline()
        print("✅ Server initialized")
        
        # Test 1: Simple chmod command (similar to the problematic one)
        print("\n🧪 Test 1: chmod command (non-streaming)")
        start_time = time.time()
        
        test1_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "chmod +x /home/prabeer/DevelopmentNov/demo-mcp/*.py",
                    "stream": False
                }
            }
        }
        server_proc.stdin.write(json.dumps(test1_msg) + "\n")
        server_proc.stdin.flush()
        
        # Wait for response with timeout
        timeout = time.time() + 10  # 10 second timeout
        response_received = False
        
        while time.time() < timeout:
            if server_proc.stdout.readable():
                response = server_proc.stdout.readline()
                if response:
                    try:
                        resp_data = json.loads(response)
                        elapsed = time.time() - start_time
                        print(f"📥 chmod response received after {elapsed:.1f}s: {resp_data['result']['content'][0]['text'][:100]}...")
                        response_received = True
                        break
                    except json.JSONDecodeError:
                        print(f"❌ Invalid JSON: {response}")
                        break
                else:
                    time.sleep(0.1)
            else:
                break
        
        if not response_received:
            elapsed = time.time() - start_time
            print(f"❌ No response received after {elapsed:.1f}s - command may be hanging!")
        
        # Test 2: The exact problematic command (if path exists)
        print("\n🧪 Test 2: Exact problematic chmod command")
        start_time = time.time()
        
        test2_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "chmod +x /home/prabeer/DevelopmentNov/HYLUMINIX/mapapp/scripts/admin_panel/*.py",
                    "stream": False
                }
            }
        }
        server_proc.stdin.write(json.dumps(test2_msg) + "\n")
        server_proc.stdin.flush()
        
        # Wait for response with timeout
        timeout = time.time() + 10  # 10 second timeout
        response_received = False
        
        while time.time() < timeout:
            if server_proc.stdout.readable():
                response = server_proc.stdout.readline()
                if response:
                    try:
                        resp_data = json.loads(response)
                        elapsed = time.time() - start_time
                        print(f"📥 Problematic chmod response after {elapsed:.1f}s: {resp_data['result']['content'][0]['text']}")
                        response_received = True
                        break
                    except json.JSONDecodeError:
                        print(f"❌ Invalid JSON: {response}")
                        break
                else:
                    time.sleep(0.1)
            else:
                break
        
        if not response_received:
            elapsed = time.time() - start_time
            print(f"❌ CONFIRMED: Problematic command hanging after {elapsed:.1f}s!")
        
        # Test 3: Same command with streaming to see if it helps
        print("\n🧪 Test 3: Same command with streaming enabled")
        start_time = time.time()
        
        test3_msg = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "chmod +x /home/prabeer/DevelopmentNov/HYLUMINIX/mapapp/scripts/admin_panel/*.py",
                    "stream": True,
                    "request_id": "chmod-stream-test"
                }
            }
        }
        server_proc.stdin.write(json.dumps(test3_msg) + "\n")
        server_proc.stdin.flush()
        
        # Watch for streaming responses
        timeout = time.time() + 10
        response_received = False
        progress_count = 0
        
        while time.time() < timeout:
            if server_proc.stdout.readable():
                response = server_proc.stdout.readline()
                if response:
                    try:
                        resp_data = json.loads(response)
                        if "method" in resp_data and resp_data["method"] == "$/progress":
                            progress_count += 1
                            elapsed = time.time() - start_time
                            print(f"🔄 Progress {progress_count} after {elapsed:.1f}s: {resp_data['params']['output']}")
                        elif "result" in resp_data:
                            elapsed = time.time() - start_time
                            print(f"✅ Streaming final result after {elapsed:.1f}s: {resp_data['result']['content'][0]['text']}")
                            response_received = True
                            break
                    except json.JSONDecodeError:
                        print(f"❌ Invalid JSON: {response}")
                        break
                else:
                    time.sleep(0.1)
            else:
                break
        
        if not response_received:
            elapsed = time.time() - start_time
            print(f"❌ Streaming also hanging after {elapsed:.1f}s with {progress_count} progress updates!")
        
        # Test 4: Background execution
        print("\n🧪 Test 4: Same command as background task")
        start_time = time.time()
        
        test4_msg = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "chmod +x /home/prabeer/DevelopmentNov/HYLUMINIX/mapapp/scripts/admin_panel/*.py",
                    "background": True
                }
            }
        }
        server_proc.stdin.write(json.dumps(test4_msg) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        if response:
            resp_data = json.loads(response)
            content_text = resp_data["result"]["content"][0]["text"]
            if "Background task started with ID:" in content_text:
                task_id = content_text.split("ID: ")[1].split("\n")[0]
                elapsed = time.time() - start_time
                print(f"🔄 Background task started after {elapsed:.1f}s with ID: {task_id}")
                
                # Check status after a few seconds
                time.sleep(3)
                status_msg = {
                    "jsonrpc": "2.0",
                    "id": 6,
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
                    total_elapsed = time.time() - start_time
                    print(f"📊 Background task status after {total_elapsed:.1f}s: {resp_data['result']['content'][0]['text']}")
        
        # Test 5: Test if it's specifically a glob pattern issue
        print("\n🧪 Test 5: Test glob pattern vs specific file")
        
        # First test with a simple command that should work
        test5a_msg = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "echo 'Testing glob pattern' && ls /home/prabeer/DevelopmentNov/demo-mcp/*.py | head -1",
                    "stream": False
                }
            }
        }
        server_proc.stdin.write(json.dumps(test5a_msg) + "\n")
        server_proc.stdin.flush()
        
        response = server_proc.stdout.readline()
        if response:
            resp_data = json.loads(response)
            print(f"📥 Glob test result: {resp_data['result']['content'][0]['text']}")
        
        # Shutdown
        print("\n🛑 Shutting down server...")
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
    
    print("\n✅ Single command test completed!")

if __name__ == "__main__":
    test_single_commands()
