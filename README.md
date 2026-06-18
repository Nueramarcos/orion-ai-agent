# orion-ai-agent
Local autonomous coding agent: ingests codebases, traces bugs via AST, applies surgical patches without human intervention

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

For more information, refer to the source code in `Orion/ast_parser.py`.
