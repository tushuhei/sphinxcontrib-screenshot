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


@pytest.mark.sphinx('html', testroot="color-schemes")
def test_color_scheme_option(app: SphinxTestApp, status: StringIO,
                             warning: StringIO, image_regression) -> None:
  app.build()
  out_html = app.outdir / "index.html"

  soup = BeautifulSoup(out_html.read_text(), "html.parser")
  imgs = soup.find_all('img')

  img_path = app.outdir / imgs[0]['src']
  with open(img_path, "rb") as fd:
    image_regression.check(fd.read())


@pytest.mark.sphinx('html', testroot="default-color-scheme")
def test_default_color_scheme_config_parameter(app: SphinxTestApp,
                                               status: StringIO,
                                               warning: StringIO,
                                               image_regression) -> None:
  app.build()
  out_html = app.outdir / "index.html"

  soup = BeautifulSoup(out_html.read_text(), "html.parser")
  imgs = soup.find_all('img')

  img_path = app.outdir / imgs[0]['src']
  with open(img_path, "rb") as fd:
    image_regression.check(fd.read())


@pytest.mark.sphinx('html', testroot="auto-dark")
def test_auto_dark_generates_two_images(app: SphinxTestApp, status: StringIO,
                                        warning: StringIO) -> None:
  """Test that :color-scheme: auto generates two screenshots.

  The screenshots should have appropriate CSS classes.
  """
  app.build()
  out_html = app.outdir / "index.html"

  soup = BeautifulSoup(out_html.read_text(), "html.parser")
  imgs = soup.find_all('img')

  assert len(imgs) == 2, "Should generate exactly two images (light and dark)"

  light_img = imgs[0]
  dark_img = imgs[1]

  assert 'only-light' in light_img.get(
      'class', []), "First image should have 'only-light' class"
  assert 'only-dark' in dark_img.get(
      'class', []), "Second image should have 'only-dark' class"

  screenshots_dir = app.outdir / "_static" / "screenshots"
  assert screenshots_dir.exists(), "Screenshots directory should exist"

  light_img_path = app.outdir / light_img['src']
  dark_img_path = app.outdir / dark_img['src']

  assert light_img_path.exists(), "Light mode screenshot should exist"
  assert dark_img_path.exists(), "Dark mode screenshot should exist"

  assert light_img_path != dark_img_path, (
      "Light and dark screenshots should be different files")


@pytest.mark.sphinx('html', testroot="auto-dark")
def test_auto_dark_includes_css(app: SphinxTestApp, status: StringIO,
                                warning: StringIO) -> None:
  """Test that the CSS file is included when using :color-scheme: auto."""
  app.build()
  out_html = app.outdir / "index.html"

  soup = BeautifulSoup(out_html.read_text(), "html.parser")
  css_links = soup.find_all('link', rel='stylesheet')

  css_hrefs = [link.get('href', '') for link in css_links]
  assert any('screenshot-theme.css' in href for href in css_hrefs), (
      "screenshot-theme.css should be included in the HTML")

  css_file_path = (
      app.outdir / "_static" / "sphinxcontrib-screenshot" /
      "screenshot-theme.css")
  assert css_file_path.exists(), (
      "CSS file should be copied to output directory")
