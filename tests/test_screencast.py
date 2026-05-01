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
import re
import subprocess
from io import StringIO

import pytest
from bs4 import BeautifulSoup
from sphinx.testing.util import SphinxTestApp

from sphinxcontrib.screenshot._ffmpeg import _find_ffmpeg


def _video_dimensions(filepath):
  """Return (width, height) of a WebM by parsing ffmpeg -i stderr."""
  ffmpeg = _find_ffmpeg()
  assert ffmpeg, 'ffmpeg not found, required for tests'
  result = subprocess.run([ffmpeg, '-i', str(filepath)],
                          capture_output=True,
                          text=True)

  for line in result.stderr.split('\n'):
    if 'Video:' in line:
      match = re.search(r'(\d+)x(\d+)', line)
      if match:
        return int(match.group(1)), int(match.group(2))

  raise AssertionError(
      f'Could not parse video dimensions from:\n{result.stderr}')


@pytest.mark.sphinx('html', testroot='screencast')
def test_default(app: SphinxTestApp, status: StringIO,
                 warning: StringIO) -> None:
  """A bare directive emits one ``<video>`` pointing to a non-empty .webm."""
  app.build()

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  videos = soup.find_all('video')
  assert len(videos) == 1

  src = videos[0]['src']
  assert src.endswith('.webm')
  assert (app.outdir / src).exists()
  assert (app.outdir / src).stat().st_size > 0


@pytest.mark.sphinx('html', testroot='screencast-attrs')
def test_attributes(app: SphinxTestApp, status: StringIO,
                    warning: StringIO) -> None:
  """Boolean flags reach ``<video>`` and Figure options reach the figure."""
  app.build()

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  video = soup.find('video')
  assert video is not None
  assert video.has_attr('loop')
  assert video.has_attr('muted')
  assert video.has_attr('controls')

  figcaption = soup.find('figcaption')
  assert figcaption is not None
  # Sphinx wraps the caption text in a ``span.caption-text`` and appends a
  # ``¶`` headerlink — match the inner span rather than the full text.
  caption_text = figcaption.find(class_='caption-text')
  assert caption_text is not None
  assert caption_text.text.strip() == 'Test caption'

  figure = soup.find('figure')
  assert figure is not None
  assert 'align-center' in figure.get('class', [])


@pytest.mark.sphinx('html', testroot='screencast')
def test_cache_hit(app: SphinxTestApp, status: StringIO,
                   warning: StringIO) -> None:
  """A second build with ``force_all=True`` reuses the cached .webm."""
  app.build()
  webms = list((app.outdir / "_static" / "screencasts").glob("*.webm"))
  assert len(webms) == 1
  mtime_first = webms[0].stat().st_mtime

  # Force Sphinx to revisit the doctree without invalidating the cache file.
  app.build(force_all=True)
  webms_after = list((app.outdir / "_static" / "screencasts").glob("*.webm"))
  assert len(webms_after) == 1
  assert webms_after[0].name == webms[0].name
  assert webms_after[0].stat().st_mtime == mtime_first


@pytest.mark.sphinx('text', testroot='screencast-poster')
def test_poster_fallback_text(app: SphinxTestApp, status: StringIO,
                              warning: StringIO) -> None:
  """Non-HTML builders use the explicit ``:poster:`` URL as fallback image."""
  app.build()
  assert 'screencast directive skipped' not in warning.getvalue()
  assert (app.outdir / "index.txt").exists()


@pytest.mark.sphinx('text', testroot='screencast', freshenv=True)
def test_no_poster_non_html(app: SphinxTestApp, status: StringIO,
                            warning: StringIO) -> None:
  """Without a poster, non-HTML builders warn and skip the directive."""
  app.build()
  assert 'screencast directive skipped' in warning.getvalue()
  screencasts_dir = app.outdir / "_static" / "screencasts"
  assert not screencasts_dir.exists() or not list(
      screencasts_dir.glob("*.webm"))


@pytest.mark.sphinx('html', testroot='screencast-autoplay')
def test_autoplay_forces_muted(app: SphinxTestApp, status: StringIO,
                               warning: StringIO) -> None:
  """``:autoplay:`` without ``:muted:`` warns and forces ``muted`` on."""
  app.build()

  warn_text = warning.getvalue()
  assert 'autoplay' in warn_text and 'muted' in warn_text

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  video = soup.find('video')
  assert video is not None
  assert video.has_attr('autoplay')
  assert video.has_attr('muted')


@pytest.mark.sphinx('html', testroot='screencast-contexts')
def test_custom_context_builder(app: SphinxTestApp, status: StringIO,
                                warning: StringIO) -> None:
  """A 4-args builder accepting ``record_video_dir`` records video."""
  app.build()

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  video = soup.find('video')
  assert video is not None
  src = video['src']
  assert (app.outdir / src).exists()
  assert (app.outdir / src).stat().st_size > 0


@pytest.mark.sphinx('html', testroot='screencast-contexts-legacy')
def test_legacy_context_builder_emits_error_and_skips(
    app: SphinxTestApp, status: StringIO, warning: StringIO) -> None:
  """A 3-args builder is detected early: error logged, directive skipped."""
  app.build()
  warn_text = warning.getvalue()
  assert 'record_video_dir' in warn_text

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  assert soup.find('video') is None


@pytest.mark.sphinx('html', testroot='screencast-poster-auto')
def test_poster_auto(app: SphinxTestApp, status: StringIO,
                     warning: StringIO) -> None:
  """Bare ``:poster:`` produces a PNG sibling next to the .webm."""
  app.build()

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  video = soup.find('video')
  assert video is not None
  assert video.has_attr('poster')

  poster_src = video['poster']
  assert poster_src.endswith('.png')
  assert (app.outdir / poster_src).exists()
  assert (app.outdir / poster_src).stat().st_size > 0

  # Poster sits next to the .webm with the same hash basename.
  webm_src = video['src']
  assert webm_src.endswith('.webm')
  assert (app.outdir / webm_src).exists()
  assert poster_src.replace('.png', '.webm') == webm_src


@pytest.mark.sphinx('html', testroot='screencast-poster-auto-end')
def test_poster_auto_end(app: SphinxTestApp, status: StringIO,
                         warning: StringIO) -> None:
  """``:poster: auto-end`` captures the post-interaction state."""
  from PIL import Image

  app.build()

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  video = soup.find('video')
  assert video is not None
  assert video.has_attr('poster')

  poster_path = app.outdir / video['poster']
  assert poster_path.exists()
  assert poster_path.stat().st_size > 0

  # Page starts red and the interaction repaints it green. With
  # :poster: auto-end, the screenshot is taken after the interaction
  # runs, so the poster should be green — not red.
  img = Image.open(poster_path).convert('RGB')
  r, g, b = img.getpixel((img.width // 2, img.height // 2))
  assert g > 200 and r < 50, f'expected green poster, got rgb=({r},{g},{b})'


@pytest.mark.sphinx('html', testroot='screencast-config-defaults')
def test_config_defaults_apply_to_flags(app: SphinxTestApp, status: StringIO,
                                        warning: StringIO) -> None:
  """``screencast_default_*`` fill in flags absent from the directive."""
  app.build()

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  video = soup.find('video')
  assert video is not None
  # No flags written on the directive — these come from conf.py defaults.
  assert video.has_attr('loop')
  assert video.has_attr('muted')
  assert video.has_attr('controls')
  assert not video.has_attr('autoplay')


@pytest.mark.sphinx('html', testroot='screencast-trim')
def test_trim_explicit(app: SphinxTestApp, status: StringIO,
                       warning: StringIO) -> None:
  """``:trim-start: 0.5`` runs the ffmpeg post-process to a valid .webm."""
  app.build()

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  video = soup.find('video')
  assert video is not None

  webm = app.outdir / video['src']
  assert webm.exists()
  assert webm.stat().st_size > 0


@pytest.mark.sphinx('html', testroot='screencast-locator')
def test_locator(app: SphinxTestApp, status: StringIO,
                 warning: StringIO) -> None:
  """``:locator:`` crops the video to the matched element's bounding box."""
  app.build()

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  video = soup.find('video')
  assert video is not None

  webm = app.outdir / video['src']
  assert webm.exists()
  # The HTML page has a #target div of 120x80px at margin 30px. The crop
  # should produce a video roughly that size (libvpx may round to even).
  width, height = _video_dimensions(webm)
  assert 118 <= width <= 122, f'unexpected width {width}'
  assert 78 <= height <= 82, f'unexpected height {height}'


@pytest.mark.sphinx('html', testroot='screencast-color-scheme-auto')
def test_color_scheme_auto(app: SphinxTestApp, status: StringIO,
                           warning: StringIO) -> None:
  """``:color-scheme: auto`` emits two videos with only-light/only-dark."""
  app.build()

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  videos = soup.find_all('video')
  assert len(videos) == 2

  classes = [set(v.get('class', [])) for v in videos]
  assert {'only-light'} <= classes[0]
  assert {'only-dark'} <= classes[1]

  # Each video has its own .webm — distinct hash because color_scheme is in it.
  srcs = [v['src'] for v in videos]
  assert srcs[0] != srcs[1]
  assert all((app.outdir / s).exists() for s in srcs)


@pytest.mark.sphinx('html', testroot='screencast-locator-padding')
def test_locator_padding(app: SphinxTestApp, status: StringIO,
                         warning: StringIO) -> None:
  """``:locator-padding:`` widens the locator's crop box."""
  app.build()

  soup = BeautifulSoup((app.outdir / "index.html").read_text(), "html.parser")
  video = soup.find('video')
  assert video is not None

  webm = app.outdir / video['src']
  assert webm.exists()
  # ``:locator-padding: 10`` widens the 120x80 #target bbox by 10 px on
  # each side -> ~140x100. libvpx may round dimensions to even.
  width, height = _video_dimensions(webm)
  assert 138 <= width <= 142, f'unexpected width {width}'
  assert 98 <= height <= 102, f'unexpected height {height}'
