#!/usr/bin/env python3
"""
Detailed investigation of command execution behavior
"""

import json
import subprocess
import sys
import time
import threading
from pathlib import Path

def investigate_command_behavior():
    """Investigate the exact command execution behavior"""
    print("🔍 Detailed Command Execution Investigation")
    print("=" * 55)
    
    # Test the command directly first
    print("🧪 Direct shell test:")
    try:
        result = subprocess.run([
            "/bin/bash", "-c", 
            "chmod +x /home/prabeer/DevelopmentNov/HYLUMINIX/mapapp/scripts/admin_panel/*.py"
        ], capture_output=True, text=True, timeout=5)
        print(f"✅ Direct command succeeded:")
        print(f"   Return code: {result.returncode}")
        print(f"   Stdout: '{result.stdout}'")
        print(f"   Stderr: '{result.stderr}'")
    except subprocess.TimeoutExpired:
        print("❌ Direct command timed out!")
    except Exception as e:
        print(f"❌ Direct command failed: {e}")
    
    # Now test through MCP server with detailed monitoring
    print("\n🔬 MCP Server Investigation:")
    
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = Path(__file__).parent.parent
    
    try:
        # Start server with debugging
        server_proc = subprocess.Popen(
            [sys.executable, str(server_path), "--saferoot", str(safe_root), "--debug"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        debug_output = []
        
        def read_stderr():
            """Capture all debug output"""
            while True:
                line = server_proc.stderr.readline()
                if not line:
                    break
                debug_output.append(line.strip())
                print(f"🔧 {line.strip()}")
        
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()
        
        # Initialize
        init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        server_proc.stdin.write(json.dumps(init_msg) + "\n")
        server_proc.stdin.flush()
        
        # Wait for init response
        response = server_proc.stdout.readline()
        if response:
            print("✅ Server initialized")
        else:
            print("❌ No init response")
            return
        
        # Send the problematic command with careful timing
        print("\n📤 Sending command...")
        start_time = time.time()
        
        cmd_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "chmod +x /home/prabeer/DevelopmentNov/HYLUMINIX/mapapp/scripts/admin_panel/*.py",
                    "stream": False
                }
            }
        }
        
        server_proc.stdin.write(json.dumps(cmd_msg) + "\n")
        server_proc.stdin.flush()
        print(f"📤 Command sent at {time.time() - start_time:.3f}s")
        
        # Monitor for response with detailed timing
        response_received = False
        timeout = time.time() + 15  # 15 second timeout
        
        while time.time() < timeout:
            # Check if there's data available
            try:
                import select
                ready, _, _ = select.select([server_proc.stdout], [], [], 0.1)
                if ready:
                    response = server_proc.stdout.readline()
                    if response:
                        elapsed = time.time() - start_time
                        print(f"📥 Response received at {elapsed:.3f}s")
                        try:
                            resp_data = json.loads(response)
                            if "result" in resp_data:
                                content = resp_data["result"]["content"][0]["text"]
                                print(f"✅ Command result: '{content}' (length: {len(content)})")
                                print(f"✅ Response data: {resp_data}")
                                response_received = True
                                break
                            else:
                                print(f"❓ Unexpected response structure: {resp_data}")
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON decode error: {e}")
                            print(f"Raw response: '{response}'")
                            break
                else:
                    elapsed = time.time() - start_time
                    if elapsed > 5:  # Print status every 5 seconds
                        print(f"⏳ Still waiting for response... {elapsed:.1f}s elapsed")
                        # Reset the 5 second counter
                        timeout = time.time() + 10
            except ImportError:
                # Fallback if select is not available
                response = server_proc.stdout.readline()
                if response:
                    elapsed = time.time() - start_time
                    print(f"📥 Response received at {elapsed:.3f}s: {response}")
                    response_received = True
                    break
                time.sleep(0.1)
        
        if not response_received:
            elapsed = time.time() - start_time
            print(f"❌ NO RESPONSE received after {elapsed:.1f}s!")
            print("🔍 Debug output summary:")
            for line in debug_output[-10:]:  # Show last 10 debug lines
                print(f"   {line}")
        
        # Check if process is still running
        if server_proc.poll() is None:
            print("🔄 Server process is still running")
        else:
            print(f"💀 Server process died with code: {server_proc.returncode}")
        
        # Try to shutdown gracefully
        try:
            shutdown_msg = {"jsonrpc": "2.0", "id": 99, "method": "shutdown"}
            server_proc.stdin.write(json.dumps(shutdown_msg) + "\n")
            server_proc.stdin.flush()
            
            # Wait a bit for shutdown
            time.sleep(1)
            if server_proc.poll() is None:
                exit_msg = {"jsonrpc": "2.0", "method": "exit"}
                server_proc.stdin.write(json.dumps(exit_msg) + "\n")
                server_proc.stdin.flush()
                server_proc.wait(timeout=3)
        except:
            server_proc.terminate()
            server_proc.wait()
        
    except Exception as e:
        print(f"❌ Investigation failed: {e}")
        import traceback
        traceback.print_exc()
        
    print("\n✅ Investigation completed!")

if __name__ == "__main__":
    investigate_command_behavior()
