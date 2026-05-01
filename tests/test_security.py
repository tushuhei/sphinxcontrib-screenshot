
import os
import pytest
from unittest.mock import MagicMock, PropertyMock
from sphinxcontrib.screenshot._common import _PlaywrightDirective

def test_resolve_url_security():
    # Setup mock directive
    directive = _PlaywrightDirective.__new__(_PlaywrightDirective)
    env = MagicMock()
    # Use absolute paths that are consistent
    env.srcdir = "/app/docs"
    env.docname = "index"
    env.doc2path.return_value = "/app/docs/index.rst"

    # Mock the env property
    type(directive).env = PropertyMock(return_value=env)

    # We need to mock _evaluate_substitutions as well
    directive._evaluate_substitutions = lambda x: x

    # 1. Test allowed file path within srcdir
    allowed_path = "/image.html"
    resolved = directive._resolve_url(allowed_path)
    assert resolved == "file:///app/docs/image.html"

    # 2. Test relative path within srcdir
    resolved = directive._resolve_url("./local.html")
    assert resolved == "file:///app/docs/local.html"

    # 3. Test absolute file:// URL within srcdir
    resolved = directive._resolve_url("file:///app/docs/image.html")
    assert resolved == "file:///app/docs/image.html"

    # 4. Test path traversal attempt (relative)
    # "../../etc/passwd" relative to docdir "/app/docs" -> "/etc/passwd"
    with pytest.raises(RuntimeError, match="Security Error"):
        directive._resolve_url("../../etc/passwd")

    # 5. Test path traversal attempt (absolute file://)
    with pytest.raises(RuntimeError, match="Security Error"):
        directive._resolve_url("file:///etc/passwd")

    # 6. Test absolute path outside srcdir (as seen by Sphinx)
    # "/../etc/passwd" -> joined with srcdir "/app/docs" -> "/etc/passwd"
    with pytest.raises(RuntimeError, match="Security Error"):
        directive._resolve_url("/../etc/passwd")

    # 7. Test http/https are still allowed
    assert directive._resolve_url("http://example.com") == "http://example.com"
    assert directive._resolve_url("https://example.com") == "https://example.com"

# CLEANUP: Remove the PropertyMock from the class to avoid side effects on other tests
@pytest.fixture(autouse=True)
def cleanup_mock():
    yield
    if hasattr(_PlaywrightDirective, 'env'):
        del _PlaywrightDirective.env

if __name__ == "__main__":
    # Manual debug
    directive = _PlaywrightDirective.__new__(_PlaywrightDirective)
    env = MagicMock()
    env.srcdir = "/app/docs"
    env.docname = "index"
    env.doc2path.return_value = "/app/docs/index.rst"
    type(directive).env = PropertyMock(return_value=env)
    directive._evaluate_substitutions = lambda x: x

    print("Testing relative path traversal...")
    try:
        res = directive._resolve_url("../../etc/passwd")
        print(f"FAILED: Result: {res}")
    except RuntimeError as e:
        print(f"PASSED: Caught expected error: {e}")

    print("Testing absolute file:// traversal...")
    try:
        res = directive._resolve_url("file:///etc/passwd")
        print(f"FAILED: Result: {res}")
    except RuntimeError as e:
        print(f"PASSED: Caught expected error: {e}")

    print("Testing allowed relative path...")
    try:
        res = directive._resolve_url("./local.html")
        print(f"PASSED: Result: {res}")
    except Exception as e:
        print(f"FAILED: Caught unexpected error: {e}")

    # Clean up for next run if it's imported
    del _PlaywrightDirective.env
