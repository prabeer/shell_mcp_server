#!/usr/bin/env python3
"""
Direct test of the specific problematic command
"""

import json
import subprocess
import sys
import time
import threading
from pathlib import Path

def test_specific_curl_command():
    """Test the exact command that was causing issues"""
    print("🎯 Testing Specific Problematic Command")
    print("=" * 50)
    
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = Path(__file__).parent.parent
    
    # The exact command that was hanging
    problematic_command = 'curl -s http://localhost:3000/ | grep -E "(Transform Your Business|HYLUMINIX)" | head -3'
    
    print(f"Command: {problematic_command}")
    print("Expected: Should timeout gracefully within 60 seconds")
    print("Starting test...")
    
    start_time = time.time()
    
    try:
        # Start server
        server_proc = subprocess.Popen(
            [sys.executable, str(server_path), "--saferoot", str(safe_root), "--debug"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Monitor stderr
        stderr_lines = []
        def read_stderr():
            while True:
                line = server_proc.stderr.readline()
                if not line:
                    break
                stderr_lines.append(line.strip())
                print(f"[SERVER] {line.strip()}")
        
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()
        
        # Initialize
        init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        server_proc.stdin.write(json.dumps(init_msg) + "\n")
        server_proc.stdin.flush()
        
        # Read init response
        init_response = server_proc.stdout.readline()
        print(f"Init response: {init_response.strip()}")
        
        # Send the problematic command with streaming
        cmd_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "run_shell",
                "arguments": {
                    "command": problematic_command,
                    "stream": True,
                    "request_id": "test_curl"
                }
            }
        }
        
        print(f"\nSending command at {time.time() - start_time:.1f}s...")
        server_proc.stdin.write(json.dumps(cmd_msg) + "\n")
        server_proc.stdin.flush()
        
        # Monitor progress and response
        response = None
        progress_count = 0
        last_progress_time = time.time()
        
        print("Monitoring progress...")
        
        while time.time() - start_time < 120:  # 2 minute max wait
            line = server_proc.stdout.readline()
            if line:
                try:
                    msg = json.loads(line)
                    if msg.get('id') == 2:
                        response = msg
                        break
                    elif msg.get('method') == '$/progress':
                        progress_count += 1
                        elapsed = time.time() - start_time
                        progress_text = msg.get('params', {}).get('output', '')
                        print(f"[{elapsed:6.1f}s] Progress #{progress_count}: {progress_text}")
                        last_progress_time = time.time()
                except json.JSONDecodeError:
                    continue
            else:
                # Check if we're stuck
                if time.time() - last_progress_time > 10:
                    print(f"[{time.time() - start_time:6.1f}s] No progress for 10s, checking...")
                    last_progress_time = time.time()
        
        elapsed = time.time() - start_time
        
        if response:
            print(f"\n✅ COMMAND COMPLETED in {elapsed:.1f}s")
            print(f"Progress updates received: {progress_count}")
            
            result = response.get('result', {})
            content = result.get('content', [{}])[0].get('text', 'No content')
            print(f"Response length: {len(content)} characters")
            print("Response content:")
            print("-" * 40)
            print(content[:500])
            if len(content) > 500:
                print("... (truncated)")
            print("-" * 40)
            
            # Check if it was properly timed out
            if "timeout" in content.lower() or "terminated" in content.lower():
                print("✅ Command was properly handled with timeout/termination")
            else:
                print("ℹ️ Command completed normally")
        else:
            print(f"\n❌ NO RESPONSE after {elapsed:.1f}s")
            print("This indicates the server is still hanging!")
        
        # Cleanup
        print("\nCleaning up server...")
        try:
            server_proc.terminate()
            server_proc.wait(timeout=5)
            print("✅ Server terminated cleanly")
        except subprocess.TimeoutExpired:
            print("⚠️ Server didn't terminate, force killing...")
            server_proc.kill()
            server_proc.wait()
            print("✅ Server force killed")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n💥 EXCEPTION after {elapsed:.1f}s: {e}")
        
        # Emergency cleanup
        try:
            if 'server_proc' in locals():
                server_proc.kill()
                server_proc.wait()
        except:
            pass
    
    print(f"\n🎯 Test completed in {time.time() - start_time:.1f}s")

if __name__ == "__main__":
    test_specific_curl_command()
