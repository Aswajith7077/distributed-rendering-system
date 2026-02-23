"""
Operator: FrameSplit
--------------------
Mimics the 'Frame Split' operator from the BigEarth pipeline.
Divides the full image into an N x M grid of tile regions.

Each tile is described as:
  { 'id': int, 'x': int, 'y': int, 'width': int, 'height': int }
"""


def split(img_width: int, img_height: int, rows: int, cols: int) -> list[dict]:
    """
    Splits an image of (img_width x img_height) into a (rows x cols) grid.
    Returns a list of tile descriptor dicts.
    """
    tiles = []
    tile_w = img_width // cols
    tile_h = img_height // rows

    tile_id = 0
    for row in range(rows):
        for col in range(cols):
            x = col * tile_w
            y = row * tile_h

            # Last column/row absorbs any remainder pixels
            w = tile_w if col < cols - 1 else img_width - x
            h = tile_h if row < rows - 1 else img_height - y

            tiles.append({
                "id": tile_id,
                "x": x,
                "y": y,
                "width": w,
                "height": h,
            })
            tile_id += 1

    return tiles
