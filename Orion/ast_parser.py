"""
Orion - AST Parser
Cross-file analysis and symbol resolution.
"""

import ast
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class Symbol:
    name: str
    kind: str          # "function" | "class" | "variable"
    defined_in: str    # source file path
    lineno: int
    col_offset: int = 0
    qualified: str = ""   # e.g. "module.ClassName.method"

    def __post_init__(self):
        if not self.qualified:
            self.qualified = self.name


@dataclass
class ImportRef:
    """A single import statement resolved to an origin file (if found)."""
    alias: str          # local name used in this file
    module: str         # dotted module string
    origin_file: str | None = None   # resolved path, None if external/stdlib


@dataclass
class ParseResult:
    source_file: str
    node_count: int = 0
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[ImportRef] = field(default_factory=list)
    calls: list[tuple[str, int]] = field(default_factory=list)   # (name, lineno)
    errors: list[str] = field(default_factory=list)

    # convenience views
    @property
    def functions(self) -> list[str]:
        return [s.name for s in self.symbols if s.kind == "function"]

    @property
    def classes(self) -> list[str]:
        return [s.name for s in self.symbols if s.kind == "class"]


# ── Single-file walker ────────────────────────────────────────────────────────

class ASTWalker(ast.NodeVisitor):
    """Walks one Python AST, collecting symbols, imports, and call sites."""

    def __init__(self, filepath: str = ""):
        self._file = filepath
        self._scope: list[str] = []   # stack of class/function names
        self.result = ParseResult(source_file=filepath)

    # ── scope helpers ──────────────────────────────────────────────────────

    def _qualified(self, name: str) -> str:
        return ".".join(self._scope + [name])

    def _push(self, name: str):
        self._scope.append(name)

    def _pop(self):
        self._scope.pop()

    # ── visitors ───────────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        sym = Symbol(
            name=node.name,
            kind="function",
            defined_in=self._file,
            lineno=node.lineno,
            col_offset=node.col_offset,
            qualified=self._qualified(node.name),
        )
        self.result.symbols.append(sym)
        self.result.node_count += 1
        self._push(node.name)
        self.generic_visit(node)
        self._pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        sym = Symbol(
            name=node.name,
            kind="class",
            defined_in=self._file,
            lineno=node.lineno,
            col_offset=node.col_offset,
            qualified=self._qualified(node.name),
        )
        self.result.symbols.append(sym)
        self.result.node_count += 1
        self._push(node.name)
        self.generic_visit(node)
        self._pop()

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            local = alias.asname or alias.name
            self.result.imports.append(ImportRef(alias=local, module=alias.name))
        self.result.node_count += 1

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        module = node.module or ""
        for alias in node.names:
            local = alias.asname or alias.name
            self.result.imports.append(ImportRef(alias=local, module=f"{module}.{alias.name}"))
        self.result.node_count += 1

    def visit_Call(self, node: ast.Call) -> Any:
        # Capture the call target name as best we can
        if isinstance(node.func, ast.Name):
            self.result.calls.append((node.func.id, node.lineno))
        elif isinstance(node.func, ast.Attribute):
            self.result.calls.append((node.func.attr, node.lineno))
        self.result.node_count += 1
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        for target in node.targets:
            if isinstance(target, ast.Name):
                sym = Symbol(
                    name=target.id,
                    kind="variable",
                    defined_in=self._file,
                    lineno=node.lineno,
                    qualified=self._qualified(target.id),
                )
                self.result.symbols.append(sym)
        self.result.node_count += 1
        self.generic_visit(node)


# ── Cross-file analyser ───────────────────────────────────────────────────────

class ProjectAnalyser:
    """
    Parses a collection of Python files and resolves cross-file references.

    Usage:
        analyser = ProjectAnalyser(root="/path/to/project")
        analyser.scan()
        report = analyser.resolve()
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.results: dict[str, ParseResult] = {}       # path → ParseResult
        self._symbol_index: dict[str, list[Symbol]] = defaultdict(list)
        # module name → file path, e.g. "orion.core.ast_parser" → "/…/ast_parser.py"
        self._module_map: dict[str, str] = {}

    # ── scanning ───────────────────────────────────────────────────────────

    def scan(self, glob: str = "**/*.py") -> "ProjectAnalyser":
        """Parse every matching file under root."""
        for path in sorted(self.root.glob(glob)):
            result = self._parse_file(path)
            key = str(path)
            self.results[key] = result
            # index symbols
            for sym in result.symbols:
                self._symbol_index[sym.name].append(sym)
            # build module map
            mod = self._path_to_module(path)
            if mod:
                self._module_map[mod] = key
        return self

    def _parse_file(self, path: Path) -> ParseResult:
        walker = ASTWalker(filepath=str(path))
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            walker.visit(tree)
        except SyntaxError as e:
            walker.result.errors.append(f"SyntaxError: {e}")
        except OSError as e:
            walker.result.errors.append(f"IOError: {e}")
        return walker.result

    def _path_to_module(self, path: Path) -> str | None:
        """Convert a file path to a dotted module name relative to root."""
        try:
            rel = path.relative_to(self.root)
        except ValueError:
            return None
        parts = list(rel.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        elif parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        else:
            return None
        return ".".join(parts)

    # ── resolution ─────────────────────────────────────────────────────────

    def resolve(self) -> "ResolutionReport":
        """Resolve import references across all parsed files."""
        resolved: list[tuple[str, ImportRef]] = []
        unresolved: list[tuple[str, ImportRef]] = []

        for filepath, result in self.results.items():
            for imp in result.imports:
                origin = self._resolve_import(imp)
                imp.origin_file = origin
                if origin:
                    resolved.append((filepath, imp))
                else:
                    unresolved.append((filepath, imp))

        return ResolutionReport(
            results=self.results,
            symbol_index=dict(self._symbol_index),
            resolved=resolved,
            unresolved=unresolved,
        )

    def _resolve_import(self, imp: ImportRef) -> str | None:
        """Return the file path that defines this import, or None."""
        # Try exact module match
        if imp.module in self._module_map:
            return self._module_map[imp.module]
        # Try parent module (e.g. "orion.core.ast_parser.parse_file" → "orion.core.ast_parser")
        parts = imp.module.split(".")
        for end in range(len(parts) - 1, 0, -1):
            candidate = ".".join(parts[:end])
            if candidate in self._module_map:
                return self._module_map[candidate]
        return None   # stdlib or external

    # ── call-site lookup ───────────────────────────────────────────────────

    def find_callers(self, symbol_name: str) -> dict[str, list[int]]:
        """Return {filepath: [lineno, ...]} for every call site of symbol_name."""
        callers: dict[str, list[int]] = defaultdict(list)
        for filepath, result in self.results.items():
            for name, lineno in result.calls:
                if name == symbol_name:
                    callers[filepath].append(lineno)
        return dict(callers)

    def find_definitions(self, symbol_name: str) -> list[Symbol]:
        """Return all symbols with this name across the project."""
        return self._symbol_index.get(symbol_name, [])


# ── Report ────────────────────────────────────────────────────────────────────

@dataclass
class ResolutionReport:
    results: dict[str, ParseResult]
    symbol_index: dict[str, list[Symbol]]
    resolved: list[tuple[str, ImportRef]]
    unresolved: list[tuple[str, ImportRef]]

    def print_summary(self):
        total_files = len(self.results)
        total_syms = sum(len(v) for v in self.symbol_index.values())
        print(f"Files parsed  : {total_files}")
        print(f"Unique symbols: {len(self.symbol_index)}")
        print(f"Total symbols : {total_syms}")
        print(f"Imports resolved  : {len(self.resolved)}")
        print(f"Imports unresolved: {len(self.unresolved)}")

    def print_symbol_table(self):
        print("\n── Symbol table ──")
        for name, syms in sorted(self.symbol_index.items()):
            for s in syms:
                rel = Path(s.defined_in).name
                print(f"  {s.kind:<10} {s.qualified:<40} {rel}:{s.lineno}")

    def print_cross_refs(self):
        print("\n── Cross-file imports ──")
        for src, imp in self.resolved:
            src_name = Path(src).name
            dst_name = Path(imp.origin_file).name if imp.origin_file else "?"
            print(f"  {src_name}  →  {imp.alias!r} from {imp.module!r}  ({dst_name})")


# ── Public helpers ────────────────────────────────────────────────────────────

def parse_file(path: str | Path) -> ParseResult:
    walker = ASTWalker(filepath=str(path))
    path = Path(path)
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        walker.visit(tree)
    except SyntaxError as e:
        walker.result.errors.append(f"SyntaxError: {e}")
    except OSError as e:
        walker.result.errors.append(f"IOError: {e}")
    return walker.result


def parse_source(source: str, filename: str = "<string>") -> ParseResult:
    walker = ASTWalker(filepath=filename)
    try:
        tree = ast.parse(source, filename=filename)
        walker.visit(tree)
    except SyntaxError as e:
        walker.result.errors.append(f"SyntaxError: {e}")
    return walker.result


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(prog="orion", description="Orion AST analyser")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("scan", help="scan a project directory")
    sp.add_argument("root", help="project root")
    sp.add_argument("--symbols", action="store_true", help="print symbol table")
    sp.add_argument("--xrefs", action="store_true", help="print cross-file imports")

    fp = sub.add_parser("file", help="parse a single file")
    fp.add_argument("path")

    cf = sub.add_parser("callers", help="find call sites of a symbol")
    cf.add_argument("root")
    cf.add_argument("symbol")

    args = p.parse_args()

    if args.cmd == "file":
        r = parse_file(args.path)
        print(f"Symbols  : {[s.qualified for s in r.symbols]}")
        print(f"Imports  : {[i.module for i in r.imports]}")
        print(f"Calls    : {r.calls[:10]}")

    elif args.cmd == "scan":
        analyser = ProjectAnalyser(args.root).scan()
        report = analyser.resolve()
        report.print_summary()
        if args.symbols:
            report.print_symbol_table()
        if args.xrefs:
            report.print_cross_refs()

    elif args.cmd == "callers":
        analyser = ProjectAnalyser(args.root).scan()
        callers = analyser.find_callers(args.symbol)
        defs = analyser.find_definitions(args.symbol)
        print(f"\nDefinitions of {args.symbol!r}:")
        for s in defs:
            print(f"  {s.defined_in}:{s.lineno}  ({s.kind})")
        print(f"\nCallers of {args.symbol!r}:")
        for filepath, lines in callers.items():
            print(f"  {Path(filepath).name}: lines {lines}")


__all__ = ["parse_file", "parse_source", "ProjectAnalyser", "main"]


if __name__ == "__main__":
    main()
