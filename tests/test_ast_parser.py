import pytest
from Orion import parse_file, parse_source

def test_imports():
    pass  # Existing test function

def test_ast_parser():
    pass  # Existing test function

def test_parse_file():
    source_code = """
def hello_world():
    print("Hello, World!")
"""
    result = parse_source(source_code)
    assert "hello_world" in result.functions

def test_parse_source():
    source_code = """
class MyClass:
    def my_method(self):
        pass
"""
    result = parse_source(source_code)
    assert "MyClass" in result.classes
