# sphinxcontrib-screenshot

A Sphinx extension to embed website screenshots.

```rst
.. screenshot:: http://www.example.com
  :browser: chromium
  :viewport-width: 1280
  :viewport-height: 960
  :color-scheme: dark
```

Read more in the [documentation](https://sphinxcontrib-screenshot.readthedocs.io).

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
