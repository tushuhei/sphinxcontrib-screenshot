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

from io import StringIO

import pytest
from bs4 import BeautifulSoup
from PIL import Image
from sphinx.testing.util import SphinxTestApp


@pytest.mark.sphinx('html')
def test_default(app: SphinxTestApp, status: StringIO,
                 warning: StringIO) -> None:
  app.build()
  out_html = app.outdir / "index.html"
  soup = BeautifulSoup(out_html.read_text(), "html.parser")

  # Every screenshot directive should become an image.
  imgs = soup.find_all('img')
  assert len(list(imgs)) == 4

  # The image size should be set as specified.
  img_obj = Image.open(app.outdir / imgs[0]['src'])
  width, height = img_obj.size
  assert width == 480
  assert height == 320

  # The caption should be rendered.
  figcaption = soup.select_one('figcaption span')
  assert figcaption and (figcaption.get_text().strip()
                         == 'This is a test screenshot')

  # The images should be different after the specified user interaction.
  img_before_interaction = Image.open(app.outdir / imgs[0]['src'])
  img_after_interaction = Image.open(app.outdir / imgs[2]['src'])
  assert list(img_before_interaction.getdata()) != list(
      img_after_interaction.getdata())

  # The images should be the same if the difference is only the caption.
  img_with_caption_a = imgs[0]
  img_with_caption_b = imgs[1]
  assert img_with_caption_a['src'] == img_with_caption_b['src']

  # The figure node should have the class name specified.
  assert 'round' in soup.find_all('figure')[-1]['class']
