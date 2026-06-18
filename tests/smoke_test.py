import pytest

def test_imports():
    try:
        from Orion import parse_file, parse_source
    except ImportError as e:
        pytest.fail(f"Failed to import module: {e}")

def test_ast_parser():
    # Add basic tests for the AST parser here
    pass

if __name__ == '__main__':
    pytest.main()
