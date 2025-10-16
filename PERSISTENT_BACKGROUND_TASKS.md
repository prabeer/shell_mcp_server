# Persistent Background Tasks Feature

## Overview
The MCP Shell Server now supports persistent background tasks that survive server restarts. This feature ensures that long-running background tasks are not lost when the server is restarted, providing better reliability for long-running operations.

## Key Features

### 1. Automatic Task Persistence
- **Disk Storage**: All background tasks are automatically saved to disk
- **JSON Format**: Tasks stored in `.mcp_background_tasks.json` file
- **Atomic Operations**: File writes use atomic operations to prevent corruption
- **File Locking**: Prevents concurrent access issues

### 2. Server Restart Recovery
- **Automatic Loading**: Tasks are automatically loaded when server starts
- **Status Recovery**: Completed, failed, and terminated tasks maintain their status
- **Lost Task Detection**: Running tasks are marked as "lost" after restart
- **Output Preservation**: Task output is preserved across restarts

### 3. Intelligent Cleanup
- **Age-based Cleanup**: Tasks older than 24 hours are automatically removed
- **Memory Management**: Old completed tasks are cleaned from memory after 1 hour
- **Storage Optimization**: Disk storage is automatically optimized

## Task States

### Standard States
- **pending**: Task is created but not yet started
- **running**: Task is currently executing
- **completed**: Task finished successfully (exit code 0)
- **failed**: Task finished with error (non-zero exit code)
- **terminated**: Task was manually terminated
- **timeout**: Task exceeded its timeout limit

### Recovery State
- **lost**: Task was running when server restarted (cannot be recovered)

## Storage Format

Tasks are stored in JSON format with the following structure:

```json
{
  "task_id": {
    "task_id": "abc12345",
    "command": "long-running-command",
    "timeout": 1800,
    "status": "completed",
    "start_time": 1634567890.123,
    "end_time": 1634567895.456,
    "exit_code": 0,
    "output_lines": ["line1", "line2", "..."],
    "created_at": 1634567890.123
  }
}
```

## Usage Examples

### Starting a Persistent Background Task
```json
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
```

### Checking Tasks After Server Restart
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "task_list"
  }
}
```

**Response (showing restored tasks):**
```text
📝 Background Tasks (2 total):
   Status Summary: completed: 1, lost: 1
==================================================
• abc12345: completed (45.2s) - python train_model.py
• def67890: lost (server restarted) (23.1s) - long-running-process
```

### Getting Output from Restored Task
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "task_output",
    "arguments": {
      "task_id": "abc12345"
    }
  }
}
```

## Implementation Details

### Storage Location
- **File**: `.mcp_background_tasks.json` in the safe root directory
- **Permissions**: Uses file locking to prevent corruption
- **Backup**: Atomic writes ensure data integrity

### Recovery Process
1. **Server Startup**: Automatically loads tasks from disk
2. **Status Check**: Determines which tasks were running during restart
3. **State Update**: Marks running tasks as "lost"
4. **Memory Restore**: Recreates task objects with preserved state
5. **Output Restore**: Restores all captured output

### Cleanup Strategy
- **Memory**: Tasks older than 1 hour removed from memory
- **Disk**: Tasks older than 24 hours removed from storage
- **Automatic**: Cleanup runs during normal operations

## Benefits

### 1. Reliability
- ✅ Long-running tasks survive server restarts
- ✅ No loss of completed task information
- ✅ Preserved task output and status

### 2. Operational Continuity
- ✅ Server maintenance doesn't lose task history
- ✅ Debugging capabilities preserved across restarts
- ✅ Audit trail maintained

### 3. Resource Management
- ✅ Automatic cleanup prevents disk space issues
- ✅ Memory usage is controlled
- ✅ Performance remains optimal

## Limitations

### 1. Running Tasks Cannot Be Recovered
- Tasks that were actively running are marked as "lost"
- Process PIDs are not preserved across restarts
- Running tasks need to be restarted manually

### 2. Storage Requirements
- Requires write access to safe root directory
- JSON storage may not be suitable for extremely large outputs
- File system must support atomic operations

### 3. Time Limitations
- Tasks older than 24 hours are automatically cleaned up
- No long-term archival of task history
- Clock changes may affect cleanup timing

## Configuration

### Storage File Location
The storage file is automatically created in the safe root directory:
```
<safe_root>/.mcp_background_tasks.json
```

### Timeout Settings
```python
BACKGROUND_TASK_TIMEOUT = 1800  # 30 minutes default
```

### Cleanup Settings
- **Memory cleanup**: 1 hour after task completion
- **Disk cleanup**: 24 hours after task creation

## Security Considerations

### 1. File Access
- Storage file is created in the restricted safe root directory
- No external access outside of safe root boundaries
- File permissions follow system defaults

### 2. Data Privacy
- Task commands and output are stored in plain text
- Sensitive information in commands will be persisted
- Consider security implications for command parameters

### 3. Disk Usage
- Automatic cleanup prevents unbounded growth
- Monitor disk usage for safe root directory
- Large outputs may impact storage requirements

## Troubleshooting

### Storage File Issues
```bash
# Check if storage file exists
ls -la <safe_root>/.mcp_background_tasks.json

# View storage file contents
cat <safe_root>/.mcp_background_tasks.json | jq .

# Remove corrupted storage (will lose task history)
rm <safe_root>/.mcp_background_tasks.json
```

### Permission Issues
```bash
# Check permissions on safe root
ls -ld <safe_root>

# Ensure write permissions
chmod u+w <safe_root>
```

### Debug Information
Enable debug mode to see detailed persistence operations:
```bash
python3 safe_shell_mcp.py --saferoot <path> --debug
```

## Testing

Use the provided test script to validate persistent task functionality:
```bash
python3 test_persistent_tasks.py <safe_root_path>
```

This test will:
1. Start a background task
2. Verify storage file creation
3. Simulate server restart
4. Verify task recovery
5. Check task output preservation

## Version Information
- **Introduced**: Build version 2025-10-16-v6.0-PERSISTENT-BACKGROUND-TASKS
- **Server Version**: 1.4.0
- **Dependencies**: Python 3.8+, fcntl module