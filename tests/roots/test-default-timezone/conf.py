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
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.resolve()))

extensions = ['sphinxcontrib.screenshot']
screenshot_apps = {"example": "example_timezone_app:create_app"}
screenshot_default_timezone = 'Europe/Berlin'
