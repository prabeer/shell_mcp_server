# MCP Shell Server

## Overview
The MCP Shell Server (`safe_shell_mcp.py`) is a secure and robust shell server designed for managing shell tasks with advanced features such as streaming output, background task queuing, and interactive command detection. It is built with modularity, security, and user experience in mind, making it ideal for developers and system administrators.

## Key Features
- **Streaming Output**: Execute commands with real-time streaming output and progress updates.
- **Background Task Management**: Queue tasks to run in the background with status tracking and output retrieval.
- **Interactive Command Detection**: Detect commands requiring user input and provide warnings.
- **Secure Execution**: Restrict access to a specified safe root directory.
- **Cross-Platform Compatibility**: Supported on Linux, macOS, and Windows (via WSL).

## Supported Operating Systems
- **Linux**: Fully supported.
- **macOS**: Fully supported.
- **Windows**: Supported via Windows Subsystem for Linux (WSL).

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/prabeer/shell_mcp_server.git
   ```
2. Navigate to the project directory:
   ```bash
   cd shell_mcp_server
   ```
3. Ensure Python 3.8+ is installed on your system.
4. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
### Starting the Server
Run the MCP Shell Server with the following command:
```bash
python3 safe_shell_mcp.py --saferoot /path/to/safe/root --debug
```
- `--saferoot`: Specifies the directory to restrict access.
- `--debug`: Enables debug logging.

### Modes of Operation
1. **Streaming Mode**:
   Execute commands with real-time output streaming and progress updates.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"run_shell","arguments":{"command":"ls -la","stream":true}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

2. **Background Task Mode**:
   Run commands in the background and retrieve their status or output later.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"run_shell","arguments":{"command":"sleep 10","background":true}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

3. **Interactive Command Detection**:
   Detect commands requiring user input and provide warnings.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"run_shell","arguments":{"command":"sudo apt update"}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

### Additional Tools
- **List Directory**:
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_dir","arguments":{"path":"."}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```
- **Search Files**:
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"file_search","arguments":{"pattern":"*.py","root":"."}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

## Supported Commands

### Core Commands
1. **Run Shell Command**:
   Execute shell commands with options for streaming output or background execution.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"run_shell","arguments":{"command":"ls -la","stream":true}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

2. **Run Raw Command**:
   Execute shell commands without additional processing.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"run_raw","arguments":{"command":"echo Hello World"}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

3. **List Directory**:
   List the contents of a directory.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_dir","arguments":{"path":"."}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

4. **Search Files**:
   Search for files matching a pattern.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"file_search","arguments":{"pattern":"*.py","root":"."}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

5. **Print Working Directory**:
   Display the current working directory.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"print_workdir"}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

6. **Grep File**:
   Search for a pattern in a file.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"grep_file","arguments":{"pattern":"def","filepath":"safe_shell_mcp.py"}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

7. **Cat File**:
   Display the contents of a file.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"cat_file","arguments":{"filepath":"README.md"}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

8. **Sed Search**:
   Perform a search using `sed`.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"sed_search","arguments":{"script":"s/old/new/g","filepath":"README.md"}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

### Background Task Management
1. **Task Status**:
   Get the status of a background task.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"task_status","arguments":{"task_id":"<task_id>"}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

2. **Task Output**:
   Retrieve the output of a background task.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"task_output","arguments":{"task_id":"<task_id>","max_lines":10}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

3. **Task List**:
   List all background tasks.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"task_list"}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

4. **Task Terminate**:
   Terminate a background task.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"task_terminate","arguments":{"task_id":"<task_id>"}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

### Version Information
1. **Version**:
   Display server version and build information.
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"version"}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root
   ```

## Background and Streaming Tasks

### Background Tasks
Background tasks are designed for long-running operations that do not require immediate user interaction. These tasks run asynchronously, allowing users to continue other operations while monitoring their progress.

**Key Features:**
- Asynchronous execution for long-running commands.
- Status tracking with `task_status`.
- Output retrieval with `task_output`.
- Automatic cleanup of completed tasks after 1 hour.
- Graceful termination with `task_terminate`.

**Recommended Use Cases:**
- Training machine learning models.
- Large-scale builds or deployments.
- Data processing tasks.

**Default Timeout:**
- Background tasks have a timeout of **3600 seconds (1 hour)**.

For more details, refer to the [STREAMING_FEATURES.md](STREAMING_FEATURES.md) file.

### Streaming Tasks
Streaming tasks provide real-time feedback for commands that generate continuous output. This mode is ideal for monitoring progress and receiving updates during execution.

**Key Features:**
- Real-time output streaming.
- Progress updates every 10 lines or on important events.
- Timeout protection to prevent hanging commands.
- Start and completion status messages.
- Elapsed time tracking.

**Recommended Use Cases:**
- Build processes.
- Package installations.
- Continuous monitoring tasks.

**Default Timeout:**
- Streaming tasks have a timeout of **300 seconds (5 minutes)**.

For more details, refer to the [STREAMING_FEATURES.md](STREAMING_FEATURES.md) file.

## Compatibility
- **Designed for VS Code and GitHub Copilot**: Optimized for seamless integration with modern code editors, enabling intelligent code suggestions and streamlined workflows.
- **Supports RFC JSON Format**: Ensures structured and standardized data handling for tools and commands, making it compatible with modern APIs and automation systems.
- **Cross-Editor Compatibility**: Works seamlessly with other popular editors like PyCharm, Sublime Text, and Atom, ensuring flexibility for developers.

## Contributing
Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contact
For questions or support, please contact [Prabeer](https://github.com/prabeer).

## Integration with VS Code and GitHub Copilot

### Adding Tasks to VS Code
To integrate the MCP Shell Server with VS Code, you can add tasks to the `tasks.json` file in your workspace. Below is an example configuration:

1. Open the Command Palette in VS Code (`Ctrl+Shift+P` or `Cmd+Shift+P` on macOS) and select `Tasks: Configure Task`.
2. Choose `Create tasks.json file from template` if prompted.
3. Add the following tasks to the `tasks.json` file:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "MCP Shell: List Directory",
      "type": "shell",
      "command": "echo",
      "args": [
        "'{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"list_dir\",\"arguments\":{\"path\":\".\"}}}}' | python3 safe_shell_mcp.py --saferoot /path/to/safe/root"
      ],
      "group": "build"
    },
    {
      "label": "MCP Shell: Run Command",
      "type": "shell",
      "command": "bash",
      "args": [
        "-c",
        "read -p 'Enter command: ' cmd && echo \"{\\\"jsonrpc\\\":\\\"2.0\\\",\\\"id\\\":1,\\\"method\\\":\\\"tools/call\\\",\\\"params\\\":{\\\"name\\\":\\\"run_shell\\\",\\\"arguments\\\":{\\\"command\\\":\\\"$cmd\\\"}}}}\" | python3 safe_shell_mcp.py --saferoot /path/to/safe/root"
      ],
      "group": "build"
    }
  ]
}
```

### Adding MCP Shell Server to VS Code Settings

To configure the MCP Shell Server in VS Code settings, you can add the following snippet to your `settings.json` file:

```json
"mcp": {
  "servers": {
    "shell_server": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "<path_to_safe_shell_mcp.py>",
        "--saferoot",
        "<path_to_safe_root>",
        "--debug"
      ]
    }
  }
}
```

Replace `<path_to_safe_shell_mcp.py>` with the absolute path to the `safe_shell_mcp.py` file and `<path_to_safe_root>` with the directory you want to restrict access to.

### Adding MCP Shell Server to VS Code Workspace

To configure the MCP Shell Server for your VS Code workspace, you can add the following snippet to the `.vscode/settings.json` file:

```json
{
  "mcp": {
    "servers": {
      "shell_server": {
        "type": "stdio",
        "command": "python3",
        "args": [
          "<path_to_safe_shell_mcp.py>",
          "--saferoot",
          "<path_to_safe_root>",
          "--debug"
        ]
      }
    }
  }
}
```

Replace `<path_to_safe_shell_mcp.py>` with the absolute path to the `safe_shell_mcp.py` file and `<path_to_safe_root>` with the directory you want to restrict access to.

### Using GitHub Copilot
GitHub Copilot can assist in writing and editing code for the MCP Shell Server. To enable Copilot:

1. Install the GitHub Copilot extension from the VS Code Marketplace.
2. Open the MCP Shell Server project in VS Code.
3. Start typing commands or code snippets, and Copilot will provide intelligent suggestions.
4. Use Copilot to generate JSON-RPC commands, debug scripts, or write documentation.

For more details, refer to the [GitHub Copilot documentation](https://docs.github.com/en/copilot).
