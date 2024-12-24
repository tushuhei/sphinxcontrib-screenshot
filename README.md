# sphinxcontrib-screenshot

A Sphinx extension to embed website screenshots.

![Example screenshot](https://raw.githubusercontent.com/tushuhei/sphinxcontrib-screenshot/main/example.png)

## Install

```bash
pip install sphinxcontrib-screenshot
playwright install
```

## Usage

Add `sphinxcontrib.screenshot` to your `conf.py`.

```py
extensions = ["sphinxcontrib.screenshot"]
```

Then use the `screenshot` directive in your Sphinx source file.

```rst
.. screenshot:: http://www.example.com
```

You can also specify the screen size for the screenshot with `width` and `height` parameters.

```rst
.. screenshot:: http://www.example.com
  :width: 1280
  :height: 960
```

You can include a caption for the screenshot's `figure` directive.

```rst
.. screenshot:: http://www.example.com
  :caption: This is a screenshot for www.example.com
```

You can describe the interaction that you want to have with the webpage before taking a screenshot in JavaScript.

```rst
.. screenshot:: http://www.example.com

  document.querySelector('button').click();
```

Use `figclass` option if you want to specify a class name to the image.

```rst
.. screenshot:: http://www.example.com
  :figclass: foo
```

It also generates a PDF file when `pdf` option is given, which might be useful when you need scalable image assets.

```rst
.. screenshot:: http://www.example.com
  :pdf:
```

## Local WSGI application

`sphinxcontrib-screenshot` can launch your local WSGI applications and take screenshot of thems.
Define them in the `screenshot_apps` dict.
The key must be a name you choose for your applications, and the value must be a callable that creates a WSGI app:

```python
from flask import Flask

def create_app(sphinx_app):
    app = Flask(__name__)

    @app.route("/hello")
    def hello():
        return "Hello, world!"

    return app
```

```
screenshot_apps = {
    "example": "my_module.my_app:create_app",
}
```
Note that you might manually add your application module in `sys.path`.

Then you can use a Sphinx substitution with your application name to refer to its temporary URL:

```rst
.. screenshot:: |example|/hello
```

## Local http server
`sphinxcontrib-screenshot` supports URLs with the HTTP and HTTPS protocols.
To take screenshots of local files and build the document while running a local server for them, you can use the NPM library [concurrently](https://www.npmjs.com/package/concurrently) in the following way:

### Build the document
```bash
  npx --yes concurrently -k --success=first "make html" "python3 -m http.server 3000 --directory=examples"
```

### Watch and build the document
```bash
  npx --yes concurrently -k "make livehtml" "python3 -m http.server 3000 --directory=examples"
```


## Notes

This extension uses [Playwright](https://playwright.dev) to capture a screenshot of the specified website only.
No data is sent to any other external server; the request is limited to the specified website.
Be cautious: avoid including sensitive information (such as authentication data) in the directive content.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for details.

## License

Apache 2.0; see [`LICENSE`](LICENSE) for details.

## Disclaimer

This project is not an official Google project. It is not supported by
Google and Google specifically disclaims all warranties as to its quality,
merchantability, or fitness for a particular purpose.
