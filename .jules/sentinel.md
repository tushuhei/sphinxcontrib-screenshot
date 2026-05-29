## 2026-05-21 - Path Traversal Vulnerability in file:// URL handling
**Vulnerability:** The `_resolve_url` method in `_common.py` did not validate that resolved `file://` URLs or relative paths pointing to local files were contained within the Sphinx source directory. This allowed a malicious or misconfigured Sphinx project to take screenshots of sensitive local files (e.g., `/etc/passwd`) by providing absolute `file://` URLs or using `../` traversal in relative paths.

**Learning:** Path resolution logic that converts relative paths to absolute URLs (like `file://`) must explicitly verify that the final path is within an allowed boundary (e.g., the project root). Simply normalizing the path is not enough, as traversal sequences can still escape the intended directory. Also, `urlparse` might not handle platform-specific path conventions for `file://` URLs as well as `urllib.request.url2pathname`.

**Prevention:** Always use `os.path.commonpath` or `Path.relative_to` to verify that a resolved file path is contained within the expected base directory. Integrate these checks at the end of the resolution process to ensure all potential bypasses (relative paths, absolute paths, URLs) are covered.

## 2026-05-08 - Information Disclosure in Error Messages
**Vulnerability:** Error messages (RuntimeError) raised during path resolution and Playwright operations were leaking sensitive information, including the absolute path of the Sphinx source directory, internal function names, and raw JavaScript `interactions` scripts which could contain credentials or session tokens.

**Learning:** Exception messages that bubble up to build logs or user-facing reports should be sanitized. While descriptive errors are helpful for debugging, they should not include server-side filesystem paths or raw input that might contain secrets.

**Prevention:** Use generic error messages for security-related failures. Instead of including the problematic value or the absolute path in the error string, provide a clear explanation of the policy violation. Ensure that user-provided scripts or data are never echoed back in exceptions if they could contain sensitive information.

## 2026-06-15 - Environmental Confidentiality via URL Masking
**Vulnerability:** Even when error messages were somewhat sanitized, some logs and exceptions still interpolated the full `file://` URL, which contains the absolute filesystem path of the documentation source directory.

**Learning:** Manually sanitizing every error message is error-prone. A centralized utility for masking sensitive components of a URL (like local file paths) ensures consistency across the codebase.

**Prevention:** Use a `_mask_url` helper to replace `file://` URLs with a generic `<local file>` placeholder before including them in any user-facing error messages or building logs. This preserves debugging context (knowing a local file was involved) without revealing the underlying host's directory structure.
