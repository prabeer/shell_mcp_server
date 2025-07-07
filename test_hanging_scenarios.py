#!/usr/bin/env python3
"""
Comprehensive test for potential hanging scenarios in command execution
"""

import json
import subprocess
import sys
import time
import threading
from pathlib import Path

def test_potential_hanging_scenarios():
    """Test scenarios that might cause command hanging"""
    print("🚨 Testing Potential Command Hanging Scenarios")
    print("=" * 55)
    
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = Path(__file__).parent.parent
    
    test_cases = [
        {
            "name": "Original problematic chmod",
            "command": "chmod +x /home/prabeer/DevelopmentNov/HYLUMINIX/mapapp/scripts/admin_panel/*.py",
            "stream": False,
            "expected_fast": True
        },
        {
            "name": "chmod with verbose output",
            "command": "chmod -v +x /home/prabeer/DevelopmentNov/HYLUMINIX/mapapp/scripts/admin_panel/*.py",
            "stream": False,
            "expected_fast": True
        },
        {
            "name": "chmod with error (non-existent path)",
            "command": "chmod +x /nonexistent/path/*.py",
            "stream": False,
            "expected_fast": True
        },
        {
            "name": "Command that produces no output",
            "command": "true",
            "stream": False,
            "expected_fast": True
        },
        {
            "name": "Command that might hang (yes command)",
            "command": "timeout 2 yes | head -5",
            "stream": False,
            "expected_fast": True
        },
        {
            "name": "Large glob pattern",
            "command": "ls -la /home/prabeer/DevelopmentNov/*/*.py | wc -l",
            "stream": False,
            "expected_fast": True
        },
        {
            "name": "Command with stderr output",
            "command": "ls /nonexistent 2>&1 || echo 'Command completed'",
            "stream": False,
            "expected_fast": True
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['name']}")
        
        try:
            # Start fresh server for each test
            server_proc = subprocess.Popen(
                [sys.executable, str(server_path), "--saferoot", str(safe_root), "--debug"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            stderr_output = []
            def read_stderr():
                while True:
                    line = server_proc.stderr.readline()
                    if not line:
                        break
                    stderr_output.append(line.strip())
            
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()
            
            # Initialize
            init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
            server_proc.stdin.write(json.dumps(init_msg) + "\n")
            server_proc.stdin.flush()
            server_proc.stdout.readline()  # Consume init response
            
            # Send test command
            start_time = time.time()
            cmd_msg = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "run_shell",
                    "arguments": {
                        "command": test_case["command"],
                        "stream": test_case["stream"]
                    }
                }
            }
            
            server_proc.stdin.write(json.dumps(cmd_msg) + "\n")
            server_proc.stdin.flush()
            
            # Wait for response with timeout
            response_received = False
            timeout = time.time() + 10  # 10 second timeout
            
            while time.time() < timeout:
                response = server_proc.stdout.readline()
                if response:
                    elapsed = time.time() - start_time
                    try:
                        resp_data = json.loads(response)
                        if "result" in resp_data:
                            content = resp_data["result"]["content"][0]["text"]
                            
                            # Determine if this was expected timing
                            if elapsed < 5.0:
                                status = "✅ FAST" if test_case["expected_fast"] else "⚠️ UNEXPECTEDLY FAST"
                            else:
                                status = "❌ SLOW" if test_case["expected_fast"] else "✅ EXPECTED SLOW"
                            
                            print(f"   {status} - Completed in {elapsed:.3f}s")
                            print(f"   Output: '{content[:100]}{'...' if len(content) > 100 else ''}'")
                            response_received = True
                            break
                    except json.JSONDecodeError:
                        elapsed = time.time() - start_time
                        print(f"   ❌ JSON ERROR after {elapsed:.3f}s: {response[:100]}")
                        break
                else:
                    time.sleep(0.1)
            
            if not response_received:
                elapsed = time.time() - start_time
                print(f"   ❌ TIMEOUT - No response after {elapsed:.1f}s")
                print("   Last debug output:")
                for line in stderr_output[-3:]:
                    print(f"     {line}")
            
            # Cleanup
            try:
                server_proc.terminate()
                server_proc.wait(timeout=2)
            except:
                server_proc.kill()
                
        except Exception as e:
            print(f"   ❌ Test failed with exception: {e}")
    
    print("\n🎯 Summary:")
    print("If all tests show FAST completion, the server is working correctly.")
    print("If you're experiencing hanging, it might be:")
    print("  1. Client-side issue (UI not updating)")
    print("  2. Network/connection issue")
    print("  3. Different execution environment")
    print("  4. Race condition in specific scenarios")
    
    print("\n✅ Hanging scenario tests completed!")

if __name__ == "__main__":
    test_potential_hanging_scenarios()
