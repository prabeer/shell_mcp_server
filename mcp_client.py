#!/usr/bin/env python3
"""
Interactive MCP Shell Client
A terminal-based client for the MCP Shell Server
"""

import json
import subprocess
import sys
from pathlib import Path

class MCPShellClient:
    def __init__(self, server_path, safe_root):
        self.server_path = server_path
        self.safe_root = safe_root
        self.request_id = 0

    def call_tool(self, tool_name, params=None):
        if params is None:
            params = {}
        
        self.request_id += 1
        
        # Prepare messages
        init_msg = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {}
        }
        
        tool_msg = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            }
        }
        
        try:
            # Start MCP server
            proc = subprocess.Popen(
                ["python3", self.server_path, "--saferoot", self.safe_root],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Send messages
            input_data = json.dumps(init_msg) + "\n" + json.dumps(tool_msg) + "\n"
            stdout, stderr = proc.communicate(input=input_data, timeout=30)
            
            # Parse response
            lines = stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    try:
                        response = json.loads(line)
                        if response.get('id') == self.request_id and 'result' in response:
                            content = response['result'].get('content', [])
                            if content and content[0]:
                                return content[0].get('text', '')
                    except json.JSONDecodeError:
                        continue
            
            return f"Error: {stderr}" if stderr else "No valid response received"
            
        except subprocess.TimeoutExpired:
            proc.kill()
            return "Error: Command timed out"
        except Exception as e:
            return f"Error: {e}"

def print_banner():
    print("🐚 MCP Shell Interactive Client")
    print("=" * 40)
    print("Available commands:")
    print("  shell <command>     - Execute shell command")
    print("  ls [path]          - List directory")
    print("  cat <file>         - Read file content")
    print("  find <pattern>     - Search files by pattern")
    print("  pwd                - Show working directory")
    print("  help               - Show this help")
    print("  quit               - Exit client")
    print("=" * 40)

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 mcp_client.py <server_path> <safe_root>")
        sys.exit(1)
    
    server_path = sys.argv[1]
    safe_root = sys.argv[2]
    
    if not Path(server_path).exists():
        print(f"Error: Server path '{server_path}' does not exist")
        sys.exit(1)
    
    if not Path(safe_root).is_dir():
        print(f"Error: Safe root '{safe_root}' is not a directory")
        sys.exit(1)
    
    client = MCPShellClient(server_path, safe_root)
    print_banner()
    
    while True:
        try:
            command = input("mcp> ").strip()
            
            if not command:
                continue
            
            if command == "quit":
                print("👋 Goodbye!")
                break
            
            if command == "help":
                print_banner()
                continue
            
            parts = command.split(' ', 1)
            cmd = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            
            if cmd == "shell":
                if not args:
                    print("Error: shell command requires an argument")
                    continue
                result = client.call_tool("run_shell", {"command": args})
                print(result)
            
            elif cmd == "ls":
                path = args if args else "."
                result = client.call_tool("list_dir", {"path": path})
                print(result)
            
            elif cmd == "cat":
                if not args:
                    print("Error: cat command requires a file path")
                    continue
                result = client.call_tool("cat_file", {"filepath": args})
                print(result)
            
            elif cmd == "find":
                if not args:
                    print("Error: find command requires a search pattern")
                    continue
                result = client.call_tool("file_search", {"pattern": args, "root": "."})
                print(result)
            
            elif cmd == "pwd":
                result = client.call_tool("print_workdir")
                print(result)
            
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
        
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except EOFError:
            print("\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main()
