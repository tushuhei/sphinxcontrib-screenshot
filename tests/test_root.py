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

import pytest
from bs4 import BeautifulSoup
from PIL import Image
from sphinx.testing.util import SphinxTestApp


@pytest.mark.sphinx('html', testroot='root')
def test_default(app: SphinxTestApp) -> None:
  app.build()

  def test_index():
    soup = BeautifulSoup((app.outdir / "index.html").read_text(),
                         "html.parser")

    # Every screenshot directive should become an image.
    imgs = soup.find_all('img')
    assert len(list(imgs)) == 4

    # The image size should be set as specified.
    img_obj = Image.open(app.outdir / imgs[0]['src'])
    width, height = img_obj.size
    assert width == 480
    assert height == 320

    # The images should be the same if the difference is only the caption.
    img_with_caption_a = imgs[0]
    img_with_caption_b = imgs[1]
    assert img_with_caption_a['src'] == img_with_caption_b['src']

    # The images should be different after the specified user interaction.
    imgsrc_before_interaction = app.outdir / imgs[1]['src']
    imgsrc_after_interaction = app.outdir / imgs[2]['src']
    assert imgsrc_before_interaction != imgsrc_after_interaction
    assert list(Image.open(imgsrc_before_interaction).getdata()) != list(
        Image.open(imgsrc_after_interaction).getdata())

    # High reso image should have a larger size.
    imgsrc_standard = app.outdir / imgs[0]['src']
    imgsrc_highreso = app.outdir / imgs[3]['src']
    assert (Image.open(imgsrc_highreso).width ==
            Image.open(imgsrc_standard).width * 2)

  def test_sections_index():
    soup = BeautifulSoup((app.outdir / "sections" / "index.html").read_text(),
                         "html.parser")

    # Every screenshot directive should become an image.
    imgs = soup.find_all('img')
    assert len(list(imgs)) == 2

    # The images should be the same.
    imgsrc_relative = app.outdir / "sections" / imgs[0]['src']
    imgsrc_absolute = app.outdir / "sections" / imgs[1]['src']
    assert imgsrc_relative != imgsrc_absolute
    assert list(Image.open(imgsrc_relative).getdata()) == list(
        Image.open(imgsrc_absolute).getdata())

  test_index()
  test_sections_index()


@pytest.mark.sphinx('html', testroot="default-viewport")
def test_default_viewport(app: SphinxTestApp) -> None:
  """Test the 'screenshot_default_viewport_width' and
  'screenshot_default_viewport_height' configuration parameters."""
  app.build()
  out_html = app.outdir / "index.html"

  soup = BeautifulSoup(out_html.read_text(), "html.parser")
  imgs = soup.find_all('img')

  img_obj = Image.open(app.outdir / imgs[0]['src'])
  width, height = img_obj.size
  assert width == 1920
  assert height == 1200
