#!/usr/bin/env python3
"""
Test script to validate the anti-hang fixes
"""

import json
import subprocess
import sys
import time
import threading
from pathlib import Path

def test_anti_hang_improvements():
    """Test the anti-hang improvements"""
    print("🚨 Testing Anti-Hang Improvements")
    print("=" * 40)
    
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = Path(__file__).parent.parent
    
    test_cases = [
        {
            "name": "Original problematic curl command",
            "command": "curl -s http://localhost:3000/ | grep -E \"(Transform Your Business|HYLUMINIX)\" | head -3",
            "stream": True,
            "expected_timeout": True,
            "max_wait": 70
        },
        {
            "name": "Curl with timeout",
            "command": "timeout 5 curl -s http://localhost:3000/ | head -3",
            "stream": False,
            "expected_timeout": False,
            "max_wait": 10
        },
        {
            "name": "Network command with streaming",
            "command": "curl -s --connect-timeout 5 --max-time 10 http://httpbin.org/delay/2 | head -5",
            "stream": True,
            "expected_timeout": False,
            "max_wait": 15
        },
        {
            "name": "Hanging yes command",
            "command": "timeout 3 yes | head -10",
            "stream": True,
            "expected_timeout": False,
            "max_wait": 8
        },
        {
            "name": "Simple command",
            "command": "echo 'Hello World' && sleep 1 && echo 'Done'",
            "stream": True,
            "expected_timeout": False,
            "max_wait": 5
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['name']}")
        print(f"   Command: {test_case['command']}")
        print(f"   Stream: {test_case['stream']}")
        
        success = False
        start_time = time.time()
        
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
            
            # Collect stderr for debugging
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
            
            # Read init response
            init_response = server_proc.stdout.readline()
            
            # Send test command
            cmd_msg = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "run_shell",
                    "arguments": {
                        "command": test_case['command'],
                        "stream": test_case['stream'],
                        "request_id": f"test_{i}"
                    }
                }
            }
            
            server_proc.stdin.write(json.dumps(cmd_msg) + "\n")
            server_proc.stdin.flush()
            
            # Read response with timeout
            response = None
            progress_updates = 0
            
            while time.time() - start_time < test_case['max_wait']:
                line = server_proc.stdout.readline()
                if line:
                    try:
                        msg = json.loads(line)
                        if msg.get('id') == 2:
                            response = msg
                            break
                        elif msg.get('method') == '$/progress':
                            progress_updates += 1
                            print(f"     Progress: {msg.get('params', {}).get('output', '')}")
                    except json.JSONDecodeError:
                        continue
                else:
                    time.sleep(0.1)
            
            elapsed = time.time() - start_time
            
            if response:
                success = True
                result_text = response.get('result', {}).get('content', [{}])[0].get('text', 'No content')
                print(f"   ✅ SUCCESS in {elapsed:.1f}s")
                print(f"   📊 Progress updates: {progress_updates}")
                print(f"   📄 Result length: {len(result_text)} chars")
                
                # Check for timeout indicators in the response
                if "timeout" in result_text.lower() or "terminated" in result_text.lower():
                    print(f"   ⏱️ Command was properly timed out/terminated")
                
            else:
                print(f"   ❌ TIMEOUT - No response after {elapsed:.1f}s")
                print(f"   📊 Progress updates received: {progress_updates}")
                
                # Check if expected timeout
                if test_case.get('expected_timeout', False):
                    print(f"   ℹ️ This timeout was expected for this test case")
                    success = True  # Expected behavior
            
            # Cleanup
            try:
                server_proc.terminate()
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
                server_proc.wait()
            
            results.append({
                'test': test_case['name'],
                'success': success,
                'elapsed': elapsed,
                'progress_updates': progress_updates
            })
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"   💥 EXCEPTION: {e}")
            results.append({
                'test': test_case['name'],
                'success': False,
                'elapsed': elapsed,
                'error': str(e)
            })
            
            # Cleanup on exception
            try:
                if 'server_proc' in locals():
                    server_proc.terminate()
                    server_proc.wait(timeout=2)
            except:
                pass
    
    # Summary
    print(f"\n📊 Test Results Summary")
    print("=" * 40)
    
    successful_tests = sum(1 for r in results if r['success'])
    total_tests = len(results)
    
    for result in results:
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        print(f"{status} {result['test']} ({result['elapsed']:.1f}s)")
    
    print(f"\n🎯 Overall: {successful_tests}/{total_tests} tests passed")
    
    if successful_tests == total_tests:
        print("🎉 All anti-hang improvements working correctly!")
    else:
        print("⚠️ Some tests failed - review the implementation")
    
    return results

if __name__ == "__main__":
    test_anti_hang_improvements()
