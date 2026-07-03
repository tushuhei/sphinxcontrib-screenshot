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
from io import StringIO

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinxcontrib.screenshot._common import validate_alias


@pytest.mark.parametrize('value,expected', [
    ('my-shot', 'my-shot'),
    ('  my-shot  ', 'my-shot'),
    ('My_Shot.2', 'My_Shot.2'),
    ('a', 'a'),
])
def test_validate_alias_accepts(value: str, expected: str) -> None:
  assert validate_alias(value) == expected


@pytest.mark.parametrize('value', [
    '',
    '   ',
    '.',
    '..',
    'a/b',
    'a\\b',
    '../etc',
    '/abs',
    'a b',
    'café',
    'a#b',
])
def test_validate_alias_rejects(value: str) -> None:
  with pytest.raises(ValueError):
    validate_alias(value)


@pytest.mark.sphinx('html', testroot='alias')
def test_alias_screenshot(app: SphinxTestApp, status: StringIO,
                          warning: StringIO) -> None:
  """``:alias:`` copies the screenshot (and its PDF) to a stable name.

  The hashed artifact stays in place; the alias is a byte-identical copy
  alongside it, and the glob picks up the companion ``.pdf`` too.
  """
  app.build()

  ss_dir = app.outdir / '_static' / 'screenshots'
  alias_png = ss_dir / 'my-shot.png'
  alias_pdf = ss_dir / 'my-shot.pdf'

  assert alias_png.exists(), 'expected the aliased PNG'
  assert alias_pdf.exists(), 'expected the aliased PDF'

  hashed = [
      p for p in ss_dir.glob('*.png') if not p.name.startswith('my-shot')
  ]
  assert len(hashed) == 1, 'expected exactly one hashed PNG'
  assert alias_png.read_bytes() == hashed[0].read_bytes()


@pytest.mark.sphinx('html', testroot='alias-color-scheme-auto')
def test_alias_color_scheme_auto(app: SphinxTestApp, status: StringIO,
                                 warning: StringIO) -> None:
  """``:color-scheme: auto`` writes ``-light``/``-dark`` aliased files."""
  app.build()

  ss_dir = app.outdir / '_static' / 'screenshots'
  assert (ss_dir / 'my-shot-light.png').exists()
  assert (ss_dir / 'my-shot-dark.png').exists()
  assert not (ss_dir / 'my-shot.png').exists()


@pytest.mark.sphinx('html', testroot='alias-screencast')
def test_alias_screencast(app: SphinxTestApp, status: StringIO,
                          warning: StringIO) -> None:
  """``:alias:`` copies the screencast and its automatic poster."""
  app.build()

  sc_dir = app.outdir / '_static' / 'screencasts'
  alias_webm = sc_dir / 'my-cast.webm'
  alias_poster = sc_dir / 'my-cast.png'

  assert alias_webm.exists(), 'expected the aliased WebM'
  assert alias_webm.stat().st_size > 0
  assert alias_poster.exists(), 'expected the aliased poster'
  assert alias_poster.stat().st_size > 0
