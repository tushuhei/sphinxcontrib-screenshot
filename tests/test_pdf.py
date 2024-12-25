# Copyright 2023 Google LLC
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

import os

import pytest
from bs4 import BeautifulSoup
from sphinx.testing.util import SphinxTestApp


@pytest.mark.sphinx('html', testroot='pdf')
def test_default(app: SphinxTestApp) -> None:
  app.build()
  out_html = app.outdir / "index.html"
  soup = BeautifulSoup(out_html.read_text(), "html.parser")
  img = soup.select_one('img')
  assert img

  imgsrc = str(img['src'])
  root, ext = os.path.splitext(os.path.basename(imgsrc))
  pdf_filepath = app.outdir / '_static' / 'screenshots' / f'{root}.pdf'
  # Should generate a screenshot PDF.
  assert os.path.exists(pdf_filepath)
