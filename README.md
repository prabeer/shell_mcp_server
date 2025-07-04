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

## Contributing
Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contact
For questions or support, please contact [Prabeer](https://github.com/prabeer).
