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

## Pro tips
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
