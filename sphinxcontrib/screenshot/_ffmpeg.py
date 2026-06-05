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
"""ffmpeg location and the single-pass encoder used by screencast recording."""

import math
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


_PNG_DECODER_RE = re.compile(r'(?mi)^\s*\S+\s+png\b')


def decodes_png(ffmpeg: str) -> bool:
  """Whether ``ffmpeg`` can decode PNG input.

  The ffmpeg bundled by Playwright is built ``--disable-everything`` and only
  decodes mjpeg (its native screencast input), so PNG frames require a system
  ffmpeg. Callers fall back to JPEG capture when this returns False.
  """
  try:
    result = subprocess.run([ffmpeg, '-hide_banner', '-decoders'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            check=False)
  except OSError:
    return False
  return bool(_PNG_DECODER_RE.search(result.stdout.decode('utf-8', 'replace')))


# Near-lossless VP8 encoder, applied to the buffered frames. The bundled
# Playwright ffmpeg ships VP8 only (decodes mjpeg, encodes vp8), so VP8 is the
# default codec; users who want VP9/AV1/lossless point :ffmpeg-executable: at a
# system ffmpeg and override the encoder via :ffmpeg-options:. A low CRF on
# PNG/JPEG-q100 sources keeps monospace text crisp. Encoding is offline (frames
# are buffered first), so the slower 'good' deadline is used.
_VP8_CRF = 4

DEFAULT_ENCODE = (f'-an -c:v libvpx -b:v 0 -crf {_VP8_CRF} -qmin 0 -qmax 10 '
                  '-deadline good -cpu-used 1')


def encode_frames(
    ffmpeg: str,
    frames: typing.Sequence[typing.Tuple[bytes, float]],
    dst: str,
    fps: int,
    frame_format: str = 'png',
    crop: typing.Optional[typing.Tuple[int, int, int, int]] = None,
    trim_start: typing.Optional[float] = None,
    encode_options: typing.Optional[str] = None,
) -> None:
  """Encode buffered image frames into ``dst`` in a single ffmpeg pass.

  ``frames`` is a list of ``(image_bytes, timestamp_seconds)`` in capture
  order, each encoded as ``frame_format`` (``'png'`` or ``'jpeg'``). A
  constant-rate frame pump repeats each frame to honor wall-clock timing,
  mirroring Playwright's own ``videoRecorder.ts``. ``crop`` is ``(x, y, w, h)``
  in frame pixels; ``trim_start`` drops frames captured before that many
  seconds from the first frame. ``encode_options`` replaces the default encoder
  selection; the input, crop and even-dimension pad are always injected here.
  """
  if not frames:
    raise RuntimeError('No frames to encode.')

  decoder = 'png' if frame_format == 'png' else 'mjpeg'

  if trim_start:
    cutoff = frames[0][1] + trim_start
    frames = [f for f in frames if f[1] >= cutoff] or frames[-1:]

  # Frame pump: write each frame as many times as the constant-rate grid
  # advanced since the previous one. Identical repeated PNGs cost almost
  # nothing once VP8 inter-codes them. A trailing second of the last frame
  # leaves the video resting on the final state.
  t0 = frames[0][1]
  payload = bytearray()
  prev: typing.Optional[bytes] = None
  prev_index = 0
  for png, ts in frames:
    index = math.floor((ts - t0) * fps)
    if prev is not None:
      payload += prev * (index - prev_index)
    prev, prev_index = png, index
  payload += frames[-1][0] * fps

  vf = []
  if crop:
    x, y, w, h = crop
    vf.append(f'crop={w}:{h}:{x}:{y}')
  vf.append('pad=ceil(iw/2)*2:ceil(ih/2)*2')

  cmd = [
      ffmpeg, '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate',
      str(fps), '-c:v', decoder, '-i', 'pipe:0', '-vf', ','.join(vf)
  ]
  cmd += (encode_options or DEFAULT_ENCODE).split()
  cmd += [dst]

  proc = subprocess.Popen(
      cmd,
      stdin=subprocess.PIPE,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.PIPE)
  _, stderr = proc.communicate(input=bytes(payload))
  if proc.returncode:
    message = (stderr or b'').decode('utf-8', errors='replace').strip()
    raise RuntimeError(
        f'ffmpeg failed (exit {proc.returncode}) while encoding screencast:\n'
        f'{message}')
