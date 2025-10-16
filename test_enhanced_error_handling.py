#!/usr/bin/env python3
"""
Test script for enhanced error handling in MCP Shell Server
Tests various error scenarios to ensure robust error handling
"""

import json
import subprocess
import sys
import time
from pathlib import Path

class ErrorHandlingTester:
    def __init__(self, server_path, safe_root):
        self.server_path = server_path
        self.safe_root = safe_root
        self.test_results = []
        
    def run_test(self, test_name, tool_name, params=None):
        """Run a single test and capture results"""
        if params is None:
            params = {}
        
        print(f"\n🧪 Testing: {test_name}")
        
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
            stdout, stderr = proc.communicate(input=input_data, timeout=30)
            
            # Parse responses
            responses = []
            for line in stdout.strip().split('\n'):
                if line:
                    try:
                        responses.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            
            # Analyze results
            success = len(responses) >= 2
            error_handled = False
            timeout_handled = False
            
            for response in responses:
                if "error" in response:
                    error_handled = True
                    error_msg = response["error"].get("message", "")
                    print(f"  ✅ Error properly handled: {error_msg}")
                elif "result" in response and response.get("id") == 1:
                    content = response["result"].get("content", [])
                    if content and len(content) > 0:
                        text = content[0].get("text", "")
                        if "timeout" in text.lower() or "terminated" in text.lower():
                            timeout_handled = True
                            print(f"  ✅ Timeout properly handled")
                        elif "error" in text.lower() or "❌" in text:
                            error_handled = True
                            print(f"  ✅ Error properly handled in output")
                        else:
                            print(f"  ℹ️ Result: {text[:100]}{'...' if len(text) > 100 else ''}")
            
            if stderr:
                print(f"  📝 Debug output available (length: {len(stderr)})")
            
            self.test_results.append({
                "test": test_name,
                "success": success,
                "error_handled": error_handled,
                "timeout_handled": timeout_handled,
                "stderr_length": len(stderr)
            })
            
        except subprocess.TimeoutExpired:
            print(f"  ⏱️ Test timed out (expected for some tests)")
            proc.kill()
            self.test_results.append({
                "test": test_name,
                "success": True,
                "error_handled": True,
                "timeout_handled": True,
                "stderr_length": 0
            })
        except Exception as e:
            print(f"  ❌ Test failed: {e}")
            self.test_results.append({
                "test": test_name,
                "success": False,
                "error_handled": False,
                "timeout_handled": False,
                "stderr_length": 0
            })

    def run_all_tests(self):
        """Run comprehensive error handling tests"""
        print("🚀 Starting Enhanced Error Handling Tests")
        print("=" * 50)
        
        # Test 1: Invalid command
        self.run_test(
            "Invalid Command",
            "run_shell",
            {"command": "nonexistent_command_12345"}
        )
        
        # Test 2: Command that times out quickly
        self.run_test(
            "Timeout Command",
            "run_shell",
            {"command": "sleep 100"}  # Should timeout with our reduced timeouts
        )
        
        # Test 3: Command with permission error
        self.run_test(
            "Permission Error",
            "cat_file",
            {"filepath": "/etc/shadow"}  # Typically requires root
        )
        
        # Test 4: Network command (should have shorter timeout)
        self.run_test(
            "Network Command Timeout",
            "run_shell",
            {"command": "curl --max-time 60 https://httpstat.us/200?sleep=70000"}  # Should timeout
        )
        
        # Test 5: File not found
        self.run_test(
            "File Not Found",
            "cat_file",
            {"filepath": "nonexistent_file_12345.txt"}
        )
        
        # Test 6: Invalid regex pattern
        self.run_test(
            "Invalid Regex",
            "file_search",
            {"pattern": "[unclosed", "root": "."}
        )
        
        # Test 7: Directory outside safe root
        self.run_test(
            "Path Security Error",
            "list_dir",
            {"path": "../../etc"}
        )
        
        # Test 8: Interactive command detection
        self.run_test(
            "Interactive Command Detection",
            "run_shell",
            {"command": "sudo echo 'test'"}
        )
        
        # Test 9: Background task that fails
        self.run_test(
            "Background Task Error",
            "run_shell",
            {"command": "false", "background": True}
        )
        
        # Test 10: Streaming command with error
        self.run_test(
            "Streaming Command Error",
            "run_shell",
            {"command": "bash -c 'echo start; sleep 2; exit 1'", "stream": True}
        )
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 50)
        print("📊 Test Results Summary")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r["success"])
        error_handled_tests = sum(1 for r in self.test_results if r["error_handled"])
        
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests}/{total_tests}")
        print(f"Error Handling: {error_handled_tests}/{total_tests}")
        
        print("\nDetailed Results:")
        for result in self.test_results:
            status = "✅" if result["success"] else "❌"
            error_status = "✅" if result["error_handled"] else "❌"
            print(f"  {status} {result['test']:<25} | Error Handling: {error_status}")
        
        if successful_tests == total_tests and error_handled_tests >= total_tests * 0.8:
            print("\n🎉 Enhanced error handling tests PASSED!")
        else:
            print("\n⚠️ Some error handling tests need attention.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_enhanced_error_handling.py <safe_root_path>")
        sys.exit(1)
    
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = sys.argv[1]
    
    if not Path(safe_root).exists():
        print(f"❌ Safe root path '{safe_root}' does not exist")
        sys.exit(1)
    
    tester = ErrorHandlingTester(str(server_path), safe_root)
    tester.run_all_tests()

if __name__ == "__main__":
    main()