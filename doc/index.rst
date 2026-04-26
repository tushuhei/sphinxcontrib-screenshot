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

The extension also supports the ``file://`` protocol to take screenshots of local files, and root or document relative paths.

.. code-block:: rst

    .. screenshot:: file:///path/to/your/file.html
    .. screenshot:: /static/example.html
    .. screenshot:: ./example.html

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


.. _device-scale-factor:

``:device-scale-factor:``
=========================

You can set the device scale factor, which can be thought of as DPR (device pixel ratio):

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :device-scale-factor: 2



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


.. _locator:

``:locator:``
=============

You can crop the screenshot to a single element on the page using a
`Playwright selector <https://playwright.dev/python/docs/locators>`__.
The image is bounded by the element's bounding box rather than the
viewport.

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :locator: #content

The page is still rendered at the full :ref:`viewport <viewport_width>`,
so layout (responsive design, scrollbars) reflects the configured
viewport size; only the captured area is reduced to the matched element.

The selector must match exactly one element (Playwright strict mode).
A multi-match selector raises an error; refine the selector. If no
element is matched within :ref:`timeout <timeout>`, the build fails.

When combined with :ref:`full-page <full-page>`, ``:locator:`` wins
(the bounding box is honored). When combined with :ref:`pdf <pdf>`,
the PNG is cropped but the PDF stays page-level — Playwright's PDF
API has no per-element variant.

.. _locale:

``:locale:``
============

You can set the locale for the browser context:

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :locale: en-US

.. _pdf:

``:pdf:``
=========

It also generates a PDF file when :code:`pdf` option is given, which might be useful when you need scalable image assets.

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :pdf:


.. _timezone:

``:timezone:``
==============

You can set the timezone for the browser context:

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :timezone: America/New_York


.. _status-code:

``:status-code:``
=================

You can specify the expected HTTP status codes. A warning is emitted if the page returns a different code.

.. _timeout:

``:timeout:``
=============

You can set the timeout in milliseconds for page operations (navigation, interactions):

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :timeout: 30000

Default: ``10000`` (10 seconds)

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :status-code: 200,201,302

Default: ``200,302``

The warning can be suppressed in ``conf.py``:

.. code-block:: python

    suppress_warnings = ['screenshot.status_code']

.. _viewport_width:
.. _viewport_height:

``:viewport-width:`` and ``:viewport-height:``
==============================================

You can specify the screen size for a particular screenshot with :code:`viewport-width` and :code:`viewport-height` parameters.

.. code-block:: rst

    .. screenshot:: http://www.example.com
      :viewport-width: 320
      :viewport-height: 600

.. screenshot:: http://www.example.com
  :viewport-width: 320
  :viewport-height: 600

Screencasts
###########

In addition to still screenshots, you can record a short WebM screencast of
a page using the ``screencast`` directive. It inherits from docutils'
``Figure``, so the directive body is parsed as the figure caption (rich
reST) and the standard figure options (``:align:``, ``:figclass:``,
``:figname:``, ``:name:``, ``:class:``) are accepted. It also reuses the
page-setup options of :rst:dir:`screenshot` (``:browser:``,
``:viewport-width:``, ``:viewport-height:``, ``:locale:``, ``:timezone:``,
``:headers:``, ``:context:``, ``:device-scale-factor:``, ``:status-code:``,
``:timeout:``, ``:interactions:``).

.. screencast:: https://github.com/tushuhei/sphinxcontrib-screenshot
    :viewport-width: 800
    :viewport-height: 400
    :controls:
    :muted:
    :interactions:
        window.scrollTo({top: 600, behavior: 'smooth'});
        await new Promise(r => setTimeout(r, 1500));

    Scrolling the project page.

.. code-block:: rst

    .. screencast:: https://github.com/tushuhei/sphinxcontrib-screenshot
        :viewport-width: 800
        :viewport-height: 400
        :controls:
        :muted:
        :interactions:
            window.scrollTo({top: 600, behavior: 'smooth'});
            await new Promise(r => setTimeout(r, 1500));

        Scrolling the project page.

The recording covers the load of the page, then the JavaScript interactions
passed to ``:interactions:``, then closes. There is no separate
``:duration:`` option: to keep the page busy after a click (e.g. to capture
a CSS transition), keep awaiting in the JavaScript itself
(``await new Promise(r => setTimeout(r, ms))``). Playwright awaits the
returned Promise, so the video covers exactly what the script does.

Video options
=============

``:loop:``, ``:autoplay:``, ``:muted:``, ``:controls:``
    HTML5 ``<video>`` boolean attributes. ``:autoplay:`` without ``:muted:``
    is rejected by most browsers; if you set the former without the latter,
    a warning is emitted and ``muted`` is forced.

``:poster:``
    Still image displayed before playback. Four modes:

    - **Absent**: no poster, the ``<video>`` shows a black background.
      The directive is also skipped on non-HTML builders.
    - **Flag** (``:poster:`` with no value) or ``:poster: auto-start``: an
      automatic screenshot of the page is taken right after load, before
      interactions. Saved next to the WebM and used as the ``poster``
      attribute. Currently only generated for HTML builds.
    - ``:poster: auto-end``: same as above but the screenshot is taken
      *after* the interactions complete, so the poster reflects the final
      state shown at the end of the video.
    - **URL** (``:poster: ./image.png``): explicit URL of an image you
      provide. Also used as fallback for non-HTML builders.

    ``auto-start`` and ``auto-end`` are reserved keywords. To pass an
    image whose URL is literally one of those, use a relative form like
    ``./auto-end`` or add an extension (``auto-end.png``).

``:trim-start:``
    Trim the beginning of the recording. Three modes:

    - **Absent**: no trim. The video covers the full Playwright context
      lifecycle, including the initial about:blank flash.
    - **Flag** (``:trim-start:`` with no value): automatic. The extension
      measures the time between context creation and the end of page load
      and trims that prefix.
    - **Seconds** (``:trim-start: 1.5``): trim that many seconds off the
      front.

    Requires ffmpeg. Playwright already bundles one (downloaded by
    ``playwright install``); a system ffmpeg on PATH is also accepted.

``:locator:``
    Playwright selector. When set, the video is cropped to the bounding
    box of the matched element, similarly to the screenshot directive's
    ``:locator:``. Requires ffmpeg.

``:locator-padding:``
    Pad the locator's bounding box before cropping. Accepts the CSS
    ``padding`` shorthand: an integer (uniform), or 1–4 whitespace-separated
    integers (1 = uniform; 2 = top/bottom + right/left; 3 = top + right/left
    + bottom; 4 = top + right + bottom + left). The padded box is clamped
    to the viewport.

Caption
=======

The directive body is parsed as the figure caption (rich reST). It renders
inside a ``<figcaption>`` below the ``<video>`` for HTML builds, and is
preserved as the caption of the fallback ``<image>`` node when an explicit
``:poster:`` URL is used on non-HTML builders.

.. code-block:: rst

    .. screencast:: ./demo.html
       :align: center
       :figclass: my-screencast
       :interactions:
         document.querySelector('button').click();

       *Clicking* the demo button — caption supports **rich** reST.

Context builders and screencasts
================================

If you use :ref:`screenshot_contexts <screenshot_contexts>`, your builder must
accept a ``record_video_dir`` parameter to be usable with ``screencast``:

.. code-block:: python

    def logged_as_user(browser, url, color_scheme, record_video_dir):
        return browser.new_context(
            color_scheme=color_scheme,
            record_video_dir=record_video_dir,
            storage_state="user.json",
        )

Builders that don't accept ``record_video_dir`` are still called with three
arguments by ``screenshot`` (full backwards compatibility) but raise a build
error when used with ``screencast``.

Limitations
===========

- WebM only (Playwright's native video format). No mp4/h264, no audio.
- HTML output only. Other builders fall back to ``:poster:`` if provided,
  otherwise the directive is skipped.
- The recording starts when the Playwright context is created, so the
  first frames typically show a blank page before the load completes.
  Use ``:trim-start:`` to skip them. This is a `known Playwright
  limitation <https://github.com/microsoft/playwright/issues/27253>`__.
- ``:trim-start:`` and ``:locator:`` require ffmpeg. Playwright already
  bundles one as part of ``playwright install``; the extension uses it
  automatically and falls back to a system ffmpeg if needed.

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


``screenshot_default_device_scale_factor``
==========================================

This is the default value to use when :ref:`:device-scale-factor: <device-scale-factor>` is not set.  Defaults to 1.

.. code-block:: python

   screenshot_default_device_scale_factor = 2


``screenshot_default_locale``
=============================

This is the default value to use when :ref:`:locale: <locale>` is not set. Defaults to `None`.

.. code-block:: python

   screenshot_default_locale = "en-US"


``screenshot_default_timezone``
===============================

This is the default value to use when :ref:`:timezone: <timezone>` is not set. Defaults to `None`.

.. code-block:: python

   screenshot_default_timezone = "America/New_York"


``screenshot_default_timeout``
==============================

This is the default value to use when :ref:`:timeout: <timeout>` is not set. Defaults to ``10000`` (10 seconds).

.. code-block:: python

   screenshot_default_timeout = 30000


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

Screencast defaults
===================

Per-directive options on :rst:dir:`screencast` always win; these set the
fallback when the directive omits the option.

.. code-block:: python

    # Boolean flags. Each maps 1:1 to the matching directive flag.
    screencast_default_loop = True
    screencast_default_autoplay = True   # implies muted (browser policies)
    screencast_default_muted = True
    screencast_default_controls = True

    # Trim the recording's prefix. None disables; 'auto' uses the timer-
    # based mode that elides the about:blank flash; a number is a literal
    # offset in seconds.
    screencast_default_trim_start = 'auto'

    # Apply a poster to every screencast. None disables; 'auto-start'
    # screenshots before interactions; 'auto-end' screenshots after; a
    # path/URL provides an explicit poster.
    screencast_default_poster = 'auto-start'

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

Notes
#####

This extension uses `Playwright <https://playwright.dev>`__ to capture a screenshot of the specified website only.
No data is sent to any other external server; the request is limited to the website specified in the directive.
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
