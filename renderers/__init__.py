"""
renderers/ — Pluggable Tile Renderer Backends
==============================================
Factory module that returns the correct renderer based on config.

Supported backends:
    - "synthetic"  : procedural gradient renderer (no external deps)
    - "blender"    : Blender headless CLI renderer (requires Blender)
"""

from .base import TileRenderer
from .synthetic import SyntheticRenderer
from .blender import BlenderRenderer


_REGISTRY: dict[str, type[TileRenderer]] = {
    "synthetic": SyntheticRenderer,
    "blender": BlenderRenderer,
}


def get_renderer(config: dict | None = None) -> TileRenderer:
    """
    Factory: create a renderer instance from a config dict.

    Args:
        config: Dict with at least a "type" key.
                If None or missing, defaults to synthetic.

    Examples:
        get_renderer({"type": "synthetic"})
        get_renderer({"type": "blender", "scene_file": "scene.blend"})
    """
    if config is None:
        config = {"type": "synthetic"}

    renderer_type = config.get("type", "synthetic")

    if renderer_type not in _REGISTRY:
        available = ", ".join(_REGISTRY.keys())
        raise ValueError(
            f"Unknown renderer type '{renderer_type}'. Available: {available}"
        )

    cls = _REGISTRY[renderer_type]

    # SyntheticRenderer needs no config; BlenderRenderer needs the full dict
    if renderer_type == "synthetic":
        return cls()
    else:
        return cls(config)
