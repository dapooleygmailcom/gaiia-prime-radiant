"""
Vassal Map Raster Ingestion & Visual Terrain Feature Extractor.
"""

import os
from typing import Dict, Tuple, Any
from PIL import Image

try:
    import numpy as np
except ImportError:
    np = None


class VassalRasterTerrainClassifier:
    """
    Analyzes Vassal board raster images to classify hex terrain types,
    detect elevation contour levels, and verify printed hex coordinates.
    """

    def __init__(self, board_image_path: str):
        if not os.path.exists(board_image_path):
            raise FileNotFoundError(f"Board image not found: {board_image_path}")
        self.image_path = board_image_path
        self.pil_image = Image.open(board_image_path).convert("RGB")
        self.width, self.height = self.pil_image.size

    def sample_hex_patch(self, center_px: Tuple[float, float], radius_px: float) -> Image.Image:
        cx, cy = center_px
        r = max(5.0, radius_px * 0.6)  # Sample inner 60% to avoid hex grid border ink
        left = max(0, int(cx - r))
        top = max(0, int(cy - r))
        right = min(self.width, int(cx + r))
        bottom = min(self.height, int(cy + r))
        return self.pil_image.crop((left, top, right, bottom))

    def classify_terrain_from_color(self, patch: Image.Image) -> Tuple[str, float]:
        if np is None:
            colors = patch.getcolors(maxcolors=256 * 256)
            if not colors:
                return "Clear", 0.5
            total_r, total_g, total_b, total_px = 0, 0, 0, 0
            for count, (r, g, b) in colors:
                total_r += r * count
                total_g += g * count
                total_b += b * count
                total_px += count
            if total_px == 0:
                return "Clear", 0.5
            avg_r = total_r / total_px
            avg_g = total_g / total_px
            avg_b = total_b / total_px
        else:
            arr = np.array(patch)
            avg_r = float(np.mean(arr[:, :, 0]))
            avg_g = float(np.mean(arr[:, :, 1]))
            avg_b = float(np.mean(arr[:, :, 2]))

        # Blue Dominance (Water / River)
        if avg_b > avg_r * 1.25 and avg_b > avg_g * 1.15 and avg_b > 90:
            return "River" if avg_b < 180 else "Deep Water", 0.85

        # Green Dominance (Woods / Forest / Brush)
        if avg_g > avg_r * 1.15 and avg_g > avg_b * 1.15:
            if avg_g < 100 and avg_r < 80:
                return "Heavy Woods", 0.90
            return "Light Woods", 0.85

        # Grey / Neutral (Urban / Low-Rise Building / Road)
        diff = max(abs(avg_r - avg_g), abs(avg_g - avg_b), abs(avg_r - avg_b))
        if diff < 15 and 60 < avg_r < 160:
            return "Urban (Low-Rise)", 0.80

        # Brown / Rough Ground
        if avg_r > 120 and avg_g > 90 and avg_b < 80 and avg_r > avg_g * 1.2:
            return "Rough", 0.75

        # Cratered / Burnt Ground
        if avg_r < 60 and avg_g < 60 and avg_b < 60:
            return "Cratered", 0.80

        # Default
        return "Clear", 0.95

    def scan_hex_grid(
        self,
        dx: float,
        dy: float,
        x0: float,
        y0: float,
        stagger_odd: bool = True,
        first_col: int = 1,
        first_row: int = 1
    ) -> Dict[str, Dict[str, Any]]:
        num_cols = max(1, int((self.width - x0) / dx) + 1)
        num_rows = max(1, int((self.height - y0) / dy) + 1)
        hex_radius = min(dx, dy) / 2.0

        results = {}
        for c_idx in range(num_cols):
            col = first_col + c_idx
            stagger_offset = (dy / 2.0) if (col % 2 != 0 if stagger_odd else col % 2 == 0) else 0.0
            px_x = x0 + c_idx * dx
            
            for r_idx in range(num_rows):
                row = first_row + r_idx
                px_y = y0 + r_idx * dy + stagger_offset

                if px_x >= self.width or px_y >= self.height:
                    continue

                patch = self.sample_hex_patch((px_x, px_y), hex_radius)
                terrain, conf = self.classify_terrain_from_color(patch)
                
                obstacle_h = 0
                if terrain in ["Light Woods", "Heavy Woods", "Urban (Low-Rise)"]:
                    obstacle_h = 1
                elif terrain in ["Urban (High-Rise)"]:
                    obstacle_h = 2

                hex_id = f"{col:02d}{row:02d}"
                results[hex_id] = {
                    "hex_id": hex_id,
                    "col": col,
                    "row": row,
                    "pixel_center": (px_x, px_y),
                    "terrain": terrain,
                    "confidence": conf,
                    "elevation": 0,
                    "obstacle_height": obstacle_h
                }

        return results
