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
from pathlib import Path
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
from sphinx.util import logging as sphinx_logging
from sphinx.util.docutils import SphinxDirective
from sphinx.util.fileutil import copy_asset

logger = sphinx_logging.getLogger(__name__)

Meta = typing.TypedDict('Meta', {
    'version': str,
    'parallel_read_safe': bool,
    'parallel_write_safe': bool
})

ContextBuilder = typing.Optional[typing.Callable[[Browser, str, str],
                                                 BrowserContext]]


def parse_expected_status_codes(codes_str: str) -> typing.List[int]:
  """Parse a comma-separated string of HTTP status codes into a list.

  Args:
    codes_str: Comma-separated status codes like "200, 201, 302".

  Returns:
    List of integer status codes.
  """
  return [int(code.strip()) for code in codes_str.split(',')]


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

  You can automatically generate both light and dark mode screenshots by
  setting `:color-scheme: auto`. This creates two screenshots with appropriate
  CSS classes (`only-light` and `only-dark`) that are automatically shown
  based on the user's theme preference.

  ```rst
  .. screenshot:: http://www.example.com
    :color-scheme: auto
  ```

  You can take a screenshot of a local file using a root-relative path.

  ```rst
  .. screenshot:: /static/example.html
  ```

  Or you can use a document-relative path.

  ```rst
  .. screenshot:: ./example.html
  ```

  The `file://` protocol is also supported.

  ```rst
   .. screenshot:: file:///path/to/your/file.html
   ```
  """

  required_arguments = 1  # URL
  option_spec = {
      **(Figure.option_spec or {}),
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
      'device-scale-factor': directives.positive_int,
      'status-code': str,
  }
  pool = ThreadPoolExecutor()

  @staticmethod
  def take_screenshot(url: str,
                      browser_name: str,
                      viewport_width: int,
                      viewport_height: int,
                      filepath: str,
                      init_script: str,
                      interactions: str,
                      generate_pdf: bool,
                      color_scheme: ColorScheme,
                      full_page: bool,
                      context_builder: ContextBuilder,
                      headers: dict,
                      device_scale_factor: int,
                      locale: typing.Optional[str],
                      timezone: typing.Optional[str],
                      expected_status_codes: typing.Optional[str] = None,
                      location: typing.Optional[str] = None):
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
      device_scale_factor (int): The device scale factor for the screenshot.
        This can be thought of as DPR (device pixel ratio).
      locale (str, optional): User locale for the request.
      timezone (str, optional): User timezone for the request.
      expected_status_codes (str, optional): Expected HTTP status codes.
        Format: comma-separated list of codes (e.g., "200,201,302").
        Defaults to "200,302" (OK and redirect).
      location (str, optional): Document location for warning messages.
    """
    if expected_status_codes is None:
      expected_status_codes = "200,302"

    valid_codes = parse_expected_status_codes(expected_status_codes)

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
            color_scheme=color_scheme,
            locale=locale,
            timezone_id=timezone,
            device_scale_factor=device_scale_factor)

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
        response = page.goto(url)

        if response and response.status not in valid_codes:
          logger.warning(
              f'Page {url} returned status code {response.status}, '
              f'expected one of: {expected_status_codes}',
              type='screenshot',
              subtype='status_code',
              location=location)

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

  def _add_css_class_to_nodes(self, nodes_list: typing.Sequence[nodes.Node],
                              css_class: str) -> typing.Sequence[nodes.Node]:
    """Add a CSS class to image or figure nodes.

    Args:
      nodes_list: List of docutils nodes to modify.
      css_class: CSS class name to add (e.g., 'only-light' or 'only-dark').

    Returns:
      The modified list of nodes.
    """
    for node in nodes_list:
      if isinstance(node, (nodes.image, nodes.figure)):
        existing_classes: list = node.get('classes', [])
        node['classes'] = existing_classes + [css_class]
      if isinstance(node, nodes.figure):
        for child in node.children:
          if isinstance(child, nodes.image):
            existing_classes = child.get('classes', [])
            child['classes'] = existing_classes + [css_class]
    return nodes_list

  def _generate_single_screenshot(
      self,
      color_scheme: typing.Optional[str] = None
  ) -> typing.Sequence[nodes.Node]:
    """Generate a single screenshot and return the docutils nodes.

    Args:
      color_scheme: Optional color scheme to override the directive
        option. Used when generating dual-theme screenshots.

    Returns:
      List of docutils nodes representing the screenshot.
    """
    screenshot_init_script: str = self.env.config.screenshot_init_script or ''
    docdir = os.path.dirname(self.env.doc2path(self.env.docname))

    # Ensure the screenshots directory exists
    ss_dirpath = os.path.join(self.env.app.outdir, '_static', 'screenshots')
    os.makedirs(ss_dirpath, exist_ok=True)

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
      url_or_filepath = "file://" + os.path.normpath(url_or_filepath)

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
    color_scheme = color_scheme or self.options.get(
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
    device_scale_factor = self.options.get(
        'device-scale-factor',
        self.env.config.screenshot_default_device_scale_factor)
    status_code = self.options.get('status-code', None)
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
        str(full_page),
        str(device_scale_factor),
        str(status_code or "")
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
                             interactions, pdf,
                             typing.cast(ColorScheme, color_scheme), full_page,
                             context_builder, request_headers,
                             device_scale_factor, locale, timezone,
                             status_code, self.env.docname)
      fut.result()

    rel_ss_dirpath = os.path.relpath(ss_dirpath, start=docdir)
    rel_filepath = os.path.join(rel_ss_dirpath, filename).replace(os.sep, '/')

    self.arguments[0] = rel_filepath
    return super().run()

  def _generate_dual_theme_screenshots(self) -> typing.Sequence[nodes.Node]:
    """Generate two screenshots (light and dark mode) with CSS classes.

    Returns:
      List of docutils nodes containing both light and dark mode screenshots.
    """
    original_arguments = self.arguments[:]
    original_options = self.options.copy()

    light_nodes = self._generate_single_screenshot(color_scheme='light')
    light_nodes = self._add_css_class_to_nodes(light_nodes, 'only-light')

    self.arguments = original_arguments[:]
    self.options = original_options.copy()

    dark_nodes = self._generate_single_screenshot(color_scheme='dark')
    dark_nodes = self._add_css_class_to_nodes(dark_nodes, 'only-dark')

    self.arguments = original_arguments
    self.options = original_options

    return list(light_nodes) + list(dark_nodes)

  def run(self) -> typing.Sequence[nodes.Node]:
    """Process the screenshot directive and generate appropriate nodes.

    Returns:
      List of docutils nodes. If color-scheme is 'auto', returns two sets
      of nodes (one for light mode, one for dark mode). Otherwise returns
      a single screenshot node.
    """
    color_scheme = self.options.get(
        'color-scheme', self.env.config.screenshot_default_color_scheme)

    if color_scheme == 'auto':
      return self._generate_dual_theme_screenshots()
    else:
      return self._generate_single_screenshot()


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


def copy_static_files(app: Sphinx, exception: typing.Optional[Exception]):
  """Copy static CSS files from the extension to the build output directory.

  This function is called during the build-finished event to copy the
  screenshot-theme.css file to the output directory.

  Args:
    app: The Sphinx application instance.
    exception: Exception that occurred during build, if any.
  """
  if exception is None and app.builder.format == 'html':
    static_source_dir = Path(__file__).parent / 'static'
    static_dest_dir = Path(app.outdir) / '_static' / 'sphinxcontrib-screenshot'
    static_dest_dir.mkdir(parents=True, exist_ok=True)

    css_source = str(static_source_dir / 'screenshot-theme.css')
    css_dest = str(static_dest_dir)
    copy_asset(css_source, css_dest)


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
      description="The default color scheme for screenshots. " +
      "Use 'auto' to generate both light and dark mode screenshots")
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
      'screenshot_default_device_scale_factor',
      1,
      'env',
      description="The default device scale factor " +
      "a.k.a. DPR (device pixel ratio)")
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
  app.connect('build-finished', copy_static_files)
  app.add_css_file('sphinxcontrib-screenshot/screenshot-theme.css')
  return {
      'version': importlib.metadata.version('sphinxcontrib-screenshot'),
      'parallel_read_safe': True,
      'parallel_write_safe': True,
  }
