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
"""ffmpeg location and post-processing helpers used by screencast trim/crop."""

import functools
import os
import platform
import re
import shutil
import subprocess
import typing

# Playwright bundles ffmpeg at <browsers-path>/ffmpeg-<rev>/ffmpeg-<platform>.
# Examples:
#   ~/.cache/ms-playwright/ffmpeg-1011/ffmpeg-linux
#   ~/Library/Caches/ms-playwright/ffmpeg-1011/ffmpeg-mac-arm64
#   %USERPROFILE%\AppData\Local\ms-playwright\ffmpeg-1011\ffmpeg-win64.exe
_FFMPEG_DIR_RE = re.compile(r'^ffmpeg-\d+$')
_FFMPEG_BIN_RE = re.compile(r'^ffmpeg-[\w-]+(\.exe)?$')


def _default_browsers_path() -> str:
  """Default Playwright browsers cache, matching `playwright install`."""
  system = platform.system()
  if system == 'Windows':
    return os.path.expandvars(r'%USERPROFILE%\AppData\Local\ms-playwright')
  if system == 'Darwin':
    return os.path.expanduser('~/Library/Caches/ms-playwright')
  return os.path.expanduser('~/.cache/ms-playwright')


def _find_ffmpeg() -> typing.Optional[str]:
  """Locate an ffmpeg binary.

  Prefers the one bundled by Playwright at ``$PLAYWRIGHT_BROWSERS_PATH`` (or
  the OS-specific default used by ``playwright install``). Falls back to a
  system ffmpeg on PATH. Returns None if nothing is found.
  """
  base = os.environ.get('PLAYWRIGHT_BROWSERS_PATH') or _default_browsers_path()
  candidates = []
  if os.path.isdir(base):
    for entry in os.listdir(base):
      if not _FFMPEG_DIR_RE.match(entry):
        continue
      ffmpeg_dir = os.path.join(base, entry)
      for bin_entry in os.listdir(ffmpeg_dir):
        if _FFMPEG_BIN_RE.match(bin_entry):
          candidates.append(os.path.join(ffmpeg_dir, bin_entry))
  candidates.sort(reverse=True)
  bundled = next(
      (c for c in candidates if os.path.isfile(c) and os.access(c, os.X_OK)),
      None)
  return bundled or shutil.which('ffmpeg')


def _require_ffmpeg(reason: str) -> str:
  """Resolve ffmpeg or raise a clear error explaining what needs it."""
  ffmpeg = _find_ffmpeg()
  if not ffmpeg:
    raise RuntimeError(
        f'{reason} requires ffmpeg, but none was found. Install Playwright '
        f"browsers (`playwright install`) which bundles ffmpeg, or install "
        f'a system ffmpeg available on PATH.')
  return ffmpeg


@functools.lru_cache(maxsize=None)
def _has_vp9(ffmpeg: str) -> bool:
  """Return True iff ``ffmpeg`` has the libvpx-vp9 encoder built in.

  Playwright's bundled ffmpeg is compiled with VP8 only
  (``--enable-encoder=libvpx_vp8``); a system ffmpeg usually has both.
  Probing once per binary lets us pick the better codec when available
  and silently fall back to VP8 otherwise.
  """
  try:
    out = subprocess.run([ffmpeg, '-hide_banner', '-encoders'],
                         check=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL,
                         timeout=5).stdout
  except (subprocess.SubprocessError, OSError):
    return False
  return b'libvpx-vp9' in out


def _postprocess_video(
    ffmpeg: str,
    src: str,
    dst: str,
    trim_start: typing.Optional[float] = None,
    crop: typing.Optional[typing.Tuple[int, int, int, int]] = None,
) -> None:
  """Apply optional trim and/or crop to ``src`` and write to ``dst``.

  Combines both into a single libvpx re-encode pass when both are requested.
  ``crop`` is ``(x, y, w, h)`` in video pixels.
  """
  cmd = [ffmpeg, '-y', '-i', src]
  if trim_start:
    cmd += ['-ss', f'{trim_start:.3f}']
  if crop:
    x, y, w, h = crop
    cmd += ['-vf', f'crop={w}:{h}:{x}:{y}']
  # Constant-quality re-encode: prefer VP9 when available (better
  # compression at equal quality, especially for UI/text screen
  # content), fall back to VP8 with the libvpx ffmpeg that Playwright
  # bundles (compiled VP8-only). ``-b:v 0`` enables true CQ mode where
  # the encoder targets the CRF rather than a fixed bitrate. CRF 28 is
  # Google's recommended sweet spot for VP9 screen content; the VP8
  # equivalent is ~CRF 10 (the VP8 scale runs 4–63 with a different
  # quality curve). ``-row-mt 1`` parallelises tile-row encoding on
  # VP9 (no-op / unsupported on VP8). ``-quality good -cpu-used 1``
  # tunes VP8 for the best quality/speed trade-off.
  if _has_vp9(ffmpeg):
    cmd += [
        '-an', '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '28', '-row-mt', '1',
        dst
    ]
  else:
    cmd += [
        '-an', '-c:v', 'libvpx', '-b:v', '0', '-crf', '10', '-quality', 'good',
        '-cpu-used', '1', dst
    ]
  try:
    subprocess.run(
        cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
  except subprocess.CalledProcessError as e:
    stderr = (e.stderr or b'').decode('utf-8', errors='replace').strip()
    raise RuntimeError(
        f'ffmpeg failed (exit {e.returncode}) for {src!r}:\n{stderr}') from e
