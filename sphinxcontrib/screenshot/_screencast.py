# Copyright 2026 Google LLC
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

import inspect
import math
import os
import shutil
import tempfile
import time
import typing

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst.directives.images import Figure
from playwright._impl._helper import ColorScheme
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from sphinx.util import logging as sphinx_logging

from ._common import (ContextBuilder, _hash_filename, _navigate,
                      _PlaywrightDirective, _prepare_context,
                      _run_interactions, parse_expected_status_codes,
                      parse_locator_padding)
from ._ffmpeg import _postprocess_video, _require_ffmpeg

logger = sphinx_logging.getLogger(__name__)


class screencast(nodes.General, nodes.Element):
  """Docutils node rendered as a bare ``<video>`` element in HTML.

  The surrounding ``<figure>`` and ``<figcaption>`` are produced by the
  parent ``nodes.figure`` and ``nodes.caption`` nodes that the directive
  builds, so this node only emits the inner media element.
  """


def visit_screencast_html(self, node: screencast) -> None:
  video_attrs = f'src="{self.attval(node["src"])}"'
  for flag in ('controls', 'autoplay', 'loop', 'muted'):
    if node.get(flag):
      video_attrs += f' {flag}'
  if node.get('poster'):
    video_attrs += f' poster="{self.attval(node["poster"])}"'
  classes = node.get('classes')
  if classes:
    video_attrs += f' class="{self.attval(" ".join(classes))}"'
  self.body.append(f'<video {video_attrs}></video>\n')


def depart_screencast_html(self, node: screencast) -> None:
  pass


def visit_screencast_skip(self, node: screencast) -> None:
  """Fallback for non-HTML builders: silently skip the node so cached
  doctrees (potentially containing a screencast node from a prior HTML build)
  don't crash a subsequent text/latex/etc. build."""
  raise nodes.SkipNode


class ScreencastDirective(_PlaywrightDirective, Figure):
  """Sphinx Screencast Directive.

  Records a WebM video of a webpage using Playwright and embeds it as an
  HTML5 ``<video>`` tag inside a ``<figure>``. The directive body is
  parsed as the figure caption (rich reST), mirroring
  :rst:dir:`screenshot`. Page interactions go through the
  ``:interactions:`` option.

  ```rst
  .. screencast:: http://www.example.com
     :interactions:
       document.querySelector('button').click();
       await new Promise(r => setTimeout(r, 1000));

     A *short* caption with reST formatting.
  ```

  All options of :rst:dir:`screenshot` related to the page setup are
  supported (browser, viewport, locale, timezone, headers, context, etc.)
  except those tied to still images (``pdf``, ``full-page``,
  ``color-scheme``).

  Video-specific options:

  - ``loop`` / ``autoplay`` / ``muted`` / ``controls``: HTML5 ``<video>``
    boolean attributes. ``autoplay`` without ``muted`` is rejected by most
    browsers, so ``muted`` is forced (with a warning) when ``autoplay`` is
    set.
  - ``poster``: still image displayed before playback. Accepts a URL/path
    (explicit), the keyword ``auto-start`` (or empty value: screenshot
    taken before interactions), or ``auto-end`` (screenshot taken after
    interactions). The explicit form is also used as the fallback for
    non-HTML builders.
  """

  required_arguments = 1
  option_spec = {
      **(Figure.option_spec or {}),
      **_PlaywrightDirective.common_option_spec,
      'loop': directives.flag,
      'autoplay': directives.flag,
      'muted': directives.flag,
      'controls': directives.flag,
      'poster': directives.unchanged,
      'trim-start': directives.unchanged,
      'locator': str,
      'locator-padding': parse_locator_padding,
      'color-scheme': str,
  }

  @staticmethod
  def take_screencast(url: str,
                      browser_name: str,
                      viewport_width: int,
                      viewport_height: int,
                      filepath: str,
                      init_script: str,
                      interactions: str,
                      context_builder: ContextBuilder,
                      headers: dict,
                      device_scale_factor: int,
                      locale: typing.Optional[str],
                      timezone: typing.Optional[str],
                      poster_when: typing.Optional[str] = None,
                      trim_start: typing.Optional[float] = None,
                      trim_auto: bool = False,
                      locator: typing.Optional[str] = None,
                      locator_padding: typing.Tuple[int, int, int,
                                                    int] = (0, 0, 0, 0),
                      color_scheme: ColorScheme = 'null',
                      expected_status_codes: typing.Optional[str] = None,
                      location: typing.Optional[str] = None,
                      timeout: int = 10000):
    """Records a WebM screencast of a webpage with Playwright.

    The recording covers `goto -> networkidle -> interactions -> networkidle`.
    To capture animations after a click, the user must keep the page busy in
    the interactions JS (e.g. `await new Promise(r => setTimeout(r, 1000))`).

    ``poster_when`` toggles automatic poster generation. ``'start'`` takes
    a PNG screenshot right after page load and before interactions (matches
    the first visible frame when ``trim_start``/``trim_auto`` is also set);
    ``'end'`` takes it after interactions; ``None`` skips poster generation.
    The PNG is saved next to ``filepath`` (with a .png extension).

    ``trim_start`` (in seconds) trims the beginning of the recording.
    ``trim_auto=True`` measures the time between context creation and the
    end of the page load and uses it as the trim offset, eliminating the
    initial about:blank flash. Mutually exclusive with ``trim_start``.

    ``locator`` is a Playwright selector. When set, the video is cropped to
    the bounding box of the matched element via ffmpeg post-processing.
    ``locator_padding`` is a ``(top, right, bottom, left)`` tuple of CSS
    pixels added to the crop box on the matching side, mirroring CSS's
    ``padding`` shorthand. The box is clamped to the viewport.
    """
    if expected_status_codes is None:
      expected_status_codes = "200,302"

    valid_codes = parse_expected_status_codes(expected_status_codes)
    poster_path = os.path.splitext(filepath)[0] + '.png'
    success = False
    try:
      with (tempfile.TemporaryDirectory() as tmp_dir, sync_playwright() as
            playwright):
        browser, context = _prepare_context(
            playwright,
            browser_name,
            url,
            color_scheme,
            locale,
            timezone,
            device_scale_factor,
            context_builder,
            record_video_dir=tmp_dir,
            viewport_width=viewport_width,
            viewport_height=viewport_height)
        # Capture timer right after context creation so auto-trim brackets
        # the actual video — placing it earlier would also count the browser
        # launch overhead (100–500 ms) and trim into real content.
        t_context_start = time.monotonic()

        page = context.new_page()
        page.set_default_timeout(timeout)
        page.set_viewport_size({
            'width': viewport_width,
            'height': viewport_height
        })

        crop_box: typing.Optional[typing.Tuple[int, int, int, int]] = None
        auto_trim_offset: typing.Optional[float] = None

        try:
          if init_script:
            page.add_init_script(init_script)
          page.set_extra_http_headers(headers)
          _navigate(page, url, valid_codes, expected_status_codes, location)

          if trim_auto:
            auto_trim_offset = time.monotonic() - t_context_start

          if poster_when == 'start':
            page.screenshot(path=poster_path)

          _run_interactions(page, interactions)

          if poster_when == 'end':
            page.screenshot(path=poster_path)

          if locator:
            bbox = page.locator(locator).bounding_box(timeout=timeout)
            if bbox is None:
              raise RuntimeError(
                  f'Locator {locator!r} did not match a visible element on '
                  f'{url}.')

            # Floor x/y and ceil w/h so the bounding box always encloses the
            # element (the opposite would shave off sub-pixel edges). Clamp
            # to the viewport since ffmpeg crop coordinates outside the
            # frame fail with a cryptic message. ``locator_padding`` widens
            # the box per side (CSS shorthand) before clamping.
            pad_top, pad_right, pad_bottom, pad_left = locator_padding
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

            crop_box = (x, y, w, h)
        except PlaywrightTimeoutError as e:
          raise RuntimeError('Timeout error occurred at %s in executing\n%s' %
                             (url, interactions)) from e

        # Keep a reference to the video before closing — page.close() and
        # context.close() are required to flush the .webm to disk before
        # save_as can read it.
        video = page.video
        page.close()
        context.close()
        if video is None:
          raise RuntimeError(
              'Playwright did not record a video. The custom context '
              'builder likely did not pass record_video_dir to '
              'browser.new_context().')

        video.save_as(filepath)
        browser.close()

        effective_trim = auto_trim_offset if trim_auto else trim_start
        if (effective_trim and effective_trim > 0) or crop_box:
          ffmpeg = _require_ffmpeg(
              'screencast trim-start/locator post-processing')
          intermediate = os.path.join(tmp_dir, 'postprocessed.webm')
          _postprocess_video(
              ffmpeg,
              filepath,
              intermediate,
              trim_start=effective_trim
              if effective_trim and effective_trim > 0 else None,
              crop=crop_box)
          # shutil.move falls back to copy+delete across filesystems;
          # os.replace would raise EXDEV when tmp_dir (often tmpfs) and
          # the build directory live on different devices.
          shutil.move(intermediate, filepath)

      success = True
    finally:
      if not success:
        # Remove any partial output left behind so the next build retries
        # from scratch instead of returning a stale or half-written file.
        for path in (filepath, poster_path):
          if os.path.exists(path):
            try:
              os.remove(path)
            except OSError:
              pass

  def _parse_poster(self) -> typing.Tuple[str, str]:
    """Resolve ``:poster:`` and the config default into ``(mode, value)``.

    Bare ``:poster:`` is normalized to ``'auto-start'`` so the option and
    the (always-non-empty) config default share the same dispatch.
    """
    poster_raw: typing.Optional[str]
    if 'poster' in self.options:
      poster_raw = (self.options['poster'] or '').strip() or 'auto-start'
    else:
      config_poster = self.env.config.screencast_default_poster
      poster_raw = (config_poster.strip() or None) if config_poster else None

    if poster_raw is None:
      return 'none', ''
    if poster_raw == 'auto-start':
      return 'auto-start', ''
    if poster_raw == 'auto-end':
      return 'auto-end', ''
    return 'explicit', poster_raw

  def run(self) -> typing.Sequence[nodes.Node]:
    """Process the screencast directive and return a figure node.

    The figure wraps a ``screencast`` node (rendered as ``<video>``) and
    its caption parsed from the directive body, mirroring the structure
    that :rst:dir:`screenshot` inherits from
    :class:`docutils.parsers.rst.directives.images.Figure`.

    For non-HTML builders, falls back to the poster image if provided,
    otherwise emits a warning and skips the directive. When
    ``:color-scheme: auto`` is set, generates two videos (light + dark)
    tagged with ``only-light`` / ``only-dark`` CSS classes.
    """
    poster_mode, poster_value = self._parse_poster()

    builder_format = self.env.app.builder.format
    if builder_format != 'html':
      if poster_mode == 'explicit':
        # Reuse the figure machinery so the caption (parsed from the
        # body) renders alongside the poster image in non-HTML builders
        # too. Replace the URL argument with the poster path and let
        # Figure.run() build the figure+caption tree with an image node.
        self.arguments[0] = poster_value
        return Figure.run(self)
      logger.warning(
          'screencast directive skipped: builder %r is not HTML and no '
          'explicit :poster: URL was provided.' % builder_format,
          location=self.env.docname,
          type='screencast')
      return []

    # Browsers reject autoplay without muted — warn once (even in dual mode)
    # whenever autoplay is set, regardless of where the value came from.
    cfg = self.env.config
    autoplay = 'autoplay' in self.options or cfg.screencast_default_autoplay
    muted = 'muted' in self.options or cfg.screencast_default_muted
    if autoplay and not muted:
      logger.warning(
          'screencast: :autoplay: requires :muted: due to browser autoplay '
          'policies. Forcing muted.',
          location=self.env.docname,
          type='screencast')

    color_scheme = self.options.get('color-scheme',
                                    cfg.screenshot_default_color_scheme)
    if color_scheme == 'auto':
      return self._generate_dual_theme(
          self._generate_single_screencast, inner_types=(screencast,))
    return self._generate_single_screencast(color_scheme=color_scheme)

  def _generate_single_screencast(
      self,
      color_scheme: typing.Optional[str] = None
  ) -> typing.Sequence[nodes.Node]:
    """Generate a single screencast and return the docutils nodes."""
    poster_mode, poster_value = self._parse_poster()

    # Bare ``:trim-start:`` is normalized to ``'auto'`` so the option and the
    # config default share the same dispatch.
    trim_raw: typing.Optional[str]
    if 'trim-start' in self.options:
      trim_raw = (self.options['trim-start'] or '').strip() or 'auto'
    else:
      config_trim = self.env.config.screencast_default_trim_start
      if config_trim is None:
        trim_raw = None
      elif isinstance(config_trim, str):
        trim_raw = config_trim.strip() or None
      else:
        trim_raw = str(config_trim)

    trim_value: typing.Optional[float]
    if trim_raw is None:
      trim_mode = 'none'
      trim_value = None
    elif trim_raw == 'auto':
      trim_mode = 'auto'
      trim_value = None
    else:
      trim_mode = 'explicit'
      try:
        trim_value = float(trim_raw)
      except ValueError:
        raise self.error(
            f':trim-start: (or screencast_default_trim_start) must be a '
            f'number of seconds or "auto", got {trim_raw!r}.')

    locator_value: str = self.options.get('locator', '') or ''
    # Option_spec runs values through parse_locator_padding so per-directive
    # values are already a tuple; the config default is read raw and may be
    # an int, a string, or a sequence — normalize through the same parser.
    locator_padding_value: typing.Tuple[int, int, int, int] = self.options.get(
        'locator-padding',
        parse_locator_padding(
            self.env.config.screenshot_default_locator_padding))

    cs = color_scheme or self.options.get(
        'color-scheme', self.env.config.screenshot_default_color_scheme)

    screencast_init_script: str = self.env.config.screenshot_init_script or ''

    sc_dirpath = os.path.join(self.env.app.outdir, '_static', 'screencasts')
    os.makedirs(sc_dirpath, exist_ok=True)

    raw_path = self.arguments[0]
    url_or_filepath = self._resolve_url(raw_path)

    interactions = self.options.get('interactions', '')
    browser = self.options.get('browser',
                               self.env.config.screenshot_default_browser)
    viewport_height = self.options.get(
        'viewport-height', self.env.config.screenshot_default_viewport_height)
    viewport_width = self.options.get(
        'viewport-width', self.env.config.screenshot_default_viewport_width)
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
    request_headers = {**self.env.config.screenshot_default_headers}
    if headers:
      for header in headers.strip().split("\n"):
        name, value = header.split(" ", 1)
        request_headers[name] = value

    cfg = self.env.config
    loop_flag = 'loop' in self.options or cfg.screencast_default_loop
    autoplay_flag = ('autoplay' in self.options or
                     cfg.screencast_default_autoplay)
    muted_flag = 'muted' in self.options or cfg.screencast_default_muted
    controls_flag = ('controls' in self.options or
                     cfg.screencast_default_controls)
    # Force muted whenever autoplay is set; the user-facing warning has
    # already been emitted in run() so each dual generation stays silent.
    if autoplay_flag and not muted_flag:
      muted_flag = True

    filename = _hash_filename([
        raw_path,
        browser,
        viewport_height,
        viewport_width,
        context,
        interactions,
        device_scale_factor,
        status_code,
        loop_flag,
        autoplay_flag,
        muted_flag,
        controls_flag,
        poster_mode,
        poster_value,
        trim_mode,
        trim_value,
        locator_value,
        locator_padding_value,
        cs,
        screencast_init_script,
        locale,
        timezone,
        request_headers,
    ], '.webm')
    filepath = os.path.join(sc_dirpath, filename)

    context_builder = self._resolve_context_builder(context)

    # Detect a 3-args context builder early — recording video requires the
    # builder to accept record_video_dir. Emit an error and skip the directive
    # rather than crashing the whole Sphinx build.
    if context_builder and 'record_video_dir' not in inspect.signature(
        context_builder).parameters:
      logger.error(
          f'screencast: context builder '
          f'{context_builder.__module__}.{context_builder.__name__} must '
          f'accept a record_video_dir parameter. Update its signature to '
          f'(browser, url, color_scheme, record_video_dir). Skipping '
          f'directive.',
          location=self.env.docname,
          type='screencast')
      return []

    poster_filepath = os.path.splitext(filepath)[0] + '.png'
    poster_auto = poster_mode in ('auto-start', 'auto-end')
    needs_recording = not os.path.exists(filepath)
    if poster_auto and not os.path.exists(poster_filepath):
      needs_recording = True

    if needs_recording:
      poster_when = ('start' if poster_mode == 'auto-start' else
                     'end' if poster_mode == 'auto-end' else None)
      fut = self.pool.submit(
          ScreencastDirective.take_screencast,
          url_or_filepath,
          browser,
          viewport_width,
          viewport_height,
          filepath,
          screencast_init_script,
          interactions,
          context_builder,
          request_headers,
          device_scale_factor,
          locale,
          timezone,
          poster_when=poster_when,
          trim_start=trim_value,
          trim_auto=(trim_mode == 'auto'),
          locator=locator_value or None,
          locator_padding=locator_padding_value,
          color_scheme=typing.cast(ColorScheme, cs),
          expected_status_codes=status_code,
          location=self.env.docname,
          timeout=timeout)
      fut.result()

    # Compute src relative to the HTML output of the current doc, since the
    # screencast node has no Sphinx-side image-collection machinery to rewrite
    # the URI for us (unlike nodes.image used by ScreenshotDirective).
    target_uri = self.env.app.builder.get_target_uri(self.env.docname)
    out_doc_dir = os.path.dirname(
        os.path.join(self.env.app.outdir, target_uri))
    rel_filepath = os.path.relpath(
        filepath, start=out_doc_dir).replace(os.sep, '/')

    media_node = screencast()
    media_node['src'] = rel_filepath
    media_node['loop'] = loop_flag
    media_node['autoplay'] = autoplay_flag
    media_node['muted'] = muted_flag
    media_node['controls'] = controls_flag
    if poster_auto:
      media_node['poster'] = os.path.relpath(
          poster_filepath, start=out_doc_dir).replace(os.sep, '/')
    elif poster_mode == 'explicit':
      media_node['poster'] = poster_value
    media_node['classes'] = list(self.options.get('class', []))

    return self._wrap_in_figure(media_node)

  def _wrap_in_figure(self, inner: nodes.Node) -> typing.Sequence[nodes.Node]:
    """Wrap ``inner`` in a ``nodes.figure`` and parse the body as caption.

    Mirrors the body-parsing logic of
    :class:`docutils.parsers.rst.directives.images.Figure.run` — the
    differences: figwidth handling is dropped (only meaningful for
    images) and the inner element is supplied by the caller (a
    :class:`screencast` node) instead of an image node.
    """
    figclasses = self.options.pop('figclass', None)
    figname = self.options.pop('figname', None)
    align = self.options.pop('align', None)

    figure_node = nodes.figure('', inner)
    (figure_node.source,
     figure_node.line) = self.state_machine.get_source_and_line(self.lineno)
    if figclasses:
      figure_node['classes'] += figclasses
    if figname:
      figure_node['names'].append(nodes.fully_normalize_name(figname))
      self.state.document.note_explicit_target(figure_node, figure_node)
    if align:
      figure_node['align'] = align
    self.add_name(figure_node)

    if self.content:
      container = nodes.Element()
      self.state.nested_parse(self.content, self.content_offset, container)
      first_body_index = len(container)
      for i, child in enumerate(container):
        if isinstance(child, (nodes.target, nodes.pending)):
          figure_node += child
          continue
        if isinstance(child, nodes.paragraph):
          caption = nodes.caption(child.rawsource, '', *child.children)
          caption.source = child.source
          caption.line = child.line
          figure_node += caption
          first_body_index = i + 1
          break
        if isinstance(child, nodes.comment) and len(child) == 0:
          first_body_index = i + 1
          break
        error = self.reporter.error(
            'Figure caption must be a paragraph or empty comment.',
            nodes.literal_block(self.block_text, self.block_text),
            line=self.lineno)
        return [figure_node, error]
      if len(container) > first_body_index:
        figure_node += nodes.legend('', *container[first_body_index:])
    return [figure_node]
