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
from sphinx.testing.util import SphinxTestApp


@pytest.mark.sphinx('html', testroot="full-page")
def test_full_page_option(app: SphinxTestApp, status: StringIO,
                          warning: StringIO, image_regression) -> None:
  app.build()
  out_html = app.outdir / "index.html"

  soup = BeautifulSoup(out_html.read_text(), "html.parser")
  imgs = soup.find_all('img')

  img_path = app.outdir / imgs[0]['src']
  with open(img_path, "rb") as fd:
    image_regression.check(fd.read())


@pytest.mark.sphinx('html', testroot="default-full-page")
def test_default_full_page(app: SphinxTestApp, status: StringIO,
                           warning: StringIO, image_regression) -> None:
  app.build()
  out_html = app.outdir / "index.html"

  soup = BeautifulSoup(out_html.read_text(), "html.parser")
  imgs = soup.find_all('img')

  img_path = app.outdir / imgs[0]['src']
  with open(img_path, "rb") as fd:
    image_regression.check(fd.read())
