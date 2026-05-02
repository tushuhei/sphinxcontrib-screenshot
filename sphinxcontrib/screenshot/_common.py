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
"""Internal helpers and base directive shared by screenshot and screencast."""

import hashlib
import importlib
import json
import os
import typing
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from docutils import nodes
from docutils.parsers.rst import directives
from playwright._impl._helper import ColorScheme
from playwright.sync_api import Browser, BrowserContext
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from sphinx.util import logging as sphinx_logging
from sphinx.util.docutils import SphinxDirective

logger = sphinx_logging.getLogger(__name__)

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


def parse_locator_padding(
    value: typing.Union[str, int, typing.Sequence[int], None]
) -> typing.Tuple[int, int, int, int]:
  """Normalize a CSS-padding-shorthand value to ``(top, right, bottom, left)``.

  Accepts:
    - ``None`` or empty string — zero on all sides.
    - ``int`` — uniform on all sides.
    - sequence of 1–4 ``int``\\ s — same expansion as the string form.
    - whitespace-separated string of 1–4 non-negative integers, following the
      CSS ``padding`` shorthand:

        - 1 value: all four sides
        - 2 values: ``top/bottom``, ``right/left``
        - 3 values: ``top``, ``right/left``, ``bottom``
        - 4 values: ``top``, ``right``, ``bottom``, ``left``
  """
  if value is None:
    parts: typing.List[int] = [0]
  elif isinstance(value, int):
    parts = [value]
  elif isinstance(value, str):
    stripped = value.strip()
    parts = [int(p) for p in stripped.split()] if stripped else [0]
  else:
    parts = [int(v) for v in value]

  for n in parts:
    if n < 0:
      raise ValueError(
          f'locator-padding values must be non-negative, got {n!r}.')

  if len(parts) == 1:
    return (parts[0], parts[0], parts[0], parts[0])
  if len(parts) == 2:
    return (parts[0], parts[1], parts[0], parts[1])
  if len(parts) == 3:
    return (parts[0], parts[1], parts[2], parts[1])
  if len(parts) == 4:
    return (parts[0], parts[1], parts[2], parts[3])

  raise ValueError('locator-padding accepts 1, 2, 3, or 4 values (CSS padding '
                   f'shorthand), got {len(parts)}.')


def resolve_python_method(import_path: str):
  module_path, method_name = import_path.split(":")
  module = importlib.import_module(module_path)
  method = getattr(module, method_name)
  return method


def _hash_filename(parts: typing.Iterable[typing.Any], extension: str) -> str:
  """Build a deterministic ``<md5><extension>`` filename from arbitrary parts.

  Each part is stringified; dicts/lists are JSON-serialized with sorted keys
  so config dicts (e.g. headers) hash identically across runs.
  """

  def _normalize(value):
    if isinstance(value, (dict, list, tuple)):
      return json.dumps(value, sort_keys=True, default=str)
    return '' if value is None else str(value)

  payload = '_'.join(_normalize(p) for p in parts)
  return hashlib.md5(payload.encode()).hexdigest() + extension


def _invoke_context_builder(
    context_builder: typing.Callable, browser: Browser, url: str,
    color_scheme: ColorScheme,
    record_video_dir: typing.Optional[str]) -> BrowserContext:
  """Call a user-provided context builder with the right signature.

  For screenshot (record_video_dir is None), invoke the builder in 3-args
  mode for full backwards compatibility. For screencast, pass
  record_video_dir as a kwarg — the builder must accept it. The screencast
  directive validates this in its run() before reaching here, so the kwarg
  call is expected to succeed.
  """
  if record_video_dir is None:
    return context_builder(browser, url, color_scheme)
  return context_builder(
      browser, url, color_scheme, record_video_dir=record_video_dir)


def _prepare_context(
    playwright,
    browser_name: str,
    url: str,
    color_scheme: ColorScheme,
    locale: typing.Optional[str],
    timezone: typing.Optional[str],
    device_scale_factor: int,
    context_builder: ContextBuilder,
    record_video_dir: typing.Optional[str] = None,
    viewport_width: typing.Optional[int] = None,
    viewport_height: typing.Optional[int] = None,
) -> typing.Tuple[Browser, BrowserContext]:
  """Launch a browser and create a context, optionally via a custom builder."""
  browser: Browser = getattr(playwright, browser_name).launch()

  if context_builder:
    try:
      context = _invoke_context_builder(context_builder, browser, url,
                                        color_scheme, record_video_dir)
    except PlaywrightTimeoutError:
      raise RuntimeError(
          'Timeout error occurred at %s in executing py init script %s' %
          (url, context_builder.__name__))
  else:
    new_context_kwargs: typing.Dict[str, typing.Any] = dict(
        color_scheme=color_scheme,
        locale=locale,
        timezone_id=timezone,
        device_scale_factor=device_scale_factor)
    if record_video_dir is not None:
      new_context_kwargs['record_video_dir'] = record_video_dir
      # When recording, the video size is fixed at context creation and
      # cannot be changed by a later page.set_viewport_size(). Pin both
      # viewport and video size to the requested viewport so locator-based
      # cropping (computed in viewport coordinates) operates on a video
      # frame of matching dimensions.
      if viewport_width is not None and viewport_height is not None:
        new_context_kwargs['viewport'] = {
            'width': viewport_width,
            'height': viewport_height,
        }
        new_context_kwargs['record_video_size'] = {
            'width': viewport_width,
            'height': viewport_height,
        }
    context = browser.new_context(**new_context_kwargs)

  return browser, context


def _navigate(page, url: str, valid_codes: typing.List[int],
              expected_status_codes: str,
              location: typing.Optional[str]) -> None:
  """Navigate to URL, warn on unexpected status, wait for networkidle."""
  response = page.goto(url)

  if response and response.status not in valid_codes:
    logger.warning(
        f'Page {url} returned status code {response.status}, '
        f'expected one of: {expected_status_codes}',
        type='screenshot',
        subtype='status_code',
        location=location)

  page.wait_for_load_state('networkidle')


def _run_interactions(page, interactions: str) -> None:
  """Run JS interactions and wait for networkidle.

  Interactions are wrapped in an async IIFE so users can use ``await`` at the
  top level (e.g. ``await new Promise(r => setTimeout(r, 500))``). Playwright
  awaits the returned Promise, so synchronous code keeps working unchanged.
  """
  if interactions:
    page.evaluate(f'(async () => {{ {interactions} }})()')
    page.wait_for_load_state('networkidle')


class _PlaywrightDirective(SphinxDirective):
  """Base class shared by Playwright-driven directives.

  Holds the option spec common to all directives that drive Playwright,
  the worker pool, and the helpers that resolve URLs and custom context
  builders.
  """

  common_option_spec: typing.Dict[str, typing.Callable[[str], typing.Any]] = {
      'browser': str,
      'viewport-height': directives.positive_int,
      'viewport-width': directives.positive_int,
      'interactions': str,
      'context': str,
      'headers': directives.unchanged,
      'locale': str,
      'timezone': str,
      'device-scale-factor': directives.positive_int,
      'status-code': str,
      'timeout': directives.positive_int,
  }
  pool = ThreadPoolExecutor()

  def _evaluate_substitutions(self, text: str) -> str:
    substitutions = self.state.document.substitution_defs
    for key, value in substitutions.items():
      text = text.replace(f"|{key}|", value.astext())
    return text

  def _resolve_url(self, raw_path: str) -> str:
    """Resolve a raw URL/path argument to an absolute URL.

    Substitutions are evaluated. Root-relative and document-relative
    file paths are converted to ``file://`` URLs. Only http/https/file
    schemes are accepted.
    """
    url_or_filepath = self._evaluate_substitutions(raw_path)
    parsed = urlparse(url_or_filepath)
    scheme = parsed.scheme

    # On Windows, drive letters (e.g., C:) are misidentified as schemes.
    if os.name == 'nt' and len(scheme) == 1 and scheme.isalpha():
      scheme = ''

    if scheme in {'http', 'https'}:
      return url_or_filepath

    if scheme == 'file' or scheme == '':
      if scheme == 'file':
        # url2pathname handles file:///C:/foo -> C:\foo
        path_str = urllib.request.url2pathname(parsed.path)
        if parsed.netloc:
          if os.name == 'nt' and len(
              parsed.netloc) == 2 and parsed.netloc[1] == ':':
            target_path = Path(parsed.netloc + path_str)
          else:
            prefix = '\\\\' if os.name == 'nt' else ''
            target_path = Path(prefix + parsed.netloc + path_str)
        else:
          target_path = Path(path_str)
      else:
        if url_or_filepath.startswith('/'):
          target_path = Path(self.env.srcdir) / url_or_filepath.lstrip('/')
        else:
          docdir = Path(self.env.doc2path(self.env.docname)).parent
          target_path = docdir / url_or_filepath

      try:
        # Use realpath and commonpath for robust containment check.
        # This handles symlinks and is case-insensitive where appropriate.
        abs_target = os.path.realpath(str(target_path))
        abs_srcdir = os.path.realpath(str(self.env.srcdir))

        if os.path.commonpath(
            [os.path.normcase(abs_srcdir),
             os.path.normcase(abs_target)]) != os.path.normcase(abs_srcdir):
          raise RuntimeError(
              f'Security Error: Access to {url_or_filepath} is restricted '
              f'to the Sphinx source directory ({abs_srcdir}).')

        return Path(abs_target).as_uri()
      except (ValueError, RuntimeError, OSError) as e:
        if isinstance(e, RuntimeError) and 'Security Error' in str(e):
          raise
        raise RuntimeError(
            f'Security Error: Access to {url_or_filepath} is restricted '
            f'to the Sphinx source directory ({self.env.srcdir}).')

    raise RuntimeError(f'Invalid URL: {url_or_filepath}')

  def _resolve_context_builder(self, context_name: str) -> ContextBuilder:
    """Resolve a context name to a callable, or None if unset."""
    if not context_name:
      return None
    context_builder_path = self.config.screenshot_contexts[context_name]
    return resolve_python_method(context_builder_path)

  def _add_css_class_to_nodes(
      self,
      nodes_list: typing.Sequence[nodes.Node],
      css_class: str,
      inner_types: typing.Tuple[typing.Type[nodes.Element],
                                ...] = (nodes.image,),
  ) -> typing.Sequence[nodes.Node]:
    """Add a CSS class to figure nodes and their inner media element.

    ``inner_types`` lists the inner element types to also tag (e.g.
    ``nodes.image`` for screenshot, the screencast node for screencast).
    Tagging both the figure and its inner element keeps the existing
    behaviour and is robust against custom CSS that targets either.
    """
    for node in nodes_list:
      if isinstance(node, nodes.figure):
        node['classes'] = node.get('classes', []) + [css_class]
        for child in node.children:
          if isinstance(child, inner_types):
            child['classes'] = child.get('classes', []) + [css_class]
      elif isinstance(node, inner_types):
        node['classes'] = node.get('classes', []) + [css_class]
    return nodes_list

  def _generate_dual_theme(
      self,
      generator: typing.Callable[..., typing.Sequence[nodes.Node]],
      inner_types: typing.Tuple[type, ...] = (nodes.image,),
  ) -> typing.Sequence[nodes.Node]:
    """Run ``generator`` per theme and tag with ``only-light``/``only-dark``.

    The directive's ``arguments`` and ``options`` are saved before each call
    and restored after, since the generator may rewrite them (e.g. to inject
    a relative file path into ``arguments[0]``).
    """
    original_arguments = self.arguments[:]
    original_options = self.options.copy()

    light_nodes = generator(color_scheme='light')
    light_nodes = self._add_css_class_to_nodes(light_nodes, 'only-light',
                                               inner_types)

    self.arguments = original_arguments[:]
    self.options = original_options.copy()

    dark_nodes = generator(color_scheme='dark')
    dark_nodes = self._add_css_class_to_nodes(dark_nodes, 'only-dark',
                                              inner_types)

    self.arguments = original_arguments
    self.options = original_options

    return [*light_nodes, *dark_nodes]
