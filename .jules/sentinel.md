## 2026-05-22 - Absolute Path Leakage via file:// URLs in Exceptions
**Vulnerability:** Resolved `file://` URLs containing absolute paths were being included in `RuntimeError` messages and log warnings when operations like navigation or element location failed. This disclosed the build server's internal directory structure.

**Learning:** Normalizing or resolving paths to absolute URLs is necessary for internal logic but these URLs must be sanitized before being included in any output that might reach a user or a persistent log.

**Prevention:** Use a dedicated sanitization helper like `_mask_url` to redact sensitive schemes (like `file://`) from URLs before they are interpolated into exception messages or log entries.

## 2026-05-21 - Path Traversal Vulnerability in file:// URL handling
**Vulnerability:** The `_resolve_url` method in `_common.py` did not validate that resolved `file://` URLs or relative paths pointing to local files were contained within the Sphinx source directory. This allowed a malicious or misconfigured Sphinx project to take screenshots of sensitive local files (e.g., `/etc/passwd`) by providing absolute `file://` URLs or using `../` traversal in relative paths.

**Learning:** Path resolution logic that converts relative paths to absolute URLs (like `file://`) must explicitly verify that the final path is within an allowed boundary (e.g., the project root). Simply normalizing the path is not enough, as traversal sequences can still escape the intended directory. Also, `urlparse` might not handle platform-specific path conventions for `file://` URLs as well as `urllib.request.url2pathname`.

**Prevention:** Always use `os.path.commonpath` or `Path.relative_to` to verify that a resolved file path is contained within the expected base directory. Integrate these checks at the end of the resolution process to ensure all potential bypasses (relative paths, absolute paths, URLs) are covered.

## 2026-05-08 - Information Disclosure in Error Messages
**Vulnerability:** Error messages (RuntimeError) raised during path resolution and Playwright operations were leaking sensitive information, including the absolute path of the Sphinx source directory, internal function names, and raw JavaScript `interactions` scripts which could contain credentials or session tokens.

**Learning:** Exception messages that bubble up to build logs or user-facing reports should be sanitized. While descriptive errors are helpful for debugging, they should not include server-side filesystem paths or raw input that might contain secrets.

**Prevention:** Use generic error messages for security-related failures. Instead of including the problematic value or the absolute path in the error string, provide a clear explanation of the policy violation. Ensure that user-provided scripts or data are never echoed back in exceptions if they could contain sensitive information.
