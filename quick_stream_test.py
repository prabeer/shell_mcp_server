#!/usr/bin/env python3
"""
Quick test to demonstrate fixed streaming functionality
"""

import json
import subprocess
import sys
import time
from pathlib import Path

def quick_streaming_test():
    """Simple test to show streaming works"""
    print("🔄 Quick Streaming Test")
    print("=" * 40)
    
    # Start the MCP server
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = Path(__file__).parent
    
    try:
        # Start server process
        server_proc = subprocess.Popen(
            [sys.executable, str(server_path), "--saferoot", str(safe_root)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Send initialize
        init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        server_proc.stdin.write(json.dumps(init_msg) + "\n")
        server_proc.stdin.flush()
        
        # Read init response
        init_response = server_proc.stdout.readline()
        print(f"✅ Server initialized: {json.loads(init_response)['result']['serverInfo']['name']}")
        
        # Send streaming command
        stream_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": "for i in {1..3}; do echo \"Stream $i\"; sleep 1; done",
                    "stream": True,
                    "request_id": "quick-test"
                }
            }
        }
        server_proc.stdin.write(json.dumps(stream_msg) + "\n")
        server_proc.stdin.flush()
        
        print("📤 Sent streaming command, watching for progress updates...")
        
        # Read streaming responses
        timeout = time.time() + 10
        final_result = None
        progress_count = 0
        
        while time.time() < timeout:
            response = server_proc.stdout.readline()
            if not response:
                break
                
            try:
                resp_data = json.loads(response)
                
                if "method" in resp_data and resp_data["method"] == "$/progress":
                    progress_count += 1
                    print(f"🔄 Progress {progress_count}: {resp_data['params']['output']}")
                elif "result" in resp_data:
                    final_result = resp_data["result"]
                    print(f"✅ Final result: {final_result['content'][0]['text']}")
                    break
                    
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON: {response}")
        
        # Shutdown
        server_proc.terminate()
        server_proc.wait()
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   - Progress updates received: {progress_count}")
        print(f"   - Final result: {'✅ Success' if final_result else '❌ Failed'}")
        print(f"   - Streaming: {'✅ Working' if progress_count > 3 else '❌ Not working'}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        if server_proc.poll() is None:
            server_proc.terminate()

if __name__ == "__main__":
    quick_streaming_test()
