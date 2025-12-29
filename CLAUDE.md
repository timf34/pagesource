# pagesource

A Python CLI tool that captures all resources loaded by a webpage (like browser DevTools Sources tab) and saves them with original directory structure.

## Tech Stack
- Python 3.10+
- Playwright (async) for browser automation
- Typer for CLI
- Rich for progress display
- httpx as fallback for downloads

## Project Structure
src/pagesource/
├── __init__.py
├── cli.py          # Typer CLI entry point
├── browser.py      # Playwright page load + network capture
├── downloader.py   # Save resources to disk with structure
└── utils.py        # URL parsing, path sanitization

## Code Style
- Use async/await throughout browser code
- Type hints on all functions
- Docstrings on public functions
- Keep functions small and focused

## CLI Interface
pagesource <url>                    # Basic usage
pagesource <url> -o ./output        # Custom output dir
pagesource <url> --wait 5           # Extra wait time for JS
pagesource <url> --include-external # Include CDN assets

## Edge Cases to Handle
- Query strings in URLs (strip them, use base filename)
- URLs without file extensions (infer from content-type)
- Very long paths (truncate sensibly)
- Duplicate filenames in same directory
- data: and blob: URLs (skip)
- Failed requests (log warning, continue)

## Package Distribution
- Use pyproject.toml with hatchling
- Entry point: pagesource = "pagesource.cli:main"
- README should note: run `playwright install chromium` after install
```

Then run Claude Code with this prompt:
```
Read the CLAUDE.md file. I want to build this tool from scratch.

Before writing any code, think hard and create a detailed implementation plan. Consider:

1. The exact flow: URL input → browser load → capture responses → download → save with structure
2. How to capture network responses in Playwright (page.on("response", ...) vs route interception)
3. How to extract the URL path and create the local directory structure
4. How to handle the edge cases listed in CLAUDE.md
5. What the pyproject.toml needs for pip/uv installation

Write the plan to a file called PLAN.md. Do not write any code yet.
```

### Step 2: Implementation

Once you've reviewed and approved the plan:
```
Read PLAN.md. Now implement the tool following that plan.

Start with:
1. pyproject.toml (make it pip and uv installable)
2. src/pagesource/utils.py (URL parsing, path helpers)
3. src/pagesource/browser.py (Playwright capture logic)
4. src/pagesource/downloader.py (save to disk)
5. src/pagesource/cli.py (wire it together)
6. README.md with usage instructions

After each file, verify it has no syntax errors. When done, run `pip install -e .` and test with a real URL.