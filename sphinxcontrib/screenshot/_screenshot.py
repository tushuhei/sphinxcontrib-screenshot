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

import math
import os
import typing

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst.directives.images import Figure
from playwright._impl._helper import ColorScheme
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ._common import (ContextBuilder, _hash_filename, _navigate,
                      _PlaywrightDirective, _prepare_context,
                      _run_interactions, parse_expected_status_codes,
                      parse_locator_padding)


class ScreenshotDirective(_PlaywrightDirective, Figure):
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

  You can crop the screenshot to a single element on the page using a
  Playwright selector. The image is bounded by the element's bounding box.

  ```rst
  .. screenshot:: http://www.example.com
    :locator: #content
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
      **_PlaywrightDirective.common_option_spec,
      'pdf': directives.flag,
      'color-scheme': str,
      'full-page': directives.flag,
      'locator': str,
      'locator-padding': parse_locator_padding,
  }

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
                      location: typing.Optional[str] = None,
                      timeout: int = 10000,
                      locator: typing.Optional[str] = None,
                      locator_padding: typing.Tuple[int, int, int,
                                                    int] = (0, 0, 0, 0)):
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
      full_page (bool): Take a full page screenshot. Ignored when ``locator``
        is set (the locator's bounding box wins).
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
      locator (str, optional): Playwright selector. When set, the screenshot
        is cropped to the bounding box of the matched element rather than
        capturing the viewport. The selector must match a single element
        (Playwright strict mode). PDF generation, when enabled, remains
        page-level since Playwright's PDF API has no per-element variant.
      locator_padding (tuple): ``(top, right, bottom, left)`` CSS pixels
        added on each side of the locator's bounding box to give the matched
        element some breathing room. Only meaningful when ``locator`` is set;
        clamped to the viewport.
    """
    if expected_status_codes is None:
      expected_status_codes = "200,302"

    valid_codes = parse_expected_status_codes(expected_status_codes)

    with sync_playwright() as playwright:
      browser, context = _prepare_context(playwright, browser_name, url,
                                          color_scheme, locale, timezone,
                                          device_scale_factor, context_builder)

      page = context.new_page()
      page.set_default_timeout(timeout)
      page.set_viewport_size({
          'width': viewport_width,
          'height': viewport_height
      })

      try:
        if init_script:
          page.add_init_script(init_script)
        page.set_extra_http_headers(headers)
        _navigate(page, url, valid_codes, expected_status_codes, location)
        _run_interactions(page, interactions)
      except PlaywrightTimeoutError:
        raise RuntimeError('Timeout error occurred at %s in executing\n%s' %
                           (url, interactions))
      if locator:
        if any(locator_padding):
          # Compute the bbox manually so we can widen it by locator_padding
          # before clipping. ``page.screenshot(clip=...)`` works in viewport
          # coordinates, so scroll the element in first — Locator.screenshot
          # does this implicitly but the manual path doesn't. Floor x/y and
          # ceil w/h so the bounding box always encloses the element (the
          # opposite would shave off sub-pixel edges); clamp to the viewport
          # since Playwright rejects clip rectangles outside the page area.
          pad_top, pad_right, pad_bottom, pad_left = locator_padding
          el = page.locator(locator)
          el.scroll_into_view_if_needed(timeout=timeout)
          bbox = el.bounding_box(timeout=timeout)
          if bbox is None:
            raise RuntimeError(
                f'Locator {locator!r} did not match a visible element on '
                f'{url}.')
          x = max(0, math.floor(bbox['x']) - pad_left)
          y = max(0, math.floor(bbox['y']) - pad_top)
          w = min(
              math.ceil(bbox['x'] + bbox['width']) + pad_right - x,
              viewport_width - x)
          h = min(
              math.ceil(bbox['y'] + bbox['height']) + pad_bottom - y,
              viewport_height - y)
          if w <= 0 or h <= 0:
            raise RuntimeError(
                f'Locator {locator!r} bounding box ({bbox}) is outside '
                f'the viewport ({viewport_width}x{viewport_height}).')
          page.screenshot(
              path=filepath, clip={
                  'x': x,
                  'y': y,
                  'width': w,
                  'height': h
              })
        else:
          page.locator(locator).screenshot(path=filepath)
      else:
        page.screenshot(path=filepath, full_page=full_page)
      if generate_pdf:
        page.emulate_media(media='screen')
        root, _ = os.path.splitext(filepath)
        page.pdf(
            width=f'{viewport_width}px',
            height=f'{viewport_height}px',
            path=root + '.pdf')
      page.close()
      browser.close()

  def _generate_single_screenshot(
      self,
      color_scheme: typing.Optional[str] = None
  ) -> typing.Sequence[nodes.Node]:
    """Generate a single screenshot and return the docutils nodes."""
    screenshot_init_script: str = self.env.config.screenshot_init_script or ''
    docdir = os.path.dirname(self.env.doc2path(self.env.docname))

    ss_dirpath = os.path.join(self.env.app.outdir, '_static', 'screenshots')
    os.makedirs(ss_dirpath, exist_ok=True)

    raw_path = self.arguments[0]
    url_or_filepath = self._resolve_url(raw_path)

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
    timeout = self.options.get('timeout',
                               self.env.config.screenshot_default_timeout)
    locator = self.options.get('locator', '')
    # Option_spec runs values through parse_locator_padding so per-directive
    # values are already a tuple; the config default is read raw and may be
    # an int, a string, or a sequence — normalize through the same parser.
    locator_padding = self.options.get(
        'locator-padding',
        parse_locator_padding(
            self.env.config.screenshot_default_locator_padding))
    request_headers = {**self.env.config.screenshot_default_headers}
    if headers:
      for header in headers.strip().split("\n"):
        name, value = header.split(" ", 1)
        request_headers[name] = value

    filename = _hash_filename([
        raw_path,
        browser,
        viewport_height,
        viewport_width,
        color_scheme,
        context,
        interactions,
        full_page,
        device_scale_factor,
        status_code,
        locator,
        locator_padding,
        screenshot_init_script,
        locale,
        timezone,
        request_headers,
    ], '.png')
    filepath = os.path.join(ss_dirpath, filename)

    context_builder = self._resolve_context_builder(context)

    if not os.path.exists(filepath):
      fut = self.pool.submit(
          ScreenshotDirective.take_screenshot, url_or_filepath, browser,
          viewport_width, viewport_height, filepath,
          screenshot_init_script, interactions, pdf,
          typing.cast(ColorScheme, color_scheme), full_page, context_builder,
          request_headers, device_scale_factor, locale, timezone, status_code,
          self.env.docname, timeout, locator or None, locator_padding)
      fut.result()

    rel_ss_dirpath = os.path.relpath(ss_dirpath, start=docdir)
    rel_filepath = os.path.join(rel_ss_dirpath, filename).replace(os.sep, '/')

    self.arguments[0] = rel_filepath
    return super().run()

  def run(self) -> typing.Sequence[nodes.Node]:
    """Process the screenshot directive and generate appropriate nodes."""
    color_scheme = self.options.get(
        'color-scheme', self.env.config.screenshot_default_color_scheme)

    if color_scheme == 'auto':
      return self._generate_dual_theme(self._generate_single_screenshot)
    return self._generate_single_screenshot()
