#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# safe_shell_mcp.py - Secure STDIO MCP server for shell tasks (Python 3.8+)

import argparse, json, os, re, subprocess, sys, traceback, datetime, threading, queue, time, uuid
from pathlib import Path

# ============================================================================== CLI Config ==============================================================================
parser = argparse.ArgumentParser(description="Secure STDIO MCP Shell Server")
parser.add_argument("--saferoot", "-r", required=True, help="Restrict access to this folder only")
parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging to stderr")
args = parser.parse_args()
SAFE_ROOT = Path(args.saferoot).resolve()
DEBUG_MODE = args.debug
DEFAULT_TIMEOUT = 3600
STREAMING_TIMEOUT = 300  # Longer timeout for streaming operations
BACKGROUND_TASK_TIMEOUT = 3600  # 1 hour for background tasks
# Version tracking - increment this when making changes to verify correct loading
BUILD_VERSION = "2025-07-02-v3.0-STREAMING-ROBUST"
SERVER = {"name": "safe-shell-mcp", "version": "1.2.0", "build": BUILD_VERSION}

if not SAFE_ROOT.is_dir():
    sys.stderr.write(f"❌ SAFE_ROOT '{SAFE_ROOT}' must exist and be a directory.\n")
    sys.exit(1)

# ============================================================================== Debug Logging ==============================================================================
def _debug_log(message):
    """Write debug message to stderr if debug mode is enabled"""
    if DEBUG_MODE:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        sys.stderr.write(f"[DEBUG {timestamp}] {message}\n")
        sys.stderr.flush()

# ============================================================================== Background Task Management ==============================================================================
# Global background task registry
BACKGROUND_TASKS = {}
TASK_LOCK = threading.Lock()

class BackgroundTask:
    """Manages background task execution with status tracking"""
    def __init__(self, task_id, command, timeout=BACKGROUND_TASK_TIMEOUT):
        self.task_id = task_id
        self.command = command
        self.timeout = timeout
        self.status = "pending"  # pending, running, completed, failed, timeout
        self.process = None
        self.output_queue = queue.Queue()
        self.start_time = None
        self.end_time = None
        self.exit_code = None
        self.thread = None
        
    def start(self):
        """Start the background task"""
        self.status = "running"
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._run_task)
        self.thread.daemon = True
        self.thread.start()
        _debug_log(f"Started background task {self.task_id}")
        
    def _run_task(self):
        """Internal method to run the task"""
        try:
            _debug_log(f"Executing background command: {self.command}")
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                cwd=str(SAFE_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output line by line
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    self.output_queue.put(line.rstrip())
                
            self.process.wait()
            self.exit_code = self.process.returncode
            self.end_time = time.time()
            
            if self.exit_code == 0:
                self.status = "completed"
            else:
                self.status = "failed"
                
        except Exception as e:
            _debug_log(f"Background task {self.task_id} failed: {e}")
            self.status = "failed"
            self.output_queue.put(f"ERROR: {str(e)}")
            self.end_time = time.time()
            
    def get_status(self):
        """Get current task status with timing info"""
        elapsed = None
        if self.start_time:
            end_time = self.end_time or time.time()
            elapsed = end_time - self.start_time
            
        return {
            "task_id": self.task_id,
            "status": self.status,
            "command": self.command,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "elapsed_seconds": elapsed,
            "exit_code": self.exit_code
        }
        
    def get_output(self, max_lines=None):
        """Get accumulated output from the task"""
        lines = []
        try:
            while not self.output_queue.empty():
                lines.append(self.output_queue.get_nowait())
                if max_lines and len(lines) >= max_lines:
                    break
        except queue.Empty:
            pass
        return lines
        
    def terminate(self):
        """Terminate the running task"""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.status = "terminated"
            self.end_time = time.time()

def _create_background_task(command):
    """Create and register a new background task"""
    task_id = str(uuid.uuid4())[:8]
    task = BackgroundTask(task_id, command)
    
    with TASK_LOCK:
        BACKGROUND_TASKS[task_id] = task
        
    task.start()
    return task_id

def _get_background_task(task_id):
    """Get background task by ID"""
    with TASK_LOCK:
        return BACKGROUND_TASKS.get(task_id)

def _cleanup_completed_tasks():
    """Clean up old completed tasks"""
    with TASK_LOCK:
        current_time = time.time()
        to_remove = []
        
        for task_id, task in BACKGROUND_TASKS.items():
            if task.status in ["completed", "failed", "terminated"] and task.end_time:
                # Remove tasks older than 1 hour
                if current_time - task.end_time > 3600:
                    to_remove.append(task_id)
                    
        for task_id in to_remove:
            del BACKGROUND_TASKS[task_id]
            _debug_log(f"Cleaned up old task {task_id}")

# ============================================================================== Streaming Output ==============================================================================
def _stream_command_output(command, request_id, timeout=STREAMING_TIMEOUT):
    """Execute command with streaming output and progress updates"""
    _debug_log(f"Starting streaming command: {command}")
    
    try:
        # Send initial progress
        _progress(request_id, f"🚀 Starting command: {command}")
        
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=str(SAFE_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        output_lines = []
        start_time = time.time()
        
        # Stream output line by line
        for line in iter(process.stdout.readline, ''):
            if line:
                line = line.rstrip()
                output_lines.append(line)
                
                # Send progress update every few lines or for important lines
                if len(output_lines) % 10 == 0 or any(keyword in line.lower() for keyword in ['error', 'warning', 'complete', 'done', 'finished']):
                    elapsed = time.time() - start_time
                    _progress(request_id, f"📊 Line {len(output_lines)}: {line[:100]}{'...' if len(line) > 100 else ''} [%.1fs]" % elapsed)
                
                # Check timeout
                if time.time() - start_time > timeout:
                    process.terminate()
                    output_lines.append(f"⏱️ Command terminated after {timeout}s timeout")
                    break
        
        process.wait()
        exit_code = process.returncode
        elapsed = time.time() - start_time
        
        # Final status
        if exit_code == 0:
            _progress(request_id, f"✅ Command completed successfully in %.1fs" % elapsed)
        else:
            _progress(request_id, f"❌ Command failed with exit code {exit_code} after %.1fs" % elapsed)
            output_lines.append(f"[Exit code: {exit_code}]")
        
        return "\n".join(output_lines)
        
    except Exception as e:
        _debug_log(f"Streaming command failed: {e}")
        _progress(request_id, f"💥 Command failed: {str(e)}")
        return f"❌ Streaming execution failed: {e}"

def _detect_interactive_command(command):
    """Detect if a command might require user input"""
    interactive_patterns = [
        r'\bsudo\b',           # sudo prompts for password
        r'\bssh\b',            # ssh might prompt for password/confirmation
        r'\bgit\s+push\b',     # git push might prompt for credentials
        r'\bapt\s+install\b',  # apt install might prompt for confirmation
        r'\byum\s+install\b',  # yum install might prompt for confirmation
        r'\bpip\s+install\b',  # pip install might prompt for confirmation
        r'\bnpm\s+install\b',  # npm install might prompt for confirmation
        r'\bread\b',           # read command waits for input
        r'\bselect\b',         # select menu
        r'\bconfirm\b',        # confirmation prompts
        r'\b--interactive\b',  # explicit interactive flag
        r'\b-i\b',             # common interactive flag
    ]
    
    for pattern in interactive_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False

# ============================================================================== Core MCP Utilities ==============================================================================
def _send(msg): 
    _debug_log(f"Sending MCP message: {json.dumps(msg, separators=(',', ':'))}")
    json.dump(msg, sys.stdout, separators=(",", ":")); sys.stdout.write("\n"); sys.stdout.flush()
def _result(rid, payload): _send({"jsonrpc": "2.0", "id": rid, "result": payload})
def _error(rid, code, msg, data=None): _send({"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg, "data": data}})
def _progress(rid, text): _send({"jsonrpc": "2.0", "method": "$/progress", "params": {"id": rid, "output": text}})
def _read(): 
    line = sys.stdin.readline()
    if line:
        try:
            msg = json.loads(line)
            _debug_log(f"Received MCP message: {json.dumps(msg, separators=(',', ':'))}")
            return msg
        except json.JSONDecodeError as e:
            _debug_log(f"Failed to parse JSON: {e}")
            return None
    return None
def _shell_cwd(): return str(SAFE_ROOT)
def _safe_resolve(p):
    _debug_log(f"Resolving path: {p}")
    
    # Handle relative paths
    if not os.path.isabs(p):
        full = (SAFE_ROOT / p).resolve()
    else:
        # Handle absolute paths - just use as-is after security check
        full = Path(p).resolve()
    
    # Security check: ensure the resolved path is within SAFE_ROOT
    if not str(full).startswith(str(SAFE_ROOT)):
        _debug_log(f"Path access denied: {full}")
        raise PermissionError(f"Path '{full}' blocked - outside safe root {SAFE_ROOT}")
    
    _debug_log(f"Path resolved to: {full}")
    return full

# ============================================================================== Shell Executors ==============================================================================
def _safe_subprocess_run(cmd_list):
    """Safely run subprocess commands with proper error handling"""
    try:
        _debug_log(f"Running command: {' '.join(cmd_list)}")
        result = subprocess.run(
            cmd_list,
            cwd=_shell_cwd(),
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT
        )
        
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
            
        _debug_log(f"Command completed with return code: {result.returncode}")
        
        if result.returncode != 0:
            output += f"\n[Exit code: {result.returncode}]"
            
        return output.strip()
        
    except subprocess.TimeoutExpired:
        _debug_log(f"Command timed out after {DEFAULT_TIMEOUT}s")
        return f"⏱️ Command timed out after {DEFAULT_TIMEOUT}s"
    except FileNotFoundError as e:
        _debug_log(f"Command not found: {e}")
        return f"❌ Command not found: {' '.join(cmd_list)}"
    except Exception as e:
        _debug_log(f"Command execution failed: {e}")
        return f"❌ Command execution failed: {e}"

def _execute_shell(command):
    """Execute shell command and return complete output (non-streaming)"""
    _debug_log(f"Executing shell command: {command}")
    _debug_log(f"Working directory: {_shell_cwd()}")
    
    try:
        # Use subprocess.run for complete output collection
        result = subprocess.run(
            command, 
            shell=True, 
            cwd=_shell_cwd(),
            capture_output=True, 
            text=True, 
            timeout=DEFAULT_TIMEOUT
        )
        
        # Combine stdout and stderr
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
            
        _debug_log(f"Command completed with return code: {result.returncode}")
        _debug_log(f"Output length: {len(output)} characters")
        
        # If command failed, include return code info
        if result.returncode != 0:
            output += f"\n[Exit code: {result.returncode}]"
            
        return output.strip()
        
    except subprocess.TimeoutExpired:
        _debug_log(f"Command timed out after {DEFAULT_TIMEOUT}s")
        return f"⏱️ Command timed out after {DEFAULT_TIMEOUT}s"
    except Exception as e:
        _debug_log(f"Command execution failed: {e}")
        return f"❌ Command execution failed: {e}"

def _run_shell_handler(params):
    """Handle shell command execution with streaming and interactive detection"""
    command = params["command"]
    stream = params.get("stream", False)
    background = params.get("background", False)
    request_id = params.get("request_id", "default")
    
    _debug_log(f"Shell command: {command} (stream={stream}, background={background})")
    
    # Check for interactive commands and warn
    if _detect_interactive_command(command):
        warning = f"⚠️ WARNING: Command '{command}' may require user input and could hang. Consider using non-interactive alternatives."
        _debug_log(warning)
        
        # For interactive commands, prefer non-streaming mode unless explicitly requested
        if not stream and not background:
            return f"{warning}\n\n" + _execute_shell(command)
    
    # Handle background tasks
    if background:
        task_id = _create_background_task(command)
        _cleanup_completed_tasks()  # Clean up old tasks
        return f"🔄 Background task started with ID: {task_id}\nUse 'task_status' or 'task_output' tools to check progress."
    
    # Handle streaming output
    if stream:
        return _stream_command_output(command, request_id)
    
    # Default: non-streaming execution
    return _execute_shell(command)

def _grep_file_handler(params):
    """Handle grep file with proper debug logging"""
    pattern = params["pattern"]
    filepath = params["filepath"]
    _debug_log(f"Grep file: pattern='{pattern}', file='{filepath}'")
    resolved_path = _safe_resolve(filepath)
    return _safe_subprocess_run(["grep", "-n", pattern, str(resolved_path)])

def _cat_file_handler(params):
    """Handle cat file with proper debug logging"""
    filepath = params["filepath"]
    _debug_log(f"Cat file: {filepath}")
    resolved_path = _safe_resolve(filepath)
    return _safe_subprocess_run(["cat", str(resolved_path)])

def _sed_search_handler(params):
    """Handle sed search with proper debug logging"""
    script = params["script"]
    filepath = params["filepath"]
    _debug_log(f"Sed search: script='{script}', file='{filepath}'")
    resolved_path = _safe_resolve(filepath)
    return _safe_subprocess_run(["sed", "-n", script, str(resolved_path)])

def _list_dir_handler(params):
    """Handle directory listing with proper debug logging"""
    path = params.get("path", ".")
    _debug_log(f"List directory: {path}")
    resolved_path = _safe_resolve(path)
    return _safe_subprocess_run(["ls", "-la", str(resolved_path)])

def _file_search_handler(params):
    """Handle file search with proper error handling"""
    try:
        pattern = params["pattern"]
        root = params.get("root", ".")
        _debug_log(f"File search: pattern='{pattern}', root='{root}'")
        
        root_path = _safe_resolve(root)
        matches = []
        
        for dp, _, fs in os.walk(root_path):
            for f in fs:
                if re.search(pattern, f):
                    matches.append(os.path.join(dp, f))
        
        result = "\n".join(matches) if matches else "No matches"
        _debug_log(f"File search found {len(matches)} matches")
        return result
        
    except Exception as e:
        _debug_log(f"File search failed: {e}")
        return f"❌ File search failed: {e}"

def _descriptor(name, desc, params, out_type="text", required=None):
    if required is None: required = list(params.keys())
    return {
        "name": name, "description": desc,
        "inputSchema": {"type": "object", "properties": params, "required": required},
        "outputSchema": {
            "type": "object", "properties": {
                "content": {
                    "type": "array",
                    "items": {"type": "object", "properties": {
                        "type": {"const": out_type},
                        "text": {"type": "string"}}}}}, "required": ["content"]
        }
    }

# ============================================================================== Tool Registry ==============================================================================
TOOLS = {
    "run_shell": {
        "desc": _descriptor("run_shell", "Shell command execution with streaming/background support", {
            "command": {"type": "string"},
            "stream": {"type": "boolean", "description": "Enable streaming output with progress updates"},
            "background": {"type": "boolean", "description": "Run command in background"},
            "request_id": {"type": "string", "description": "Request ID for progress tracking"}
        }, required=["command"]),
        "handler": lambda params: _run_shell_handler(params),
    },
    "run_raw": {
        "desc": _descriptor("run_raw", "Shell command raw output", {"command": {"type": "string"}}),
        "handler": lambda params: _run_shell_handler(params),
    },
    "task_status": {
        "desc": _descriptor("task_status", "Get background task status", {
            "task_id": {"type": "string", "description": "Background task ID"}
        }),
        "handler": lambda params: _handle_task_status(params),
    },
    "task_output": {
        "desc": _descriptor("task_output", "Get background task output", {
            "task_id": {"type": "string", "description": "Background task ID"},
            "max_lines": {"type": "integer", "description": "Maximum lines to return"}
        }, required=["task_id"]),
        "handler": lambda params: _handle_task_output(params),
    },
    "task_list": {
        "desc": _descriptor("task_list", "List all background tasks", {}),
        "handler": lambda params: _handle_task_list(params),
    },
    "task_terminate": {
        "desc": _descriptor("task_terminate", "Terminate a background task", {
            "task_id": {"type": "string", "description": "Background task ID"}
        }),
        "handler": lambda params: _handle_task_terminate(params),
    },
    "file_search": {
        "desc": _descriptor("file_search", "Regex search in files", {
            "pattern": {"type": "string"}, "root": {"type": "string"}}),
        "handler": lambda params: _file_search_handler(params),
    },
    "list_dir": {
        "desc": _descriptor("list_dir", "`ls -la` on path", {"path": {"type": "string"}}, required=[]),
        "handler": lambda params: _list_dir_handler(params),
    },
    "print_workdir": {
        "desc": _descriptor("print_workdir", "Show working dir", {}),
        "handler": lambda params: (
            _debug_log("Print working directory") or
            str(SAFE_ROOT)
        ),
    },
    "grep_file": {
        "desc": _descriptor("grep_file", "Grep pattern with line numbers", {
            "pattern": {"type": "string"}, "filepath": {"type": "string"}}),
        "handler": lambda params: _grep_file_handler(params),
    },
    "cat_file": {
        "desc": _descriptor("cat_file", "Read full file", {
            "filepath": {"type": "string"}}),
        "handler": lambda params: _cat_file_handler(params),
    },
    "sed_search": {
        "desc": _descriptor("sed_search", "Run sed read-only script", {
            "script": {"type": "string"}, "filepath": {"type": "string"}}),
        "handler": lambda params: _sed_search_handler(params),
    },
    "version": {
        "desc": _descriptor("version", "Show server version and build info", {}),
        "handler": lambda params: (
            _debug_log("Version info requested") or
            f"Server: {SERVER['name']} v{SERVER['version']}\nBuild: {BUILD_VERSION}\nSafe Root: {SAFE_ROOT}\nDebug Mode: {DEBUG_MODE}"
        ),
    }
}

# ============================================================================== MCP Handlers ==============================================================================
def _handle_initialize(rid, _): 
    _debug_log("Handling initialize request")
    _result(rid, {"serverInfo": SERVER, "capabilities": {"tools": True}})

def _handle_tools_list(rid): 
    _debug_log("Handling tools/list request")
    _result(rid, {"tools": [t["desc"] for t in TOOLS.values()]})

def _handle_tools_call(rid, prm):
    name = prm.get("name")
    # Handle both 'params' and 'arguments' - VS Code sometimes uses different formats
    args = prm.get("params", {})
    if not args:
        args = prm.get("arguments", {})
    
    _debug_log(f"Handling tools/call request: {name} with args: {args}")
    
    if name not in TOOLS:
        _debug_log(f"Unknown tool requested: {name}")
        return _error(rid, -32601, f"Unknown tool '{name}'")
    
    try:
        tool = TOOLS[name]
        _debug_log(f"Executing tool: {name}")
        
        # Add request ID to args for progress tracking
        if "request_id" not in args:
            args["request_id"] = str(rid)
            
        # Execute the tool handler
        output = tool["handler"](args)
        _debug_log(f"Tool execution completed successfully")
        
        # Return raw text content
        final = {"content": [{"type": "text", "text": output}]}
        _result(rid, final)
        
    except PermissionError as e:
        _debug_log(f"Permission error: {e}")
        _error(rid, -32010, "Access denied", str(e))
    except subprocess.CalledProcessError as e:
        _debug_log(f"Command failed: {e}")
        _error(rid, -32020, "Command failed", e.output)
    except subprocess.TimeoutExpired:
        _debug_log(f"Command timeout")
        _error(rid, -32030, "Timeout", f"Exceeded {DEFAULT_TIMEOUT}s")
    except Exception as e:
        _debug_log(f"Unhandled exception: {e}")
        _error(rid, -32000, "Unhandled exception", traceback.format_exc())

def _handle_task_status(params):
    """Handle task status request"""
    task_id = params["task_id"]
    _debug_log(f"Getting task status for: {task_id}")
    
    task = _get_background_task(task_id)
    if not task:
        return f"❌ Task '{task_id}' not found"
    
    status = task.get_status()
    
    # Format status nicely
    result = f"📋 Task Status: {task_id}\n"
    result += f"   Command: {status['command']}\n"
    result += f"   Status: {status['status']}\n"
    
    if status['start_time']:
        start_time = datetime.datetime.fromtimestamp(status['start_time']).strftime("%Y-%m-%d %H:%M:%S")
        result += f"   Started: {start_time}\n"
    
    if status['end_time']:
        end_time = datetime.datetime.fromtimestamp(status['end_time']).strftime("%Y-%m-%d %H:%M:%S")
        result += f"   Finished: {end_time}\n"
    
    if status['elapsed_seconds']:
        result += f"   Duration: {status['elapsed_seconds']:.1f}s\n"
    
    if status['exit_code'] is not None:
        result += f"   Exit Code: {status['exit_code']}\n"
    
    return result

def _handle_task_output(params):
    """Handle task output request"""
    task_id = params["task_id"]
    max_lines = params.get("max_lines")
    _debug_log(f"Getting task output for: {task_id} (max_lines={max_lines})")
    
    task = _get_background_task(task_id)
    if not task:
        return f"❌ Task '{task_id}' not found"
    
    output_lines = task.get_output(max_lines)
    
    if not output_lines:
        return f"📄 No output available for task {task_id} (status: {task.status})"
    
    result = f"📄 Output for task {task_id} ({len(output_lines)} lines):\n"
    result += "=" * 50 + "\n"
    result += "\n".join(output_lines)
    
    if max_lines and len(output_lines) >= max_lines:
        result += f"\n... (truncated at {max_lines} lines)"
    
    return result

def _handle_task_list(params):
    """Handle task list request"""
    _debug_log("Listing all background tasks")
    
    with TASK_LOCK:
        if not BACKGROUND_TASKS:
            return "📝 No background tasks found"
        
        result = f"📝 Background Tasks ({len(BACKGROUND_TASKS)} total):\n"
        result += "=" * 50 + "\n"
        
        for task_id, task in BACKGROUND_TASKS.items():
            status = task.get_status()
            elapsed = status['elapsed_seconds']
            elapsed_str = f"{elapsed:.1f}s" if elapsed else "0s"
            
            result += f"• {task_id}: {status['status']} ({elapsed_str}) - {status['command'][:60]}{'...' if len(status['command']) > 60 else ''}\n"
    
    return result

def _handle_task_terminate(params):
    """Handle task termination request"""
    task_id = params["task_id"]
    _debug_log(f"Terminating task: {task_id}")
    
    task = _get_background_task(task_id)
    if not task:
        return f"❌ Task '{task_id}' not found"
    
    if task.status in ["completed", "failed", "terminated"]:
        return f"⚠️ Task '{task_id}' is already {task.status}"
    
    task.terminate()
    return f"🛑 Task '{task_id}' has been terminated"
    
# ============================================================================== Main Loop ==============================================================================
def main():
    _debug_log(f"🚀 Starting MCP server - Build: {BUILD_VERSION}")
    _debug_log(f"Server: {SERVER['name']} v{SERVER['version']}")
    _debug_log(f"Safe Root: {SAFE_ROOT}")
    _debug_log(f"Debug mode: {DEBUG_MODE}")
    
    # Always log version to stderr for easy identification
    sys.stderr.write(f"🔧 MCP Shell Server {BUILD_VERSION} - Safe Root: {SAFE_ROOT}\n")
    sys.stderr.flush()
    
    while True:
        msg = _read()
        if not msg: 
            _debug_log("No message received, breaking main loop")
            break
            
        m, rid, prm = msg.get("method"), msg.get("id"), msg.get("params", {})
        _debug_log(f"Processing method: {m}, id: {rid}")
        
        try:
            if m == "initialize": 
                _handle_initialize(rid, prm)
            elif m == "tools/list": 
                _handle_tools_list(rid)
            elif m == "tools/call": 
                _handle_tools_call(rid, prm)
            elif m == "shutdown": 
                _debug_log("Shutdown requested")
                _result(rid, {})
            elif m == "exit": 
                _debug_log("Exit requested")
                break
            else: 
                _debug_log(f"Unknown method: {m}")
                _error(rid, -32601, f"Unknown method: {m}")
        except Exception as e: 
            _debug_log(f"Unhandled MCP error: {e}")
            _error(rid, -32099, "Unhandled MCP error", traceback.format_exc())

if __name__ == "__main__":
    try: 
        main()
    except KeyboardInterrupt: 
        _debug_log("Interrupted by user")
        pass
