# Copyright 2025 Google LLC
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
def create_app(sphinx_app):

  def hello_world_app(environ, start_response):
    headers = [('Content-type', 'text/html; charset=utf-8')]
    start_response('200 OK', headers)
    style = (b"font-family: arial; " + b"font-size: 30px; " + b"padding: 0; " +
             b"margin: 0; " + b"font-smooth: never; " + b"line-height: 1.15;")

    return [
        b"<html>" + b'<body style="' + style + b'">' + b"<script>" +
        b"document.body.innerText = " +
        b"Intl.DateTimeFormat().resolvedOptions().timeZone;" + b"</script>" +
        b"</body>" + b"</html>"
    ]

  return hello_world_app
