#!/usr/bin/env python3
"""
Example of how to implement streaming output for long-running commands
This shows what could be added to the MCP server for better UX
"""

import subprocess
import threading
import time

def _stream_shell_output(command, progress_callback=None):
    """
    Execute command with streaming output - better for long-running commands
    """
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # Line buffered
        universal_newlines=True
    )
    
    output_lines = []
    
    # Stream output line by line
    for line in iter(process.stdout.readline, ''):
        if line:
            output_lines.append(line.rstrip())
            if progress_callback:
                progress_callback(f"Output: {line.rstrip()}")
    
    process.stdout.close()
    return_code = process.wait()
    
    full_output = '\n'.join(output_lines)
    if return_code != 0:
        full_output += f"\n[Exit code: {return_code}]"
        
    return full_output

def _execute_with_timeout_and_streaming(command, timeout=60, progress_callback=None):
    """
    Execute command with both timeout and streaming support
    """
    result = {'output': '', 'completed': False, 'timed_out': False}
    
    def target():
        try:
            result['output'] = _stream_shell_output(command, progress_callback)
            result['completed'] = True
        except Exception as e:
            result['output'] = f"Error: {e}"
            result['completed'] = True
    
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        # Command is still running after timeout
        result['timed_out'] = True
        result['output'] = f"⏱️ Command timed out after {timeout}s"
    
    return result

# Example usage:
if __name__ == "__main__":
    def progress_handler(message):
        print(f"[PROGRESS] {message}")
    
    print("Testing streaming command...")
    result = _execute_with_timeout_and_streaming(
        "echo 'Starting...' && sleep 2 && echo 'Middle...' && sleep 2 && echo 'Done!'",
        timeout=10,
        progress_callback=progress_handler
    )
    
    print(f"Final result: {result}")
