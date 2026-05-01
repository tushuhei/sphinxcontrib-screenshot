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


def custom_context(browser, url, color_scheme, record_video_dir):
  context = browser.new_context(
      color_scheme=color_scheme, record_video_dir=record_video_dir)
  page = context.new_page()
  page.goto(url)
  return context


def create_app(sphinx_app):

  def hello_world_app(environ, start_response):
    headers = [('Content-type', 'text/html; charset=utf-8')]
    start_response('200 OK', headers)
    return [b"<html><body>Hello, screencast context.</body></html>"]

  return hello_world_app
