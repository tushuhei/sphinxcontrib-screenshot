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
from bs4 import BeautifulSoup
from PIL import Image
from sphinx.testing.util import SphinxTestApp


@pytest.mark.sphinx('html', testroot="locator")
def test_locator_option(app: SphinxTestApp, status: StringIO,
                        warning: StringIO) -> None:
  """A :locator: directive crops the screenshot to the matched element.

  The fixture page contains two boxes:
    - ``#foo`` (200x100, the locator target)
    - ``#bar`` (400x50)

  The captured image must match ``#foo``'s bounding box (200x100 at
  the configured device scale factor of 1), distinct from the default
  viewport size that would otherwise apply.
  """
  app.build()
  out_html = app.outdir / "index.html"

  soup = BeautifulSoup(out_html.read_text(), "html.parser")
  imgs = soup.find_all('img')
  assert imgs, "expected a screenshot image"

  img_path = app.outdir / imgs[0]['src']
  with Image.open(img_path) as img:
    width, height = img.size

  assert (width, height) == (200, 100), (
      f"expected #foo's bounding box (200x100), got {width}x{height}")
