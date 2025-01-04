========================
sphinxcontrib-screenshot
========================


A Sphinx extension to embed website screenshots.

Install
#######

sphinxcontrib-screenshot uses `playwright <https://playwright.dev/python>`__ to take screenshots, so it must be installed with ``playwright install``. You can have more details on the playwright documentation.

.. code-block:: bash

    pip install sphinxcontrib-screenshot
    playwright install


Usage
#####

Add `sphinxcontrib.screenshot` to your `conf.py`.

.. code-block:: python

    extensions = ["sphinxcontrib.screenshot"]

Then use the `screenshot` directive in your Sphinx source file.

.. code-block:: rst

    .. screenshot:: http://www.example.com

Options
#######

.. screenshot:: https://github.com/tushuhei/sphinxcontrib-screenshot
    :align: right
    :width: 400

    An example of screenshot using the figure `:align:` and `:width:` options.

`screenshot` inherits from the `figure directive <https://docutils.sourceforge.io/docs/ref/rst/directives.html#image>`__
and supports all its options (`:align:`, `:alt:`, `:figclass:`, `:figwidth:`, `:height:`, `:loading:`, `:scale:`, `:target:`, `:width:`)

.. code-block:: rst

    .. screenshot:: https://github.com/tushuhei/sphinxcontrib-screenshot
        :align: right
        :width: 400

        An example of screenshot using the figure `:align:` and `:width:` options.

.. _browser:

``:browser:``
=============

You can choose the browser to use to take the screenshots with the :code:`:browser:` option.

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :browser: firefox

.. _color-scheme:

``:color-scheme:``
==================

You can set the color scheme you prefer to display the page ('dark' or 'light'):

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :color-scheme: dark

.. _context:

``:context:``
=============

The custom context to use for taking the screenshot. See :ref:`screenshot_contexts`.

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :context: logged-as-user

.. _full-page:

``:full-page:``
===============

You can indicate that you want the screenshot to take the whole page and not just the visible window:

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :full-page:

.. _header:

``:header:``
============

You can pass additional headers to the requests, for instance to customize the display language or pass authentication details:

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :header:
        Authorization Bearer my-super-secret-token
        Accept-Language fr-FR,fr

.. _interactions:

``:interactions:``
==================

You can describe the interaction that you want to have with the webpage before taking a screenshot in JavaScript.

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :interactions:
        document.querySelector('button').click();

.. _pdf:

``:pdf:``
=========

It also generates a PDF file when :code:`pdf` option is given, which might be useful when you need scalable image assets.

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :pdf:

.. screenshot:: http://www.example.com
  :pdf:


.. _viewport_width:
.. _viewport_height:

``:viewport-width:`` and ``:viewport-height:``
==============================================

You can specify the screen size for a particular screenshot with :code:`viewport-width` and :code:`viewport-height` parameters.

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :viewport-width: 800
      :viewport-height: 600

.. screenshot:: http://www.example.com
  :viewport-width: 800
  :viewport-height: 600

Configuration
#############

.. _screenshot_contexts:

``screenshot_contexts``
=======================

You can use the `screenshot_contexts` configuration parameter and the :ref:`:context: <context>` option to set up custom contexts for the screenshots.
This can be useful for instance to perform authentication requests before accessing to protected pages.
Note that you can use the `storage_state` parameter to load a previous context and avoid making authentication requests for every screenshot.

.. code-block:: python
   :caption: conf.py

    screenshot_contexts = {
        "logged-as-user": "my_module.doc:logged_as_user",
    }

.. code-block:: python
   :caption: my_module/doc.py

    def logged_as_user(browser, url, color_scheme):
        try:
            # Attempt to load a saved context from 'user.json'
            context = browser.new_context(
                color_scheme=color_scheme, storage_state="user.json"
            )
        except FileNotFoundError:
            # Create a fresh new context
            context = browser.new_context(color_scheme=color_scheme)

            # Load the authentication page
            page = context.new_page()
            page.goto(get_root_url(url) + "/login")
            page.wait_for_load_state()

            # Perform authentication
            page.locator("input[name=login]").fill("user")
            page.locator("input[name=password]").fill("password")
            page.click("*[type=submit]")
            page.wait_for_load_state()

            # Save the context in 'user.json'
            context.storage_state(path="user.json")
        return context

.. _screenshot_default_browser:

``screenshot_default_browser``
==============================

This is the default value to use when :ref:`:browser: <browser>` is not set.

.. code-block:: python

   screenshot_default_browser = "firefox"


.. _screenshot_default_color_scheme:

``screenshot_default_color_scheme``
===================================

This is the default value to use when :ref:`:color-scheme: <color-scheme>` is not set.

.. code-block:: python

   screenshot_default_color_scheme = "dark"

``screenshot_default_full_page``
===================================

This is the default value to use when :ref:`:full-page: <full-page>` is not set.

.. code-block:: python

   screenshot_default_full_page = True

``screenshot_default_headers``
==============================

Those are the default headers to be used when taking screenshots. They can be overwritten by :ref:`:header: <header>`:

.. code-block:: python

    screenshot_default_headers = {
        "Authorization": "Bearer my-super-secret-token",
        "Accept-Language": "fr-FR,fr",
    }

.. _screenshot_default_viewport_width:
.. _screenshot_default_viewport_height:

``screenshot_default_viewport_width`` and ``screenshot_default_viewport_height``
================================================================================

You can define the default size of your screenshots in `conf.py`, those values will be used by default when :ref:`:viewport-width: <viewport_width>` and :ref:`:viewport-height: <viewport_height>` are not set:

.. code-block:: python

    screenshot_default_viewport_width = 1920
    screenshot_default_viewport_height = 1200

Local WSGI application
######################

`sphinxcontrib-screenshot` can launch your local WSGI applications and take screenshot of thems.
Define them in the :code:`screenshot_apps` dict.
The key must be a name you choose for your applications, and the value must be a callable that creates a WSGI app:

.. code-block:: python
   :caption: my_module/my_app.py

    from flask import Flask

    def create_app(sphinx_app):
        app = Flask(__name__)

        @app.route("/hello")
        def hello():
            return "Hello, world!"

        return app

.. code-block:: python
   :caption: conf.py

    screenshot_apps = {
        "example": "my_module.my_app:create_app",
    }

Note that you might manually add your application module in :code:`sys.path`.

Then you can use a Sphinx substitution with your application name to refer to its temporary URL:

.. code-block:: rst

    .. screenshot:: |example|/hello

Local http server
#################

`sphinxcontrib-screenshot` supports URLs with the HTTP and HTTPS protocols.
To take screenshots of local files and build the document while running a local server for them, you can use the NPM library `concurrently <https://www.npmjs.com/package/concurrently>`__ in the following way:

.. code-block:: bash
   :caption: Build the document

   npx --yes concurrently -k --success=first "make html" "python3 -m http.server 3000 --directory=examples"

.. code-block:: bash
   :caption: Watch and build the document

   npx --yes concurrently -k "make livehtml" "python3 -m http.server 3000 --directory=examples"

Notes
#####

This extension uses `Playwright <https://playwright.dev>`__ to capture a screenshot of the specified website only.
No data is sent to any other external server; the request is limited to the specified website.
Be cautious: avoid including sensitive information (such as authentication data) in the directive content.

Contributing
############

.. include:: ../CONTRIBUTING.md
   :parser: myst_parser.sphinx_

License
#######

Apache 2.0; see the `LICENSE file <https://github.com/tushuhei/sphinxcontrib-screenshot/blob/main/LICENSE>`__ for details.

Disclaimer
##########

This project is not an official Google project. It is not supported by
Google and Google specifically disclaims all warranties as to its quality,
merchantability, or fitness for a particular purpose.
