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

import hashlib
import os
import typing
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import ViewList
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective

Meta = typing.TypedDict('Meta', {
    'version': str,
    'parallel_read_safe': bool,
    'parallel_write_safe': bool
})

__version__ = '0.1.2'


class ScreenshotDirective(SphinxDirective):
  """Sphinx Screenshot Dirctive.

  This directive embeds a screenshot of a webpage.

  # Example

  You can simply pass a URL for a webpage that you want to take a screenshot.

  ```rst
  .. screenshot:: http://www.example.com
  ```

  You can also specify the screen size for the screenshot with `width` and
  `height` parameters in pixel.

  ```rst
  .. screenshot:: http://www.example.com
    :width: 1280
    :height: 960
  ```

  You can include a caption for the screenshot's `figure` directive.

  ```rst
  .. screenshot:: http://www.example.com
    :caption: This is a screenshot for www.example.com
  ```

  You can describe the interaction that you want to have with the webpage
  before taking a screenshot in JavaScript.

  ```rst
  .. screenshot:: http://www.example.com

    document.querySelector('button').click();
  ```
  """

  required_arguments = 1  # URL
  has_content = True
  option_spec = {
      'height': directives.positive_int,
      'width': directives.positive_int,
      'caption': directives.unchanged,
      'figclass': directives.unchanged,
  }
  pool = ThreadPoolExecutor()

  @staticmethod
  def take_screenshot(url: str, width: int, height: int, filepath: str,
                      init_script: str, interactions: str):
    """Takes a screenshot with Playwright's Chromium browser.

    Args:
      url (str): The HTTP/HTTPS URL of the webpage to screenshot.
      width (int): The width of the screenshot in pixels.
      height (int): The height of the screenshot in pixels.
      filepath (str): The path to save the screenshot to.
      init_script (str): JavaScript code to be evaluated after the document
        was created but before any of its scripts were run. See more details at
        https://playwright.dev/python/docs/api/class-page#page-add-init-script
      interactions (str): JavaScript code to run before taking the screenshot
        after the page was loaded.
    """
    with sync_playwright() as playwright:
      browser = playwright.chromium.launch()
      page = browser.new_page()
      page.set_default_timeout(10000)
      page.set_viewport_size({'width': width, 'height': height})
      try:
        if init_script:
          page.add_init_script(init_script)
        page.goto(url)
        page.wait_for_load_state('networkidle')

        # Execute interactions
        if interactions:
          page.evaluate(interactions)
          page.wait_for_load_state('networkidle')
      except PlaywrightTimeoutError:
        raise RuntimeError('Timeout error occured at %s in executing\n%s' %
                           (url, interactions))
      page.screenshot(path=filepath)
      page.close()
      browser.close()

  def run(self) -> typing.List[nodes.Node]:
    screenshot_init_script: str = self.env.config.screenshot_init_script or ''

    # Ensure the screenshots directory exists
    ss_dirpath = os.path.join(self.env.app.outdir, '_static', 'screenshots')
    os.makedirs(ss_dirpath, exist_ok=True)

    # Parse parameters
    url = self.arguments[0]
    height = self.options.get('height', 960)
    width = self.options.get('width', 1280)
    caption_text = self.options.get('caption', '')
    figclass = self.options.get('figclass', '')
    interactions = '\n'.join(self.content)

    if urlparse(url).scheme not in {'http', 'https'}:
      raise RuntimeError(
          f'Invalid URL: {url}. Only HTTP/HTTPS URLs are supported.')

    # Generate filename based on hash of parameters
    hash_input = f'{url}_{height}_{width}_{interactions}'
    filename = hashlib.md5(hash_input.encode()).hexdigest() + '.png'
    filepath = os.path.join(ss_dirpath, filename)

    # Check if the file already exists. If not, take a screenshot
    if not os.path.exists(filepath):
      fut = self.pool.submit(ScreenshotDirective.take_screenshot, url, width,
                             height, filepath, screenshot_init_script,
                             interactions)
      fut.result()

    # Create image and figure nodes
    docdir = os.path.dirname(self.env.doc2path(self.env.docname))
    rel_ss_dirpath = os.path.relpath(ss_dirpath, start=docdir)
    rel_filepath = os.path.join(rel_ss_dirpath, filename).replace(os.sep, '/')
    image_node = nodes.image(uri=rel_filepath)
    figure_node = nodes.figure('', image_node)

    if figclass:
      figure_node['classes'].append(figclass)

    if caption_text:
      parsed = nodes.Element()
      self.state.nested_parse(
          ViewList([caption_text], source=''), self.content_offset, parsed)
      figure_node += nodes.caption(parsed[0].source or '', '',
                                   *parsed[0].children)

    return [figure_node]


def setup(app: Sphinx) -> Meta:
  app.add_directive('screenshot', ScreenshotDirective)
  app.add_config_value('screenshot_init_script', '', 'env')
  return {
      'version': __version__,
      'parallel_read_safe': True,
      'parallel_write_safe': True,
  }
