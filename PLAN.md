# pagesource Implementation Plan

## Overview

Build a CLI tool that captures all network resources loaded by a webpage (similar to browser DevTools Sources tab) and saves them locally preserving the original directory structure.

---

## 1. High-Level Flow

```
URL Input → Launch Browser → Navigate to Page → Capture Network Responses → Download Content → Save with Directory Structure
```

### Detailed Flow:

1. **CLI Entry** (`cli.py`)
   - Parse arguments: `url`, `--output/-o`, `--wait`, `--include-external`
   - Validate URL format
   - Create output directory if needed
   - Call async browser capture function using `asyncio.run()`

2. **Browser Capture** (`browser.py`)
   - Launch headless Chromium via Playwright
   - Register response handler BEFORE navigation
   - Navigate to URL and wait for `networkidle`
   - Apply additional wait time if `--wait` specified
   - Collect all captured responses
   - Close browser and return resource list

3. **Download & Save** (`downloader.py`)
   - For each captured resource:
     - Parse URL to extract host and path
     - Filter based on `--include-external` flag
     - Build local file path preserving structure
     - Write content to disk
   - Display progress with Rich

4. **Utilities** (`utils.py`)
   - URL parsing and validation
   - Path sanitization
   - Content-type to extension mapping
   - Filename deduplication

---

## 2. Network Capture Strategy

### Approach: `page.on("response", handler)`

Using response events (NOT route interception) because:
- We want to **observe** all responses, not modify them
- Route interception requires explicit `route.continue()` which adds complexity
- Response events give us access to the actual response body after it's received
- Works for all resource types: documents, scripts, styles, images, fonts, XHR, etc.

### Implementation:

```python
# Pseudocode
captured_resources = []

async def handle_response(response):
    # Skip non-successful responses
    if not response.ok:
        return

    # Skip data: and blob: URLs
    url = response.url
    if url.startswith(('data:', 'blob:')):
        return

    try:
        body = await response.body()
        captured_resources.append({
            'url': url,
            'content_type': response.headers.get('content-type', ''),
            'body': body
        })
    except Exception:
        # Log warning, continue
        pass

page.on("response", handle_response)
await page.goto(url, wait_until="networkidle")
```

### Why `networkidle`?

- Waits until no network connections for 500ms
- Catches lazy-loaded resources, JS-fetched content
- Combined with optional `--wait` for SPAs that load content after idle

---

## 3. Directory Structure Extraction

### URL to Local Path Mapping

Given: `https://example.com/assets/js/app.min.js?v=1.2.3`

Output structure:
```
output/
└── example.com/
    └── assets/
        └── js/
            └── app.min.js
```

### Algorithm:

1. Parse URL with `urllib.parse.urlparse()`
2. Extract `netloc` (hostname) → top-level directory
3. Extract `path` → subdirectories + filename
4. Strip query string (`?v=1.2.3`)
5. Handle edge cases (see section 4)

### Path Components:

```python
from urllib.parse import urlparse, unquote

parsed = urlparse(url)
host = parsed.netloc          # "example.com" or "cdn.example.com:8080"
path = unquote(parsed.path)   # "/assets/js/app.min.js"

# Clean host (remove port for directory name)
host_clean = host.split(':')[0]

# Build local path
local_path = output_dir / host_clean / path.lstrip('/')
```

---

## 4. Edge Case Handling

### 4.1 Query Strings in URLs

**Problem:** `style.css?v=123` should save as `style.css`

**Solution:** Use `urlparse().path` which excludes query string automatically.

### 4.2 URLs Without File Extensions

**Problem:** `/api/users` or `/page` with no extension

**Solution:** Infer extension from `Content-Type` header:

```python
CONTENT_TYPE_MAP = {
    'text/html': '.html',
    'text/css': '.css',
    'text/javascript': '.js',
    'application/javascript': '.js',
    'application/json': '.json',
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/gif': '.gif',
    'image/svg+xml': '.svg',
    'image/webp': '.webp',
    'font/woff': '.woff',
    'font/woff2': '.woff2',
    'application/font-woff': '.woff',
    'application/font-woff2': '.woff2',
    # ... etc
}

def infer_extension(path: str, content_type: str) -> str:
    """Add extension if path lacks one."""
    if '.' in Path(path).name:
        return path  # Already has extension

    # Parse content-type (ignore charset etc)
    mime = content_type.split(';')[0].strip()
    ext = CONTENT_TYPE_MAP.get(mime, '')
    return path + ext
```

### 4.3 Very Long Paths

**Problem:** Some URLs have extremely long paths or filenames (>255 chars)

**Solution:** Truncate components while preserving uniqueness:

```python
MAX_FILENAME_LENGTH = 200  # Leave room for dedup suffix
MAX_PATH_COMPONENT = 100

def truncate_path(path: str) -> str:
    parts = Path(path).parts
    truncated = []
    for part in parts:
        if len(part) > MAX_PATH_COMPONENT:
            # Keep extension if present
            stem, ext = os.path.splitext(part)
            max_stem = MAX_PATH_COMPONENT - len(ext)
            part = stem[:max_stem] + ext
        truncated.append(part)
    return str(Path(*truncated))
```

### 4.4 Duplicate Filenames

**Problem:** Multiple resources resolve to same local path

**Solution:** Track used paths and add numeric suffix:

```python
used_paths: set[Path] = set()

def deduplicate_path(path: Path) -> Path:
    if path not in used_paths:
        used_paths.add(path)
        return path

    stem = path.stem
    ext = path.suffix
    counter = 1
    while True:
        new_path = path.with_name(f"{stem}_{counter}{ext}")
        if new_path not in used_paths:
            used_paths.add(new_path)
            return new_path
        counter += 1
```

### 4.5 data: and blob: URLs

**Problem:** These are inline data, not fetchable URLs

**Solution:** Skip early in response handler:

```python
if url.startswith(('data:', 'blob:', 'about:')):
    return  # Skip
```

### 4.6 Failed Requests

**Problem:** Some resources fail to load (404, timeout, CORS)

**Solution:** Log warning and continue:

```python
try:
    body = await response.body()
except Exception as e:
    console.print(f"[yellow]Warning: Could not fetch {url}: {e}[/yellow]")
    return
```

### 4.7 External vs Same-Origin Resources

**Problem:** User may want only same-origin resources, or include CDNs

**Solution:** `--include-external` flag controls behavior:

```python
def is_same_origin(resource_url: str, page_url: str) -> bool:
    return urlparse(resource_url).netloc == urlparse(page_url).netloc

# In downloader
if not include_external and not is_same_origin(resource.url, target_url):
    continue  # Skip external
```

### 4.8 Path Traversal / Invalid Characters

**Problem:** URLs might contain `..`, special chars, or reserved Windows names

**Solution:** Sanitize path components:

```python
import re

INVALID_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
WINDOWS_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'LPT1', ...}

def sanitize_component(name: str) -> str:
    # Remove invalid characters
    name = INVALID_CHARS.sub('_', name)
    # Handle Windows reserved names
    if name.upper() in WINDOWS_RESERVED:
        name = f"_{name}"
    # Handle empty or dot-only names
    if not name or name in ('.', '..'):
        name = '_'
    return name
```

---

## 5. pyproject.toml Configuration

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pagesource"
version = "0.1.0"
description = "Capture all resources from a webpage like browser DevTools Sources tab"
readme = "README.md"
requires-python = ">=3.10"
license = "MIT"
authors = [
    { name = "Your Name", email = "you@example.com" }
]
keywords = ["web", "scraping", "playwright", "cli"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "playwright>=1.40.0",
    "typer>=0.9.0",
    "rich>=13.0.0",
    "httpx>=0.25.0",
]

[project.scripts]
pagesource = "pagesource.cli:main"

[project.urls]
Homepage = "https://github.com/yourusername/pagesource"
Repository = "https://github.com/yourusername/pagesource"

[tool.hatch.build.targets.wheel]
packages = ["src/pagesource"]
```

### Installation Methods:

```bash
# pip (editable for development)
pip install -e .

# pip (from source)
pip install .

# uv
uv pip install -e .

# After install, must run:
playwright install chromium
```

---

## 6. Module Design

### `utils.py`

Functions:
- `parse_url(url: str) -> ParseResult` - Validate and parse URL
- `url_to_local_path(url: str, base_url: str, output_dir: Path) -> Path` - Convert URL to local file path
- `sanitize_path_component(name: str) -> str` - Clean path component for filesystem
- `infer_extension(path: str, content_type: str) -> str` - Add extension based on content-type
- `is_same_origin(url: str, base_url: str) -> bool` - Check if URL is same origin

Data:
- `CONTENT_TYPE_MAP: dict[str, str]` - MIME type to extension mapping

### `browser.py`

Classes:
- `CapturedResource` - Dataclass holding url, content_type, body

Functions:
- `async capture_page_resources(url: str, wait_time: int = 0) -> list[CapturedResource]` - Main capture function

### `downloader.py`

Classes:
- `ResourceSaver` - Manages path deduplication and saving

Functions:
- `async save_resources(resources: list[CapturedResource], output_dir: Path, base_url: str, include_external: bool) -> int` - Save all resources, return count

### `cli.py`

Functions:
- `main(url: str, output: Path, wait: int, include_external: bool) -> None` - CLI entry point

---

## 7. Progress Display

Use Rich for user-friendly output:

```python
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# During capture
with console.status("[bold blue]Loading page and capturing resources..."):
    resources = await capture_page_resources(url, wait)

console.print(f"[green]✓[/green] Captured {len(resources)} resources")

# During save
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    transient=True,
) as progress:
    task = progress.add_task("Saving resources...", total=len(resources))
    for resource in resources:
        # save...
        progress.advance(task)
```

---

## 8. Error Handling Strategy

1. **URL Validation Error** → Exit with helpful message
2. **Browser Launch Failure** → Exit with "run playwright install chromium" hint
3. **Page Load Timeout** → Exit with timeout message
4. **Individual Resource Failure** → Log warning, continue with others
5. **File Write Failure** → Log warning, continue with others
6. **Keyboard Interrupt** → Clean up browser, exit gracefully

---

## 9. Testing Strategy

Manual testing with various site types:
1. Simple static site (basic HTML, CSS, JS)
2. SPA with lazy loading (React/Vue app)
3. Site with many external resources (CDNs)
4. Site with long/weird URLs
5. Site with duplicate resource names

---

## 10. Implementation Order

1. **pyproject.toml** - Package configuration
2. **src/pagesource/__init__.py** - Package init with version
3. **src/pagesource/utils.py** - URL parsing, path utilities
4. **src/pagesource/browser.py** - Playwright capture logic
5. **src/pagesource/downloader.py** - Save resources to disk
6. **src/pagesource/cli.py** - Typer CLI wiring
7. **README.md** - Usage documentation

Each module should be testable in isolation before integration.
