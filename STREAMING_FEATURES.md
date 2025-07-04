# MCP Shell Server - Streaming & Background Task Features

## Overview
The enhanced MCP Shell Server now supports streaming output, background task execution, and intelligent interactive command detection for improved user experience.

## New Features

### 1. Streaming Output with Progress Callbacks
Commands can now stream their output in real-time with progress updates.

**Usage:**
```json
{
  "name": "run_shell",
  "arguments": {
    "command": "npm install",
    "stream": true
  }
}
```

**Features:**
- Real-time output streaming
- Progress updates every 10 lines or on important events
- Timeout protection (5 minutes default)
- Start/completion status messages
- Elapsed time tracking

### 2. Background Task Queuing
Long-running commands can be executed in background with status monitoring.

**Usage:**
```json
{
  "name": "run_shell", 
  "arguments": {
    "command": "npm run build",
    "background": true
  }
}
```

**Task Management Tools:**
- `task_status` - Get detailed status of a background task
- `task_output` - Retrieve output from a background task
- `task_list` - List all background tasks
- `task_terminate` - Stop a running background task

### 3. Interactive Command Detection
Automatically detects commands that might require user input and provides warnings.

**Detected Patterns:**
- `sudo` commands (password prompts)
- `ssh` connections (authentication)
- `git push` (credential prompts)
- Package manager installations (`apt`, `yum`, `pip`, `npm`)
- Interactive shells and utilities

**Behavior:**
- Shows warning for potentially interactive commands
- Suggests non-interactive alternatives
- Prevents hanging on input-waiting commands

### 4. Enhanced Error Handling
- Timeout protection for all operations
- Better error messages with context
- Graceful handling of terminated processes
- Resource cleanup for background tasks

## API Examples

### Streaming Command Execution
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "run_shell",
    "arguments": {
      "command": "find . -name '*.py' | head -20",
      "stream": true
    }
  }
}
```

### Background Task with Status Monitoring
```json
// Start background task
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "run_shell",
    "arguments": {
      "command": "python train_model.py",
      "background": true
    }
  }
}

// Check task status (returns task ID from previous call)
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "task_status",
    "arguments": {
      "task_id": "a1b2c3d4"
    }
  }
}

// Get task output
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "task_output",
    "arguments": {
      "task_id": "a1b2c3d4",
      "max_lines": 50
    }
  }
}
```

## Configuration

### Timeouts
- **DEFAULT_TIMEOUT**: 60 seconds (normal commands)
- **STREAMING_TIMEOUT**: 300 seconds (streaming commands)
- **BACKGROUND_TASK_TIMEOUT**: 3600 seconds (background tasks)

### Task Management
- Automatic cleanup of completed tasks after 1 hour
- Thread-safe task registry
- Graceful process termination

## Best Practices

### When to Use Streaming
- Long-running commands with continuous output
- Build processes, installations, downloads
- When you need real-time feedback

### When to Use Background Tasks
- Very long operations (>5 minutes)
- Training ML models, large builds
- When you need to run multiple commands in parallel

### Interactive Command Alternatives
Instead of potentially interactive commands, use:
- `sudo -n` (non-interactive sudo)
- `git push --non-interactive`
- `apt-get install -y` (auto-confirm)
- `pip install --quiet`

## Version Information
- Build Version: `2025-07-02-v3.0-STREAMING-ROBUST`
- Added: Threading, queue management, streaming output
- Enhanced: Error handling, timeout management, task lifecycle
