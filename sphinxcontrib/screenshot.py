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
from docutils.parsers.rst.directives.images import Figure
from playwright._impl._helper import ColorScheme
from playwright.sync_api import Browser, BrowserContext
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

ContextBuilder = typing.Optional[typing.Callable[[Browser, str, str],
                                                 BrowserContext]]


class ScreenshotDirective(SphinxDirective, Figure):
  """Sphinx Screenshot Dirctive.

  This directive embeds a screenshot of a webpage.

  # Example

  You can simply pass a URL for a webpage that you want to take a screenshot.

  ```rst
  .. screenshot:: http://www.example.com
  ```

  You can also specify the screen size for the screenshot with
  `viewport-width` and `viewport-height` parameters in pixel.

  ```rst
  .. screenshot:: http://www.example.com
    :viewport-width: 1280
    :viewport-height: 960
  ```

  You can describe the interaction that you want to have with the webpage
  before taking a screenshot in JavaScript.

  ```rst
  .. screenshot:: http://www.example.com

    document.querySelector('button').click();
  ```

  It also generates a PDF file when `pdf` option is given, which might be
  useful when you need scalable image assets.

  ```rst
  .. screenshot:: http://www.example.com
    :pdf:
  ```
  """

  required_arguments = 1  # URL
  option_spec = {
      **Figure.option_spec,
      'browser': str,
      'viewport-height': directives.positive_int,
      'viewport-width': directives.positive_int,
      'interactions': str,
      'pdf': directives.flag,
      'color-scheme': str,
      'full-page': directives.flag,
      'context': str,
      'headers': directives.unchanged,
      'locale': str,
      'timezone': str,
  }
  pool = ThreadPoolExecutor()

  @staticmethod
  def take_screenshot(url: str, browser_name: str, viewport_width: int,
                      viewport_height: int, filepath: str, init_script: str,
                      interactions: str, generate_pdf: bool,
                      color_scheme: ColorScheme, full_page: bool,
                      context_builder: ContextBuilder, headers: dict,
                      locale: typing.Optional[str],
                      timezone: typing.Optional[str]):
    """Takes a screenshot with Playwright's Chromium browser.

    Args:
      url (str): The HTTP/HTTPS URL of the webpage to screenshot.
      browser_name (str): Browser to use ('chromium', 'firefox' or 'webkit').
      viewport_width (int): The width of the screenshot in pixels.
      viewport_height (int): The height of the screenshot in pixels.
      filepath (str): The path to save the screenshot to.
      init_script (str): JavaScript code to be evaluated after the document
        was created but before any of its scripts were run. See more details at
        https://playwright.dev/python/docs/api/class-page#page-add-init-script
      interactions (str): JavaScript code to run before taking the screenshot
        after the page was loaded.
      generate_pdf (bool): Generate a PDF file along with the screenshot.
      color_scheme (str): The preferred color scheme. Can be 'light' or 'dark'.
      full_page (bool): Take a full page screenshot.
      context: A method to build the Playwright context.
      headers (dict): Custom request header.
      locale (str, optional): User locale for the request.
      timezone (str, optional): User timezone for the request.
    """
    with sync_playwright() as playwright:
      browser: Browser = getattr(playwright, browser_name).launch()

      if context_builder:
        try:
          context = context_builder(browser, url, color_scheme)
        except PlaywrightTimeoutError:
          raise RuntimeError(
              'Timeout error occured at %s in executing py init script %s' %
              (url, context_builder.__name__))
      else:
        context = browser.new_context(
            color_scheme=color_scheme, locale=locale, timezone_id=timezone)

      page = context.new_page()
      page.set_default_timeout(10000)
      page.set_viewport_size({
          'width': viewport_width,
          'height': viewport_height
      })

      try:
        if init_script:
          page.add_init_script(init_script)
        page.set_extra_http_headers(headers)
        page.goto(url)
        page.wait_for_load_state('networkidle')

        # Execute interactions
        if interactions:
          page.evaluate(interactions)
          page.wait_for_load_state('networkidle')
      except PlaywrightTimeoutError:
        raise RuntimeError('Timeout error occured at %s in executing\n%s' %
                           (url, interactions))
      page.screenshot(path=filepath, full_page=full_page)
      if generate_pdf:
        page.emulate_media(media='screen')
        root, ext = os.path.splitext(filepath)
        page.pdf(
            width=f'{viewport_width}px',
            height=f'{viewport_height}px',
            path=root + '.pdf')
      page.close()
      browser.close()

  def evaluate_substitutions(self, text: str) -> str:
    substitutions = self.state.document.substitution_defs
    for key, value in substitutions.items():
      text = text.replace(f"|{key}|", value.astext())
    return text

  def run(self) -> typing.Sequence[nodes.Node]:
    screenshot_init_script: str = self.env.config.screenshot_init_script or ''
    docdir = os.path.dirname(self.env.doc2path(self.env.docname))

    # Ensure the screenshots directory exists
    ss_dirpath = os.path.join(self.env.app.outdir, '_static', 'screenshots')
    os.makedirs(ss_dirpath, exist_ok=True)

    # Parse parameters
    raw_path = self.arguments[0]
    url_or_filepath = self.evaluate_substitutions(raw_path)

    # Check if the path is a local file path.
    if urlparse(url_or_filepath).scheme == '':
      # root-relative path
      if url_or_filepath.startswith('/'):
        url_or_filepath = os.path.join(self.env.srcdir,
                                       url_or_filepath.lstrip('/'))
      # document-relative path
      else:
        url_or_filepath = os.path.join(docdir, url_or_filepath)
      url_or_filepath = "file://" + url_or_filepath

    if urlparse(url_or_filepath).scheme not in {'http', 'https', 'file'}:
      raise RuntimeError(
          f'Invalid URL: {url_or_filepath}. ' +
          'Only HTTP/HTTPS/FILE URLs or root/document-relative file paths ' +
          'are supported.')

    interactions = self.options.get('interactions', '')
    browser = self.options.get('browser',
                               self.env.config.screenshot_default_browser)
    viewport_height = self.options.get(
        'viewport-height', self.env.config.screenshot_default_viewport_height)
    viewport_width = self.options.get(
        'viewport-width', self.env.config.screenshot_default_viewport_width)
    color_scheme = self.options.get(
        'color-scheme', self.env.config.screenshot_default_color_scheme)
    pdf = 'pdf' in self.options
    full_page = ('full-page' in self.options or
                 self.env.config.screenshot_default_full_page)
    locale = self.options.get('locale',
                              self.env.config.screenshot_default_locale)
    timezone = self.options.get('timezone',
                                self.env.config.screenshot_default_timezone)
    context = self.options.get('context', '')
    headers = self.options.get('headers', '')

    request_headers = {**self.env.config.screenshot_default_headers}
    if headers:
      for header in headers.strip().split("\n"):
        name, value = header.split(" ", 1)
        request_headers[name] = value

    # Generate filename based on hash of parameters
    hash_input = "_".join([
        raw_path, browser,
        str(viewport_height),
        str(viewport_width), color_scheme, context, interactions,
        str(full_page)
    ])
    filename = hashlib.md5(hash_input.encode()).hexdigest() + '.png'
    filepath = os.path.join(ss_dirpath, filename)

    if context:
      context_builder_path = self.config.screenshot_contexts[context]
      context_builder = resolve_python_method(context_builder_path)
    else:
      context_builder = None

    # Check if the file already exists. If not, take a screenshot
    if not os.path.exists(filepath):
      fut = self.pool.submit(ScreenshotDirective.take_screenshot,
                             url_or_filepath, browser, viewport_width,
                             viewport_height, filepath, screenshot_init_script,
                             interactions, pdf, color_scheme, full_page,
                             context_builder, request_headers, locale,
                             timezone)
      fut.result()

    # Create image and figure nodes
    rel_ss_dirpath = os.path.relpath(ss_dirpath, start=docdir)
    rel_filepath = os.path.join(rel_ss_dirpath, filename).replace(os.sep, '/')

    self.arguments[0] = rel_filepath
    return super().run()


app_threads = {}


def resolve_python_method(import_path: str):
  module_path, method_name = import_path.split(":")
  module = importlib.import_module(module_path)
  method = getattr(module, method_name)
  return method


def setup_apps(app: Sphinx, config: Config):
  """Start the WSGI application threads.

    A new replacement is created for each WSGI app."""
  for wsgi_app_name, wsgi_app_path in config.screenshot_apps.items():
    port = pick_unused_port()
    config.rst_prolog = (
        config.rst_prolog or
        "") + f"\n.. |{wsgi_app_name}| replace:: http://localhost:{port}\n"
    app_builder = resolve_python_method(wsgi_app_path)
    wsgi_app = app_builder(app)
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
      'screenshot_default_viewport_width',
      1280,
      'env',
      description="The default width for screenshots")
  app.add_config_value(
      'screenshot_default_viewport_height',
      960,
      'env',
      description="The default height for screenshots")
  app.add_config_value(
      'screenshot_default_browser',
      'chromium',
      'env',
      description="The default browser for screenshots")
  app.add_config_value(
      'screenshot_default_full_page',
      False,
      'env',
      description="Whether to take full page screenshots")
  app.add_config_value(
      'screenshot_default_color_scheme',
      'null',
      'env',
      description="The default color scheme for screenshots")
  app.add_config_value(
      'screenshot_contexts', {},
      'env',
      types=[dict[str, str]],
      description="A dict of paths to Playwright context build methods")
  app.add_config_value(
      'screenshot_default_headers', {},
      'env',
      description="The default headers to pass in requests")
  app.add_config_value(
      'screenshot_default_locale',
      None,
      'env',
      description="The default locale in requests")
  app.add_config_value(
      'screenshot_default_timezone',
      None,
      'env',
      description="The default timezone in requests")
  app.add_config_value(
      'screenshot_apps', {},
      'env',
      types=[dict[str, str]],
      description="A dict of WSGI apps")
  app.connect('config-inited', setup_apps)
  app.connect('build-finished', teardown_apps)
  return {
      'version': importlib.metadata.version('sphinxcontrib-screenshot'),
      'parallel_read_safe': True,
      'parallel_write_safe': True,
  }
