from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest

from sphinxcontrib.screenshot._common import _PlaywrightDirective


def test_resolve_url_security():
  # Setup mock directive
  directive = _PlaywrightDirective.__new__(_PlaywrightDirective)
  env = MagicMock()

  # Create a real temporary directory for reliable resolution testing
  import tempfile
  with tempfile.TemporaryDirectory() as tmp_dir:
    srcdir = Path(tmp_dir).resolve()
    env.srcdir = str(srcdir)
    env.docname = 'index'

    # doc2path should return a path inside srcdir
    index_rst = srcdir / 'index.rst'
    env.doc2path.return_value = str(index_rst)

    # Mock the env property
    type(directive).env = PropertyMock(return_value=env)

    # We need to mock _evaluate_substitutions as well
    directive._evaluate_substitutions = lambda x: x

    # 1. Test allowed file path within srcdir
    image_html = srcdir / 'image.html'
    image_html.touch()
    allowed_path = '/image.html'
    resolved = directive._resolve_url(allowed_path)
    assert resolved == image_html.as_uri()

    # 2. Test relative path within srcdir
    local_html = srcdir / 'local.html'
    local_html.touch()
    resolved = directive._resolve_url('./local.html')
    assert resolved == local_html.as_uri()

    # 3. Test absolute file:// URL within srcdir
    target_uri = image_html.as_uri()
    resolved = directive._resolve_url(target_uri)
    assert resolved == target_uri

    # 4. Test path traversal attempt (relative)
    # We use a path that is guaranteed to be outside the tmp_dir
    with pytest.raises(RuntimeError, match='Security Error'):
      directive._resolve_url('../../etc/passwd')

    # 5. Test path traversal attempt (absolute file://)
    # On Windows, /etc/passwd doesn't exist, but we just want to see it blocked
    with pytest.raises(RuntimeError, match='Security Error'):
      directive._resolve_url('file:///etc/passwd')

    # 6. Test absolute path outside srcdir
    with pytest.raises(RuntimeError, match='Security Error'):
      directive._resolve_url('/../etc/passwd')

    # 7. Test http/https are still allowed
    assert directive._resolve_url('http://example.com') == 'http://example.com'
    res = directive._resolve_url('https://example.com')
    assert res == 'https://example.com'


# CLEANUP: Remove the PropertyMock from the class to avoid side effects
@pytest.fixture(autouse=True)
def cleanup_mock():
  yield
  if hasattr(_PlaywrightDirective, 'env'):
    del _PlaywrightDirective.env


if __name__ == '__main__':
  # Manual debug setup
  directive = _PlaywrightDirective.__new__(_PlaywrightDirective)
  env = MagicMock()

  import tempfile
  with tempfile.TemporaryDirectory() as tmp_dir:
    srcdir = Path(tmp_dir).resolve()
    env.srcdir = str(srcdir)
    env.docname = 'index'
    index_rst = srcdir / 'index.rst'
    env.doc2path.return_value = str(index_rst)
    type(directive).env = PropertyMock(return_value=env)
    directive._evaluate_substitutions = lambda x: x

    print('Testing relative path traversal...')
    try:
      res = directive._resolve_url('../../etc/passwd')
      print(f'FAILED: Result: {res}')
    except RuntimeError as e:
      print(f'PASSED: Caught expected error: {e}')

    print('Testing absolute file:// traversal...')
    try:
      res = directive._resolve_url('file:///etc/passwd')
      print(f'FAILED: Result: {res}')
    except RuntimeError as e:
      print(f'PASSED: Caught expected error: {e}')

    print('Testing allowed relative path...')
    try:
      local_html = srcdir / 'local.html'
      local_html.touch()
      res = directive._resolve_url('./local.html')
      print(f'PASSED: Result: {res}')
    except Exception as e:
      print(f'FAILED: Caught unexpected error: {e}')

  # Clean up
  del _PlaywrightDirective.env
