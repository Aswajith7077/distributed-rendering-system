"""
Operator: Stitch
----------------
Mimics the 'Image Stitch' operator from the BigEarth pipeline.
Takes a list of rendered tile image paths and pastes them into a
single full-resolution output image.
"""

import os
from PIL import Image


def stitch(
    tile_results: list[dict], img_width: int, img_height: int, output_path: str
) -> str:
    """
    Assembles tile images into a final stitched image.

    Args:
        tile_results: List of dicts with keys: 'path', 'x', 'y'
        img_width:    Full image width in pixels
        img_height:   Full image height in pixels
        output_path:  Where to save the final image

    Returns:
        The output_path of the saved image.
    """
    canvas = Image.new("RGB", (img_width, img_height), color=(0, 0, 0))

    for tile in tile_results:
        tile_img = Image.open(tile["path"])
        canvas.paste(tile_img, (tile["x"], tile["y"]))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    canvas.save(output_path)
    return output_path
