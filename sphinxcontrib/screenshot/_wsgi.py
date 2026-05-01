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

import threading
import typing
import wsgiref.simple_server

from portpicker import pick_unused_port
from sphinx.application import Sphinx
from sphinx.config import Config

from ._common import resolve_python_method

app_threads: typing.Dict[str, typing.Tuple[wsgiref.simple_server.WSGIServer,
                                           threading.Thread]] = {}


def setup_apps(app: Sphinx, config: Config):
  """Start the WSGI application threads.

  A new replacement is created for each WSGI app.
  """
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
