"""URL parsing, path sanitization, and utility functions."""

import re
from pathlib import Path
from urllib.parse import ParseResult, unquote, urlparse

# MIME type to file extension mapping
CONTENT_TYPE_MAP: dict[str, str] = {
    # Text
    "text/html": ".html",
    "text/css": ".css",
    "text/javascript": ".js",
    "text/plain": ".txt",
    "text/xml": ".xml",
    # Application
    "application/javascript": ".js",
    "application/x-javascript": ".js",
    "application/json": ".json",
    "application/xml": ".xml",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/gzip": ".gz",
    "application/wasm": ".wasm",
    "application/manifest+json": ".webmanifest",
    # Images
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
    "image/avif": ".avif",
    # Fonts
    "font/woff": ".woff",
    "font/woff2": ".woff2",
    "font/ttf": ".ttf",
    "font/otf": ".otf",
    "application/font-woff": ".woff",
    "application/font-woff2": ".woff2",
    "application/x-font-woff": ".woff",
    "application/x-font-ttf": ".ttf",
    "application/vnd.ms-fontobject": ".eot",
    # Audio/Video
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/ogg": ".ogg",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/ogg": ".ogv",
}

# Characters invalid in filenames (Windows-focused for cross-platform compat)
INVALID_CHARS = re.compile(r'[<>:"|?*\x00-\x1f\\]')

# Windows reserved names
WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})

MAX_PATH_COMPONENT = 100
MAX_FILENAME_LENGTH = 200


def parse_url(url: str) -> ParseResult:
    """Validate and parse a URL.

    Args:
        url: The URL string to parse.

    Returns:
        Parsed URL components.

    Raises:
        ValueError: If URL is invalid or missing scheme/host.
    """
    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)

    if not parsed.netloc:
        raise ValueError(f"Invalid URL: missing host in '{url}'")

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: '{parsed.scheme}' (must be http or https)")

    return parsed


def sanitize_path_component(name: str) -> str:
    """Clean a path component for filesystem safety.

    Args:
        name: Raw path component from URL.

    Returns:
        Sanitized component safe for filesystem use.
    """
    if not name:
        return "_"

    # Remove invalid characters
    name = INVALID_CHARS.sub("_", name)

    # Handle Windows reserved names
    name_upper = name.upper()
    # Check both exact match and with extension (e.g., CON.txt)
    base_name = name_upper.split(".")[0]
    if base_name in WINDOWS_RESERVED:
        name = f"_{name}"

    # Handle empty or dot-only names
    if not name or name in (".", ".."):
        name = "_"

    # Truncate if too long
    if len(name) > MAX_PATH_COMPONENT:
        stem, ext = _split_extension(name)
        max_stem = MAX_PATH_COMPONENT - len(ext)
        name = stem[:max_stem] + ext

    return name


def _split_extension(filename: str) -> tuple[str, str]:
    """Split filename into stem and extension.

    Args:
        filename: The filename to split.

    Returns:
        Tuple of (stem, extension) where extension includes the dot.
    """
    if "." not in filename:
        return filename, ""

    # Handle double extensions like .min.js
    parts = filename.rsplit(".", 1)
    return parts[0], "." + parts[1]


def infer_extension(path: str, content_type: str) -> str:
    """Add file extension based on content-type if path lacks one.

    Args:
        path: URL path that may lack an extension.
        content_type: Content-Type header value.

    Returns:
        Path with extension added if needed.
    """
    filename = Path(path).name

    # Check if already has an extension
    if "." in filename:
        return path

    # Parse content-type (ignore charset, boundary, etc.)
    mime = content_type.split(";")[0].strip().lower()
    ext = CONTENT_TYPE_MAP.get(mime, "")

    return path + ext


def is_same_origin(url: str, base_url: str) -> bool:
    """Check if a URL is same-origin as the base URL.

    Args:
        url: URL to check.
        base_url: Base URL to compare against.

    Returns:
        True if both URLs have the same origin (scheme + host).
    """
    parsed_url = urlparse(url)
    parsed_base = urlparse(base_url)
    return parsed_url.netloc == parsed_base.netloc


def url_to_local_path(url: str, output_dir: Path) -> Path:
    """Convert a URL to a local file path preserving directory structure.

    Args:
        url: Full URL of the resource.
        output_dir: Base output directory.

    Returns:
        Local path where the resource should be saved.
    """
    parsed = urlparse(url)

    # Get host (strip port for directory name)
    host = parsed.netloc.split(":")[0]
    host = sanitize_path_component(host)

    # Get path and decode URL encoding
    url_path = unquote(parsed.path)

    # Handle root path
    if not url_path or url_path == "/":
        url_path = "/index.html"

    # Handle paths ending with / (directory index)
    if url_path.endswith("/"):
        url_path = url_path + "index.html"

    # Split into components and sanitize each
    path_parts = url_path.strip("/").split("/")
    sanitized_parts = [sanitize_path_component(part) for part in path_parts]

    # Build full local path
    local_path = output_dir / host / Path(*sanitized_parts)

    return local_path


def should_skip_url(url: str) -> bool:
    """Check if a URL should be skipped (data:, blob:, etc.).

    Args:
        url: URL to check.

    Returns:
        True if URL should be skipped.
    """
    skip_prefixes = ("data:", "blob:", "about:", "javascript:", "chrome:", "chrome-extension:")
    return url.startswith(skip_prefixes)
