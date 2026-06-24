# orion-ai-agent
Local autonomous coding agent: ingests codebases, traces bugs via AST, applies surgical patches without human intervention

[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![CI](https://github.com/Nueramarcos/orion-ai-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Nueramarcos/orion-ai-agent/actions/workflows/ci.yml)

## Usage
To use Orion AST analyser, follow these steps:

1. **Install**: Python 3.10+ is required with no extra dependencies.
2. **Run a single file**:
   ```sh
   python Orion/ast_parser.py file <path>
   ```
3. **Scan a project directory and print symbol table**:
   ```sh
   python Orion/ast_parser.py scan <project_root> --symbols
   ```
4. **Find call sites of a symbol**:
   ```sh
   python Orion/ast_parser.py callers <project_root> <symbol>
   ```

For more information, refer to the source code in `Orion/ast_parser.py.

## Troubleshooting section
- Missing file: Ensure the file exists at the specified path.
- Parse errors: Check if the file is correctly formatted and contains valid Python code.
