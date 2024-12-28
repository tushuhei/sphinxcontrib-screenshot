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
import importlib
import importlib.metadata
import os
import threading
import typing
import wsgiref.simple_server
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import ViewList
from playwright._impl._helper import ColorScheme
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from portpicker import pick_unused_port
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.util.docutils import SphinxDirective

Meta = typing.TypedDict('Meta', {
    'version': str,
    'parallel_read_safe': bool,
    'parallel_write_safe': bool
})


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

  Use `figclass` option if you want to specify a class name to the image.

  ```rst
  .. screenshot:: http://www.example.com
    :figclass: foo
  ```

  It also generates a PDF file when `pdf` option is given, which might be
  useful when you need scalable image assets.

  ```rst
  .. screenshot:: http://www.example.com
    :pdf:
  ```
  """

  required_arguments = 1  # URL
  has_content = True
  option_spec = {
      'height': directives.positive_int,
      'width': directives.positive_int,
      'caption': directives.unchanged,
      'figclass': directives.unchanged,
      'pdf': directives.flag,
      'color-scheme': str,
  }
  pool = ThreadPoolExecutor()

  @staticmethod
  def take_screenshot(url: str, width: int, height: int, filepath: str,
                      init_script: str, interactions: str, generate_pdf: bool,
                      color_scheme: ColorScheme):
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
      generate_pdf (bool): Generate a PDF file along with the screenshot.
      color_scheme (str): The preferred color scheme. Can be 'light' or 'dark'.
    """
    with sync_playwright() as playwright:
      browser = playwright.chromium.launch()
      page = browser.new_page(color_scheme=color_scheme)
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
      if generate_pdf:
        page.emulate_media(media='screen')
        root, ext = os.path.splitext(filepath)
        page.pdf(width=f'{width}px', height=f'{height}px', path=root + '.pdf')
      page.close()
      browser.close()

  def evaluate_substitutions(self, text: str) -> str:
    substitutions = self.state.document.substitution_defs
    for key, value in substitutions.items():
      text = text.replace(f"|{key}|", value.astext())
    return text

  def run(self) -> typing.List[nodes.Node]:
    screenshot_init_script: str = self.env.config.screenshot_init_script or ''

    # Ensure the screenshots directory exists
    ss_dirpath = os.path.join(self.env.app.outdir, '_static', 'screenshots')
    os.makedirs(ss_dirpath, exist_ok=True)

    # Parse parameters
    raw_url = self.arguments[0]
    url = self.evaluate_substitutions(raw_url)
    height = self.options.get('height',
                              self.env.config.screenshot_default_height)
    width = self.options.get('width', self.env.config.screenshot_default_width)
    color_scheme = self.options.get('color-scheme', 'null')
    caption_text = self.options.get('caption', '')
    figclass = self.options.get('figclass', '')
    pdf = 'pdf' in self.options
    interactions = '\n'.join(self.content)

    if urlparse(url).scheme not in {'http', 'https'}:
      raise RuntimeError(
          f'Invalid URL: {url}. Only HTTP/HTTPS URLs are supported.')

    # Generate filename based on hash of parameters
    hash_input = f'{raw_url}_{height}_{width}_{color_scheme}_{interactions}'
    filename = hashlib.md5(hash_input.encode()).hexdigest() + '.png'
    filepath = os.path.join(ss_dirpath, filename)

    # Check if the file already exists. If not, take a screenshot
    if not os.path.exists(filepath):
      fut = self.pool.submit(ScreenshotDirective.take_screenshot, url, width,
                             height, filepath, screenshot_init_script,
                             interactions, pdf, color_scheme)
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


app_threads = {}


def resolve_wsgi_app_import(app: Sphinx, app_path: str):
  module_path, app_attribute = app_path.split(":")
  module = importlib.import_module(module_path)
  app_attr = getattr(module, app_attribute)
  wsgi_app = app_attr(app) if callable(app_attr) else app_attr
  return wsgi_app


def setup_apps(app: Sphinx, config: Config):
  """Start the WSGI application threads.

    A new replacement is created for each WSGI app."""
  for wsgi_app_name, wsgi_app_path in config.screenshot_apps.items():
    port = pick_unused_port()
    config.rst_prolog = (
        config.rst_prolog or
        "") + f"\n.. |{wsgi_app_name}| replace:: http://localhost:{port}\n"
    wsgi_app = resolve_wsgi_app_import(app, wsgi_app_path)
    httpd = wsgiref.simple_server.make_server("localhost", port, wsgi_app)
    thread = threading.Thread(target=httpd.serve_forever)
    thread.start()
    app_threads[wsgi_app_name] = (httpd, thread)


def teardown_apps(app: Sphinx, exception: typing.Optional[Exception]):
  """Shut down the WSGI application threads."""
  for httpd, thread in app_threads.values():
    httpd.shutdown()
    thread.join()


def setup(app: Sphinx) -> Meta:
  app.add_directive('screenshot', ScreenshotDirective)
  app.add_config_value('screenshot_init_script', '', 'env')
  app.add_config_value(
      'screenshot_default_width',
      1280,
      'env',
      description="The default width for screenshots")
  app.add_config_value(
      'screenshot_default_height',
      960,
      'env',
      description="The default height for screenshots")
  app.add_config_value(
      'screenshot_apps', {},
      'env',
      types=[dict[str, typing.Any]],
      description="A dict of WSGI apps")
  app.connect('config-inited', setup_apps)
  app.connect('build-finished', teardown_apps)
  return {
      'version': importlib.metadata.version('sphinxcontrib-screenshot'),
      'parallel_read_safe': True,
      'parallel_write_safe': True,
  }
