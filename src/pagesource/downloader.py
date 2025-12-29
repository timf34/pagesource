"""Save captured resources to disk with directory structure."""

from pathlib import Path

from rich.console import Console

from .browser import CapturedResource
from .utils import infer_extension, is_same_origin, url_to_local_path


class ResourceSaver:
    """Manages saving resources with path deduplication."""

    def __init__(self, output_dir: Path, base_url: str, include_external: bool = False):
        """Initialize the resource saver.

        Args:
            output_dir: Base directory for saved resources.
            base_url: Original page URL for same-origin checks.
            include_external: Whether to save external (CDN) resources.
        """
        self.output_dir = output_dir
        self.base_url = base_url
        self.include_external = include_external
        self.used_paths: set[Path] = set()
        self.console = Console()

    def _deduplicate_path(self, path: Path) -> Path:
        """Get a unique path by adding numeric suffix if needed.

        Args:
            path: Desired file path.

        Returns:
            Path that doesn't conflict with already-used paths.
        """
        if path not in self.used_paths:
            self.used_paths.add(path)
            return path

        stem = path.stem
        ext = path.suffix
        parent = path.parent
        counter = 1

        while True:
            new_path = parent / f"{stem}_{counter}{ext}"
            if new_path not in self.used_paths:
                self.used_paths.add(new_path)
                return new_path
            counter += 1

    def save_resource(self, resource: CapturedResource) -> Path | None:
        """Save a single resource to disk.

        Args:
            resource: The captured resource to save.

        Returns:
            Path where resource was saved, or None if skipped.
        """
        # Filter external resources if not included
        if not self.include_external and not is_same_origin(resource.url, self.base_url):
            return None

        # Get base path from URL
        local_path = url_to_local_path(resource.url, self.output_dir)

        # Infer extension from content-type if needed
        path_str = str(local_path)
        path_with_ext = infer_extension(path_str, resource.content_type)
        local_path = Path(path_with_ext)

        # Deduplicate if path already used
        local_path = self._deduplicate_path(local_path)

        # Create parent directories
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        try:
            local_path.write_bytes(resource.body)
            return local_path
        except OSError as e:
            self.console.print(f"[yellow]Warning: Could not save {resource.url}: {e}[/yellow]")
            return None


def save_resources(
    resources: list[CapturedResource],
    output_dir: Path,
    base_url: str,
    include_external: bool = False,
) -> tuple[int, int]:
    """Save all captured resources to disk.

    Args:
        resources: List of captured resources.
        output_dir: Base directory for saved resources.
        base_url: Original page URL for same-origin checks.
        include_external: Whether to save external (CDN) resources.

    Returns:
        Tuple of (saved_count, skipped_count).
    """
    saver = ResourceSaver(output_dir, base_url, include_external)

    saved = 0
    skipped = 0

    for resource in resources:
        result = saver.save_resource(resource)
        if result is not None:
            saved += 1
        else:
            skipped += 1

    return saved, skipped
