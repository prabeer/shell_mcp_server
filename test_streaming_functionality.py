#!/usr/bin/env python3
"""
Test script for streaming functionality
Demonstrates real-time streaming output capabilities
"""

import json
import subprocess
import sys
import time
from pathlib import Path

class StreamingTester:
    def __init__(self, server_path, safe_root):
        self.server_path = server_path
        self.safe_root = safe_root
        
    def test_streaming_vs_normal(self):
        """Compare streaming vs normal execution"""
        print("🧪 Testing Streaming vs Normal Execution")
        print("=" * 50)
        
        # Test command that produces output over time
        test_command = "for i in {1..5}; do echo \"Output line $i\"; sleep 1; done"
        
        print(f"\n📝 Test command: {test_command}")
        
        # Test 1: Normal execution
        print(f"\n1️⃣ Normal Execution (no streaming):")
        print("-" * 30)
        start_time = time.time()
        normal_result = self.send_mcp_command("run_shell", {"command": test_command})
        normal_time = time.time() - start_time
        print(f"Result:\n{normal_result}")
        print(f"⏱️ Execution time: {normal_time:.1f}s")
        
        # Test 2: Streaming execution
        print(f"\n2️⃣ Streaming Execution:")
        print("-" * 30)
        start_time = time.time()
        streaming_result = self.send_mcp_command("run_shell", {
            "command": test_command, 
            "stream": True
        })
        streaming_time = time.time() - start_time
        print(f"Result:\n{streaming_result}")
        print(f"⏱️ Execution time: {streaming_time:.1f}s")
        
        # Test 3: Long-running command with streaming
        print(f"\n3️⃣ Long-running Streaming Command:")
        print("-" * 40)
        long_command = "echo 'Starting long process'; for i in {1..10}; do echo \"Processing item $i/10\"; sleep 0.5; done; echo 'Process completed'"
        
        start_time = time.time()
        long_result = self.send_mcp_command("run_shell", {
            "command": long_command, 
            "stream": True
        })
        long_time = time.time() - start_time
        print(f"Result:\n{long_result}")
        print(f"⏱️ Execution time: {long_time:.1f}s")
        
        print(f"\n✅ Streaming tests completed!")
        print(f"\nKey Observations:")
        print(f"• Normal execution shows output only at completion")
        print(f"• Streaming execution shows progressive output with indicators")
        print(f"• Streaming provides real-time feedback and progress tracking")
        
    def send_mcp_command(self, tool_name, params=None):
        """Send a command to MCP server and get response"""
        if params is None:
            params = {}
        
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
            
            # Return the tool response
            for response in responses:
                if "result" in response and response.get("id") == 1:
                    content = response["result"].get("content", [])
                    if content and len(content) > 0:
                        return content[0].get("text", "")
            
            return "No valid response received"
            
        except subprocess.TimeoutExpired:
            proc.kill()
            return "Command timed out"
        except Exception as e:
            return f"Error: {e}"

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_streaming.py <safe_root_path>")
        sys.exit(1)
    
    server_path = Path(__file__).parent / "safe_shell_mcp.py"
    safe_root = sys.argv[1]
    
    if not Path(safe_root).exists():
        print(f"❌ Safe root path '{safe_root}' does not exist")
        sys.exit(1)
    
    tester = StreamingTester(str(server_path), safe_root)
    tester.test_streaming_vs_normal()

if __name__ == "__main__":
    main()