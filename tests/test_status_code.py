# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from io import StringIO

import pytest
from sphinx.testing.util import SphinxTestApp


@pytest.mark.sphinx('html', testroot="status-code-warning")
def test_status_code_warning_on_404(app: SphinxTestApp, status: StringIO,
                                    warning: StringIO) -> None:
  """Test that 404 status code generates a warning with default settings.

  This test uses a WSGI app that returns 404, which should trigger a warning
  since the default expected status codes are 200,302.
  """
  app.build()
  warning_text = warning.getvalue()

  assert "404" in warning_text
  assert "200,302" in warning_text
  assert "WARNING" in warning_text
