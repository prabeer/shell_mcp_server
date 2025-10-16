#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# safe_shell_mcp.py - Secure STDIO MCP server for shell tasks (Python 3.8+)

import argparse, json, os, re, subprocess, sys, traceback, datetime, threading, queue, time, uuid, select, signal, pickle, fcntl
from pathlib import Path

# ============================================================================== CLI Config ==============================================================================
parser = argparse.ArgumentParser(description="Secure STDIO MCP Shell Server")
parser.add_argument("--saferoot", "-r", required=True, help="Restrict access to this folder only")
parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging to stderr")
args = parser.parse_args()
SAFE_ROOT = Path(args.saferoot).resolve()
DEBUG_MODE = args.debug
DEFAULT_TIMEOUT = 300  # 5 minutes timeout for run_shell and run_raw commands
STREAMING_TIMEOUT = 180  # 3 minutes for streaming operations
BACKGROUND_TASK_TIMEOUT = 1800  # 30 minutes for background tasks
READLINE_TIMEOUT = 15  # 15 seconds for single line reads
NETWORK_COMMAND_TIMEOUT = 45  # 45 seconds for network commands
PROCESS_TERMINATION_TIMEOUT = 10  # Max time to wait for process termination
ERROR_RECOVERY_TIMEOUT = 5  # Time to wait for error recovery attempts
# Specific timeout constants for clarity
RUN_SHELL_TIMEOUT = 300  # 5 minutes - specific timeout for run_shell and run_raw commands
# Version tracking - increment this when making changes to verify correct loading
BUILD_VERSION = "2025-10-16-v6.0-PERSISTENT-BACKGROUND-TASKS"
SERVER = {"name": "safe-shell-mcp", "version": "1.4.0", "build": BUILD_VERSION}

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

# Persistent task storage
TASK_STORAGE_FILE = None  # Will be set based on SAFE_ROOT

def _get_task_storage_path():
    """Get the path for persistent task storage"""
    global TASK_STORAGE_FILE
    if TASK_STORAGE_FILE is None:
        TASK_STORAGE_FILE = SAFE_ROOT / ".mcp_background_tasks.json"
    return TASK_STORAGE_FILE

def _save_tasks_to_disk():
    """Save current background tasks to disk for persistence"""
    try:
        storage_path = _get_task_storage_path()
        tasks_data = {}
        
        with TASK_LOCK:
            for task_id, task in BACKGROUND_TASKS.items():
                # Only save serializable data
                task_data = {
                    "task_id": task.task_id,
                    "command": task.command,
                    "timeout": task.timeout,
                    "status": task.status,
                    "start_time": task.start_time,
                    "end_time": task.end_time,
                    "exit_code": task.exit_code,
                    "output_lines": task.get_output(),  # Get current output
                    "created_at": time.time()
                }
                tasks_data[task_id] = task_data
        
        # Atomic write with file locking
        temp_path = storage_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(tasks_data, f, indent=2)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        
        # Atomic rename
        temp_path.rename(storage_path)
        _debug_log(f"Saved {len(tasks_data)} tasks to disk")
        
    except Exception as e:
        _debug_log(f"Error saving tasks to disk: {e}")

def _load_tasks_from_disk():
    """Load background tasks from disk after server restart"""
    try:
        storage_path = _get_task_storage_path()
        if not storage_path.exists():
            _debug_log("No persistent task storage found")
            return
        
        with open(storage_path, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            tasks_data = json.load(f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        
        current_time = time.time()
        loaded_count = 0
        recovered_count = 0
        
        with TASK_LOCK:
            for task_id, task_data in tasks_data.items():
                # Skip very old tasks (older than 24 hours)
                if current_time - task_data.get("created_at", 0) > 86400:
                    continue
                
                # Create a restored background task
                restored_task = BackgroundTask(
                    task_data["task_id"], 
                    task_data["command"], 
                    task_data["timeout"]
                )
                
                # Restore state
                restored_task.status = task_data["status"]
                restored_task.start_time = task_data["start_time"]
                restored_task.end_time = task_data["end_time"]
                restored_task.exit_code = task_data["exit_code"]
                
                # Restore output
                for line in task_data.get("output_lines", []):
                    restored_task.output_queue.put(line)
                
                # If task was running, mark it as lost
                if restored_task.status == "running":
                    restored_task.status = "lost"
                    restored_task.end_time = current_time
                    restored_task.output_queue.put("[Task was running when server restarted - marked as lost]")
                    recovered_count += 1
                
                BACKGROUND_TASKS[task_id] = restored_task
                loaded_count += 1
        
        _debug_log(f"Loaded {loaded_count} tasks from disk ({recovered_count} marked as lost)")
        
        # Clean up old entries and resave
        if loaded_count > 0:
            _save_tasks_to_disk()
        
    except Exception as e:
        _debug_log(f"Error loading tasks from disk: {e}")

def _cleanup_task_storage():
    """Clean up old task storage entries"""
    try:
        storage_path = _get_task_storage_path()
        if storage_path.exists():
            current_time = time.time()
            
            with open(storage_path, 'r') as f:
                tasks_data = json.load(f)
            
            # Remove tasks older than 24 hours
            cleaned_data = {}
            for task_id, task_data in tasks_data.items():
                if current_time - task_data.get("created_at", 0) <= 86400:
                    cleaned_data[task_id] = task_data
            
            if len(cleaned_data) != len(tasks_data):
                with open(storage_path, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    json.dump(cleaned_data, f, indent=2)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                _debug_log(f"Cleaned up task storage: {len(tasks_data)} -> {len(cleaned_data)} tasks")
    
    except Exception as e:
        _debug_log(f"Error cleaning up task storage: {e}")

class BackgroundTask:
    """Manages background task execution with status tracking and persistence"""
    def __init__(self, task_id, command, timeout=BACKGROUND_TASK_TIMEOUT):
        self.task_id = task_id
        self.command = command
        self.timeout = timeout
        self.status = "pending"  # pending, running, completed, failed, timeout, lost
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
        _save_tasks_to_disk()  # Save state when task starts
        
    def _run_task(self):
        """Internal method to run the task - ENHANCED VERSION WITH BETTER ERROR HANDLING"""
        try:
            _debug_log(f"Executing background command: {self.command}")
            self.process = subprocess.Popen(
                ["/bin/bash", "-c", self.command],
                cwd=str(SAFE_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # Create new process group
            )
            
            # Read output line by line with enhanced timeout protection
            last_output_time = time.time()
            error_count = 0
            max_errors = 5
            total_timeout = time.time() + self.timeout
            
            while True:
                current_time = time.time()
                
                # Check global timeout first
                if current_time > total_timeout:
                    _debug_log(f"Background task {self.task_id} hit global timeout ({self.timeout}s)")
                    self.output_queue.put(f"⏱️ Task timed out after {self.timeout}s")
                    self.status = "timeout"
                    _terminate_process_group(self.process)
                    break
                
                line = _read_with_timeout(self.process, READLINE_TIMEOUT)
                
                if line is not None:
                    if line:  # Non-empty line
                        self.output_queue.put(line.rstrip())
                        last_output_time = current_time
                        error_count = 0  # Reset error count on successful read
                    # Continue reading
                else:
                    # Timeout on readline - enhanced error handling
                    error_count += 1
                    
                    if self.process.poll() is not None:
                        break  # Process has ended
                    
                    # Check if we've been stuck too long
                    if current_time - last_output_time > READLINE_TIMEOUT * 3:
                        _debug_log(f"Background task {self.task_id} appears stuck (no output for {current_time - last_output_time:.1f}s)")
                        
                        # Try to detect if process is in error state
                        try:
                            # Send a gentle signal to check responsiveness
                            self.process.send_signal(signal.SIGCONT if hasattr(signal, 'SIGCONT') else signal.SIGTERM)
                            time.sleep(ERROR_RECOVERY_TIMEOUT)
                        except (OSError, ProcessLookupError):
                            _debug_log(f"Process {self.process.pid} appears to be dead")
                            break
                        
                        if error_count >= max_errors:
                            _debug_log(f"Background task {self.task_id} exceeded max errors ({max_errors})")
                            self.output_queue.put("🛑 Task terminated - too many consecutive errors")
                            self.status = "failed"
                            _terminate_process_group(self.process)
                            break
                        
                        self.output_queue.put("⚠️ Task appears to be stuck - attempting recovery")
                        last_output_time = current_time  # Reset to avoid spam
                
                # Check if process has ended
                if self.process.poll() is not None:
                    # Read any remaining output with timeout protection
                    try:
                        remaining_start = time.time()
                        while time.time() - remaining_start < ERROR_RECOVERY_TIMEOUT:
                            remaining = self.process.stdout.readline()
                            if not remaining:
                                break
                            if remaining.strip():
                                self.output_queue.put(remaining.strip())
                    except Exception as e:
                        _debug_log(f"Error reading remaining output: {e}")
                    break
            
            # Enhanced process completion handling
            try:
                self.process.wait(timeout=PROCESS_TERMINATION_TIMEOUT)
            except subprocess.TimeoutExpired:
                _debug_log(f"Process {self.process.pid} didn't terminate cleanly, force killing")
                _terminate_process_group(self.process)
                self.process.wait()
            
            self.exit_code = self.process.returncode
            self.end_time = time.time()
            
            # Enhanced status determination
            if self.status == "timeout":
                pass  # Already set above
            elif self.exit_code == 0:
                self.status = "completed"
            elif self.exit_code == -9 or self.exit_code == -15:  # SIGKILL or SIGTERM
                self.status = "terminated"
                self.output_queue.put(f"[Process was terminated with signal {abs(self.exit_code)}]")
            else:
                self.status = "failed"
                self.output_queue.put(f"[Process failed with exit code {self.exit_code}]")
                
        except subprocess.CalledProcessError as e:
            _debug_log(f"Background task {self.task_id} subprocess error: {e}")
            self.status = "failed"
            self.output_queue.put(f"SUBPROCESS ERROR: {str(e)}")
            if hasattr(e, 'output') and e.output:
                self.output_queue.put(f"Command output: {e.output}")
            self.end_time = time.time()
        except OSError as e:
            _debug_log(f"Background task {self.task_id} OS error: {e}")
            self.status = "failed"
            self.output_queue.put(f"OS ERROR: {str(e)} - Command may not exist or insufficient permissions")
            self.end_time = time.time()
        except Exception as e:
            _debug_log(f"Background task {self.task_id} unexpected error: {e}")
            self.status = "failed"
            self.output_queue.put(f"UNEXPECTED ERROR: {str(e)}")
            self.end_time = time.time()
        finally:
            # Save task state when it completes
            try:
                _save_tasks_to_disk()
            except Exception as e:
                _debug_log(f"Error saving task state on completion: {e}")
            
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
        """Terminate the running task with escalating force - ENHANCED VERSION"""
        if self.process and self.process.poll() is None:
            try:
                _debug_log(f"Terminating background task {self.task_id}")
                _terminate_process_group(self.process)
                self.status = "terminated"
                self.end_time = time.time()
                
            except Exception as e:
                _debug_log(f"Error terminating task {self.task_id}: {e}")
                self.status = "terminated"  # Mark as terminated even if there was an error
                self.end_time = time.time()
            finally:
                # Save task state when terminated
                try:
                    _save_tasks_to_disk()
                except Exception as e:
                    _debug_log(f"Error saving task state on termination: {e}")

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
    """Clean up old completed tasks from memory and disk"""
    with TASK_LOCK:
        current_time = time.time()
        to_remove = []
        
        for task_id, task in BACKGROUND_TASKS.items():
            if task.status in ["completed", "failed", "terminated", "lost"] and task.end_time:
                # Remove tasks older than 1 hour
                if current_time - task.end_time > 3600:
                    to_remove.append(task_id)
                    
        for task_id in to_remove:
            del BACKGROUND_TASKS[task_id]
            _debug_log(f"Cleaned up old task {task_id}")
    
    # Also clean up disk storage if we removed any tasks
    if to_remove:
        try:
            _save_tasks_to_disk()
            _cleanup_task_storage()
        except Exception as e:
            _debug_log(f"Error cleaning up task storage: {e}")

# ============================================================================== Streaming Output ==============================================================================
def _stream_command_output(command, request_id, timeout=STREAMING_TIMEOUT):
    """Execute command with streaming output and progress updates - ENHANCED ERROR HANDLING VERSION"""
    _debug_log(f"Starting streaming command: {command}")
    
    # Determine appropriate timeout based on command type
    effective_timeout = timeout
    if _detect_network_command(command):
        effective_timeout = min(timeout, NETWORK_COMMAND_TIMEOUT)
        _debug_log(f"Network command detected, using shorter timeout: {effective_timeout}s")
    
    process = None
    try:
        # Send initial progress
        _progress(request_id, f"🚀 Starting command: {command}")
        
        # Create process with process group for better control
        process = subprocess.Popen(
            ["/bin/bash", "-c", command],
            cwd=str(SAFE_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # Create new process group
        )
        
        output_lines = []
        start_time = time.time()
        last_output_time = start_time
        consecutive_timeouts = 0
        max_consecutive_timeouts = 3
        error_count = 0
        max_errors = 10
        
        _debug_log(f"Process started with PID: {process.pid}")
        
        # Stream output line by line with enhanced timeout protection
        while process.poll() is None:
            current_time = time.time()
            
            # Check global timeout
            if current_time - start_time > effective_timeout:
                _debug_log(f"Global timeout reached ({effective_timeout}s)")
                _progress(request_id, f"⏱️ Command timeout after {effective_timeout}s - terminating")
                _terminate_process_group(process)
                output_lines.append(f"⏱️ Command terminated after {effective_timeout}s timeout")
                break
            
            # Try to read a line with timeout
            line = _read_with_timeout(process, READLINE_TIMEOUT)
            
            if line is not None:
                if line:  # Non-empty line
                    line = line.rstrip()
                    output_lines.append(line)
                    last_output_time = current_time
                    consecutive_timeouts = 0
                    error_count = 0  # Reset error count on successful read
                    
                    # Send progress update with throttling
                    elapsed = current_time - start_time
                    if len(output_lines) % 10 == 1 or elapsed > 10:  # Throttle progress updates
                        _progress(request_id, f"📊 Line {len(output_lines)}: {line[:100]}{'...' if len(line) > 100 else ''} [%.1fs]" % elapsed)
                # Continue for empty lines
            else:
                # Timeout on readline
                consecutive_timeouts += 1
                error_count += 1
                _debug_log(f"Readline timeout #{consecutive_timeouts}, total errors: {error_count}")
                
                # Check if we've hit too many errors
                if error_count >= max_errors:
                    _debug_log(f"Too many errors ({error_count}), terminating process")
                    _progress(request_id, f"💥 Too many errors ({error_count}) - terminating process")
                    _terminate_process_group(process)
                    output_lines.append(f"💥 Process terminated due to excessive errors ({error_count})")
                    break
                
                # Check if we've been stuck too long without output
                if current_time - last_output_time > READLINE_TIMEOUT * 2:
                    _debug_log(f"No output for {current_time - last_output_time:.1f}s, checking if process is responsive")
                    
                    # Check if process is still alive but maybe stuck
                    if consecutive_timeouts >= max_consecutive_timeouts:
                        _debug_log(f"Process appears stuck after {consecutive_timeouts} consecutive timeouts")
                        _progress(request_id, f"🔄 Process appears stuck - attempting recovery")
                        
                        # Try to send a signal to check if process is responsive
                        try:
                            if hasattr(signal, 'SIGCONT'):
                                process.send_signal(signal.SIGCONT)
                            time.sleep(ERROR_RECOVERY_TIMEOUT)
                        except (OSError, ProcessLookupError) as e:
                            _debug_log(f"Process appears to be dead: {e}")
                            output_lines.append(f"🛑 Process appears to have died: {e}")
                            break
                        except Exception as e:
                            _debug_log(f"Error sending recovery signal: {e}")
                        
                        # If still no response, terminate
                        if process.poll() is None and current_time - last_output_time > READLINE_TIMEOUT * 4:
                            _debug_log("Process not responding after recovery attempt, terminating")
                            _progress(request_id, f"🛑 Process unresponsive - terminating")
                            _terminate_process_group(process)
                            output_lines.append("🛑 Process terminated - appeared to be hanging")
                            break
        
        # Enhanced process completion handling
        if process.poll() is None:
            try:
                process.wait(timeout=PROCESS_TERMINATION_TIMEOUT)
            except subprocess.TimeoutExpired:
                _debug_log("Process didn't exit cleanly, force terminating")
                _terminate_process_group(process)
                try:
                    process.wait(timeout=ERROR_RECOVERY_TIMEOUT)
                except subprocess.TimeoutExpired:
                    _debug_log("Process still didn't exit after force termination")
        
        # Read any remaining output with timeout protection
        if process.stdout and not process.stdout.closed:
            try:
                remaining_start = time.time()
                while time.time() - remaining_start < ERROR_RECOVERY_TIMEOUT:
                    remaining = process.stdout.readline()
                    if not remaining:
                        break
                    if remaining.strip():
                        output_lines.append(remaining.strip())
            except Exception as e:
                _debug_log(f"Error reading remaining output: {e}")
        
        exit_code = process.returncode
        elapsed = time.time() - start_time
        
        # Enhanced final status reporting
        if exit_code == 0:
            _progress(request_id, f"✅ Command completed successfully in %.1fs" % elapsed)
        elif exit_code is None:
            _progress(request_id, f"🛑 Command was terminated after %.1fs" % elapsed)
            output_lines.append(f"[Process terminated]")
        elif exit_code == -9:
            _progress(request_id, f"💀 Command was killed (SIGKILL) after %.1fs" % elapsed)
            output_lines.append(f"[Process killed with SIGKILL]")
        elif exit_code == -15:
            _progress(request_id, f"🛑 Command was terminated (SIGTERM) after %.1fs" % elapsed)
            output_lines.append(f"[Process terminated with SIGTERM]")
        elif exit_code < 0:
            _progress(request_id, f"💥 Command terminated by signal {abs(exit_code)} after %.1fs" % elapsed)
            output_lines.append(f"[Process terminated by signal {abs(exit_code)}]")
        else:
            _progress(request_id, f"❌ Command failed with exit code {exit_code} after %.1fs" % elapsed)
            output_lines.append(f"[Exit code: {exit_code}]")
        
        return "\n".join(output_lines)
        
    except subprocess.CalledProcessError as e:
        _debug_log(f"Streaming command subprocess error: {e}")
        _progress(request_id, f"💥 Subprocess error: {str(e)}")
        error_msg = f"❌ Subprocess error: {e}"
        if hasattr(e, 'output') and e.output:
            error_msg += f"\nCommand output: {e.output}"
        return error_msg
    except OSError as e:
        _debug_log(f"Streaming command OS error: {e}")
        _progress(request_id, f"💥 OS error: {str(e)}")
        return f"❌ OS error: {e} - Command may not exist or insufficient permissions"
    except Exception as e:
        _debug_log(f"Streaming command unexpected error: {e}")
        _progress(request_id, f"💥 Unexpected error: {str(e)}")
        return f"❌ Unexpected error during streaming execution: {e}"
    finally:
        # Ensure process is cleaned up
        if process and process.poll() is None:
            try:
                _terminate_process_group(process)
            except Exception as e:
                _debug_log(f"Error in final cleanup: {e}")

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

def _detect_network_command(command):
    """Detect if a command involves network operations that might hang"""
    network_patterns = [
        r'\bcurl\b',           # curl commands
        r'\bwget\b',           # wget commands
        r'\bping\b',           # ping commands
        r'\btelnet\b',         # telnet commands
        r'\bnc\b',             # netcat commands
        r'\bnetcat\b',         # netcat commands
        r'\bssh\b',            # ssh commands
        r'\bftp\b',            # ftp commands
        r'\bsftp\b',           # sftp commands
        r'\brsync\b.*:',       # rsync over network
        r'https?://',          # HTTP/HTTPS URLs
        r'ftp://',             # FTP URLs
    ]
    
    for pattern in network_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False

def _detect_potentially_hanging_command(command):
    """Detect commands that might hang due to various reasons"""
    hanging_patterns = [
        r'\byes\b',            # yes command without timeout
        r'\btail\s+-f\b',      # tail -f follows files indefinitely
        r'\bwatch\b',          # watch command runs indefinitely
        r'\btop\b',            # top command is interactive
        r'\bhtop\b',           # htop command is interactive
        r'\bless\b',           # less pager
        r'\bmore\b',           # more pager
        r'\bvi\b',             # vi editor
        r'\bvim\b',            # vim editor
        r'\bnano\b',           # nano editor
        r'\bemacs\b',          # emacs editor
    ]
    
    for pattern in hanging_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False

# ============================================================================== Non-blocking I/O Utilities ==============================================================================
def _read_with_timeout(process, timeout=READLINE_TIMEOUT):
    """Read from process stdout with timeout using select"""
    if sys.platform == 'win32':
        # Windows doesn't support select on pipes, fallback to threading
        return _read_with_timeout_threaded(process, timeout)
    
    ready, _, _ = select.select([process.stdout], [], [], timeout)
    if ready:
        try:
            line = process.stdout.readline()
            return line
        except Exception:
            return None
    return None  # Timeout

def _read_with_timeout_threaded(process, timeout=READLINE_TIMEOUT):
    """Fallback threaded implementation for reading with timeout"""
    result = [None]
    
    def read_line():
        try:
            result[0] = process.stdout.readline()
        except Exception:
            result[0] = None
    
    thread = threading.Thread(target=read_line)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        # Thread is still running, meaning readline is blocked
        return None  # Timeout
    
    return result[0]

def _terminate_process_group(process):
    """Terminate process and its entire process group with enhanced error handling"""
    if process.poll() is None:
        try:
            _debug_log(f"Attempting to terminate process group for PID {process.pid}")
            
            # Step 1: Try graceful termination of process group
            if hasattr(os, 'killpg'):
                try:
                    pgid = os.getpgid(process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    _debug_log(f"Sent SIGTERM to process group {pgid}")
                except (OSError, ProcessLookupError) as e:
                    _debug_log(f"Could not send SIGTERM to process group: {e}")
            
            # Step 2: Wait for graceful termination
            try:
                process.wait(timeout=PROCESS_TERMINATION_TIMEOUT)
                _debug_log(f"Process {process.pid} terminated gracefully")
                return
            except subprocess.TimeoutExpired:
                _debug_log(f"Process {process.pid} didn't terminate gracefully, escalating")
            
            # Step 3: Force termination with SIGKILL
            if hasattr(os, 'killpg'):
                try:
                    pgid = os.getpgid(process.pid)
                    os.killpg(pgid, signal.SIGKILL)
                    _debug_log(f"Sent SIGKILL to process group {pgid}")
                except (OSError, ProcessLookupError) as e:
                    _debug_log(f"Could not send SIGKILL to process group: {e}")
            
            # Step 4: Direct process termination as fallback
            try:
                process.kill()
                _debug_log(f"Sent SIGKILL directly to process {process.pid}")
            except (OSError, ProcessLookupError) as e:
                _debug_log(f"Could not kill process directly: {e}")
            
            # Step 5: Final wait with shorter timeout
            try:
                process.wait(timeout=ERROR_RECOVERY_TIMEOUT)
                _debug_log(f"Process {process.pid} finally terminated")
            except subprocess.TimeoutExpired:
                _debug_log(f"Process {process.pid} still didn't terminate - may be zombified")
                
        except Exception as e:
            _debug_log(f"Error during process termination: {e}")
            # Final fallback attempt
            try:
                process.kill()
                process.wait(timeout=ERROR_RECOVERY_TIMEOUT)
            except Exception as final_e:
                _debug_log(f"Final termination attempt failed: {final_e}")

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
    """Safely run subprocess commands with enhanced error handling"""
    try:
        _debug_log(f"Running command: {' '.join(cmd_list)}")
        
        # Use specific timeout for file operations (5 minutes)
        timeout = RUN_SHELL_TIMEOUT
        command_str = ' '.join(cmd_list)
        if _detect_network_command(command_str):
            timeout = NETWORK_COMMAND_TIMEOUT
            _debug_log(f"Network command detected, using shorter timeout: {timeout}s")
        else:
            _debug_log(f"Using standard timeout: {timeout}s (5 minutes)")
        
        result = subprocess.run(
            cmd_list,
            cwd=_shell_cwd(),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = result.stdout or ""
        if result.stderr:
            output += "\n" + result.stderr
            
        _debug_log(f"Command completed with return code: {result.returncode}")
        
        # Enhanced return code handling
        if result.returncode == 0:
            return output.strip()
        elif result.returncode == -9:
            output += f"\n[Process killed with SIGKILL]"
        elif result.returncode == -15:
            output += f"\n[Process terminated with SIGTERM]"
        elif result.returncode < 0:
            output += f"\n[Process terminated by signal {abs(result.returncode)}]"
        else:
            output += f"\n[Exit code: {result.returncode}]"
            
        return output.strip()
        
    except subprocess.TimeoutExpired:
        _debug_log(f"Command timed out after {timeout}s")
        return f"⏱️ Command timed out after {timeout}s"
    except subprocess.CalledProcessError as e:
        _debug_log(f"Subprocess error: {e}")
        error_msg = f"❌ Subprocess error: {e}"
        if hasattr(e, 'output') and e.output:
            error_msg += f"\nCommand output: {e.output}"
        return error_msg
    except FileNotFoundError as e:
        _debug_log(f"Command not found: {e}")
        return f"❌ Command not found: {' '.join(cmd_list)} - Check if the command exists and is in PATH"
    except PermissionError as e:
        _debug_log(f"Permission denied: {e}")
        return f"❌ Permission denied: {' '.join(cmd_list)} - Check file permissions"
    except OSError as e:
        _debug_log(f"OS error: {e}")
        return f"❌ OS error: {e} - System-level error occurred"
    except Exception as e:
        _debug_log(f"Unexpected command execution error: {e}")
        return f"❌ Unexpected command execution error: {e}"

def _execute_shell(command):
    """Execute shell command and return complete output (non-streaming) - ENHANCED ERROR HANDLING VERSION"""
    _debug_log(f"Executing shell command: {command}")
    _debug_log(f"Working directory: {_shell_cwd()}")
    
    # Use specific timeout for run_shell and run_raw commands (5 minutes)
    timeout = RUN_SHELL_TIMEOUT
    if _detect_network_command(command):
        timeout = NETWORK_COMMAND_TIMEOUT
        _debug_log(f"Network command detected, using shorter timeout: {timeout}s")
    else:
        _debug_log(f"Using run_shell timeout: {timeout}s (5 minutes)")
    
    process = None
    try:
        # Use explicit bash execution for consistency with streaming/background tasks
        # Create process with process group for better control
        process = subprocess.Popen(
            ["/bin/bash", "-c", command], 
            cwd=_shell_cwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # Create new process group
        )
        
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _debug_log(f"Command timed out after {timeout}s, terminating process group")
            _terminate_process_group(process)
            try:
                stdout, stderr = process.communicate(timeout=ERROR_RECOVERY_TIMEOUT)
            except subprocess.TimeoutExpired:
                _debug_log("Process still didn't respond after termination")
                stdout, stderr = "", "Process was forcefully terminated and didn't respond"
            return f"⏱️ Command timed out after {timeout}s and was terminated"
        
        # Combine stdout and stderr
        output = stdout or ""
        if stderr:
            output += "\n" + stderr
            
        _debug_log(f"Command completed with return code: {process.returncode}")
        _debug_log(f"Output length: {len(output)} characters")
        
        # Enhanced return code handling
        if process.returncode == 0:
            return output.strip()
        elif process.returncode == -9:
            output += f"\n[Process killed with SIGKILL]"
        elif process.returncode == -15:
            output += f"\n[Process terminated with SIGTERM]"
        elif process.returncode < 0:
            output += f"\n[Process terminated by signal {abs(process.returncode)}]"
        else:
            output += f"\n[Exit code: {process.returncode}]"
            
        return output.strip()
        
    except subprocess.CalledProcessError as e:
        _debug_log(f"Command subprocess error: {e}")
        error_msg = f"❌ Subprocess error: {e}"
        if hasattr(e, 'output') and e.output:
            error_msg += f"\nCommand output: {e.output}"
        return error_msg
    except OSError as e:
        _debug_log(f"Command OS error: {e}")
        return f"❌ OS error: {e} - Command may not exist or insufficient permissions"
    except Exception as e:
        _debug_log(f"Command execution unexpected error: {e}")
        return f"❌ Unexpected command execution error: {e}"
    finally:
        # Ensure process is cleaned up
        if process and process.poll() is None:
            try:
                _terminate_process_group(process)
            except Exception as e:
                _debug_log(f"Error in final cleanup: {e}")

def _run_shell_handler(params):
    """Handle shell command execution with streaming and interactive detection - ENHANCED VERSION"""
    command = params["command"]
    stream = params.get("stream", False)
    background = params.get("background", False)
    request_id = params.get("request_id", "default")
    
    _debug_log(f"Shell command: {command} (stream={stream}, background={background})")
    
    # Enhanced command analysis
    warnings = []
    
    # Check for interactive commands
    if _detect_interactive_command(command):
        warning = f"⚠️ INTERACTIVE: Command '{command}' may require user input and could hang."
        warnings.append(warning)
        _debug_log(warning)
    
    # Check for network commands
    if _detect_network_command(command):
        warning = f"⚠️ NETWORK: Command '{command}' involves network operations - using shorter timeout."
        warnings.append(warning)
        _debug_log(warning)
        
        # For network commands, prefer non-streaming mode unless explicitly requested
        if not stream and not background:
            warnings.append("💡 TIP: For network commands, consider using 'stream=true' for better progress tracking.")
    
    # Check for potentially hanging commands
    if _detect_potentially_hanging_command(command):
        warning = f"⚠️ HANG RISK: Command '{command}' may run indefinitely."
        warnings.append(warning)
        _debug_log(warning)
        warnings.append("💡 TIP: Consider using 'background=true' for long-running commands.")
    
    # Prepare warning message
    warning_msg = "\n".join(warnings) + "\n\n" if warnings else ""
    
    # Handle background tasks
    if background:
        task_id = _create_background_task(command)
        _cleanup_completed_tasks()  # Clean up old tasks
        return f"{warning_msg}🔄 Background task started with ID: {task_id}\nUse 'task_status' or 'task_output' tools to check progress."
    
    # Handle streaming output
    if stream:
        result = _stream_command_output(command, request_id)
        return warning_msg + result
    
    # Default: non-streaming execution with warnings
    result = _execute_shell(command)
    return warning_msg + result

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
    """Handle file search with enhanced error handling"""
    try:
        pattern = params["pattern"]
        root = params.get("root", ".")
        _debug_log(f"File search: pattern='{pattern}', root='{root}'")
        
        root_path = _safe_resolve(root)
        if not root_path.exists():
            return f"❌ Search root directory '{root}' does not exist"
        
        if not root_path.is_dir():
            return f"❌ Search root '{root}' is not a directory"
        
        matches = []
        error_count = 0
        max_errors = 10
        
        try:
            for dp, dirs, fs in os.walk(root_path):
                # Check for too many errors
                if error_count >= max_errors:
                    matches.append(f"⚠️ Search stopped after {max_errors} errors")
                    break
                
                try:
                    for f in fs:
                        try:
                            if re.search(pattern, f):
                                matches.append(os.path.join(dp, f))
                        except re.error as e:
                            _debug_log(f"Regex error with pattern '{pattern}': {e}")
                            return f"❌ Invalid regex pattern '{pattern}': {e}"
                        except Exception as e:
                            error_count += 1
                            _debug_log(f"Error processing file '{f}': {e}")
                            
                except PermissionError as e:
                    error_count += 1
                    _debug_log(f"Permission denied accessing directory '{dp}': {e}")
                    matches.append(f"⚠️ Permission denied: {dp}")
                except Exception as e:
                    error_count += 1
                    _debug_log(f"Error accessing directory '{dp}': {e}")
                    
        except KeyboardInterrupt:
            matches.append("🛑 Search interrupted by user")
        except Exception as e:
            _debug_log(f"Unexpected error during file search: {e}")
            return f"❌ File search failed: {e}"
        
        if error_count > 0:
            matches.append(f"⚠️ Search completed with {error_count} errors (check debug log)")
        
        result = "\n".join(matches) if matches else "No matches found"
        _debug_log(f"File search found {len([m for m in matches if not m.startswith('⚠️')])} matches with {error_count} errors")
        return result
        
    except PermissionError as e:
        _debug_log(f"Permission error in file search: {e}")
        return f"❌ Permission denied: {e}"
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
            
        # Execute the tool handler with timeout protection
        start_time = time.time()
        try:
            output = tool["handler"](args)
        except Exception as handler_error:
            elapsed = time.time() - start_time
            _debug_log(f"Tool handler failed after {elapsed:.1f}s: {handler_error}")
            raise
        
        elapsed = time.time() - start_time
        _debug_log(f"Tool execution completed successfully in {elapsed:.1f}s")
        
        # Validate output
        if output is None:
            output = f"⚠️ Tool '{name}' completed but returned no output"
        elif not isinstance(output, str):
            output = str(output)
        
        # Truncate extremely long output to prevent memory issues
        max_output_length = 100000  # 100KB limit
        if len(output) > max_output_length:
            truncated_msg = f"\n\n⚠️ Output truncated at {max_output_length} characters (original: {len(output)} chars)"
            output = output[:max_output_length] + truncated_msg
        
        # Return raw text content
        final = {"content": [{"type": "text", "text": output}]}
        _result(rid, final)
        
    except subprocess.TimeoutExpired as e:
        _debug_log(f"Tool execution timeout: {e}")
        _error(rid, -32030, "Tool execution timeout", f"Tool '{name}' exceeded maximum execution time")
    except subprocess.CalledProcessError as e:
        _debug_log(f"Subprocess error in tool: {e}")
        error_msg = f"Subprocess error in tool '{name}'"
        if hasattr(e, 'output') and e.output:
            error_msg += f": {e.output}"
        _error(rid, -32020, "Subprocess error", error_msg)
    except PermissionError as e:
        _debug_log(f"Permission error: {e}")
        _error(rid, -32010, "Access denied", f"Permission denied: {str(e)}")
    except FileNotFoundError as e:
        _debug_log(f"File not found error: {e}")
        _error(rid, -32011, "File not found", f"Required file or command not found: {str(e)}")
    except OSError as e:
        _debug_log(f"OS error: {e}")
        _error(rid, -32012, "System error", f"Operating system error: {str(e)}")
    except json.JSONDecodeError as e:
        _debug_log(f"JSON parsing error: {e}")
        _error(rid, -32013, "JSON parsing error", f"Failed to parse JSON data: {str(e)}")
    except KeyboardInterrupt:
        _debug_log(f"Tool execution interrupted")
        _error(rid, -32014, "Execution interrupted", f"Tool '{name}' was interrupted")
    except Exception as e:
        _debug_log(f"Unhandled exception in tool '{name}': {e}")
        _debug_log(f"Exception traceback: {traceback.format_exc()}")
        _error(rid, -32000, "Unhandled exception", f"Unexpected error in tool '{name}': {str(e)}")

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
        
        # Count tasks by status
        status_counts = {}
        for task in BACKGROUND_TASKS.values():
            status_counts[task.status] = status_counts.get(task.status, 0) + 1
        
        result = f"📝 Background Tasks ({len(BACKGROUND_TASKS)} total):\n"
        
        # Show status summary
        if len(status_counts) > 1:
            status_summary = ", ".join([f"{status}: {count}" for status, count in status_counts.items()])
            result += f"   Status Summary: {status_summary}\n"
        
        result += "=" * 50 + "\n"
        
        for task_id, task in BACKGROUND_TASKS.items():
            status = task.get_status()
            elapsed = status['elapsed_seconds']
            elapsed_str = f"{elapsed:.1f}s" if elapsed else "0s"
            
            # Add special indicator for restored tasks
            status_indicator = status['status']
            if status['status'] == 'lost':
                status_indicator = "lost (server restarted)"
            
            result += f"• {task_id}: {status_indicator} ({elapsed_str}) - {status['command'][:60]}{'...' if len(status['command']) > 60 else ''}\n"
    
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
    
    # Load persistent background tasks
    try:
        _load_tasks_from_disk()
    except Exception as e:
        _debug_log(f"Error loading tasks on startup: {e}")
    
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
