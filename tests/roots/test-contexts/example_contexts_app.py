# Copyright 2024 Google LLC
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

number_of_visits = 0


def custom_context(browser, url, color_scheme):
  context = browser.new_context(color_scheme=color_scheme)
  page = context.new_page()
  page.goto(url)
  return context


def create_app(sphinx_app):

  def hello_world_app(environ, start_response):
    global number_of_visits
    number_of_visits = number_of_visits + 1
    headers = [('Content-type', 'text/html; charset=utf-8')]
    start_response('200 OK', headers)
    style = b"font-family: arial; font-size: 10px; margin: 0; padding: 0"
    return [
        b"<html>" + b'<body style="' + style + b'">' +
        b"Hello, custom context. You have been here " +
        str(number_of_visits).encode() + b" times." + b"</body>" + b"</html>"
    ]

  return hello_world_app
