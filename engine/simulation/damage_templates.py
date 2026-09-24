"""
Authentic 2D Damage Matrix Templates for Renegade Legion Centurion
Every weapon and missile ammo type is defined as a 2D binary matrix (Rows x Cols) of Damage [#] / No Damage [.].
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class DamageTemplate(BaseModel):
    name: str
    category: str
    description: str
    grid_matrix: List[List[int]] = Field(description="2D matrix (rows x cols) where 1 = Damage, 0 = No Damage")
    center_col: int = Field(description="0-indexed column corresponding to the aim/impact point")

    @property
    def width(self) -> int:
        return len(self.grid_matrix[0]) if self.grid_matrix else 0

    @property
    def height(self) -> int:
        return len(self.grid_matrix)

    @property
    def penetration_array(self) -> List[int]:
        """Calculates penetration depth per column by summing damage rows."""
        if not self.grid_matrix:
            return []
        cols = self.width
        depths = [0] * cols
        for r in range(self.height):
            for c in range(cols):
                if self.grid_matrix[r][c] == 1:
                    depths[c] += 1
        return depths

    def get_penetration_at_offset(self, offset: int) -> int:
        c_idx = self.center_col + offset
        depths = self.penetration_array
        if 0 <= c_idx < len(depths):
            return depths[c_idx]
        return 0

    def render_ascii(self) -> str:
        """Renders an authentic 2D ASCII damage grid diagram."""
        lines = []
        lines.append(f"  +-- {self.name.upper()} :: {self.width}x{self.height} DAMAGE MATRIX --+")
        lines.append(f"  | Type: {self.category} | Impact Center: Col {self.center_col+1} | Total Boxes: {sum(self.penetration_array)}")
        
        # Header with column offsets
        offsets = [c - self.center_col for c in range(self.width)]
        hdr = "  | Col Offsets: " + "".join(f"{o:+2d} " for o in offsets) + "|"
        lines.append(hdr)
        lines.append("  | " + "-" * (len(hdr) - 4) + " |")
        
        for r_idx, row in enumerate(self.grid_matrix):
            row_str = f"  | Row {r_idx+1:2d}:      "
            for c_val in row:
                row_str += "[#] " if c_val == 1 else " .  "
            row_str += "|"
            lines.append(row_str)
            
        lines.append("  | " + "-" * (len(hdr) - 4) + " |")
        lines.append("  | Depth/Col:   " + "".join(f"{d:2d} " for d in self.penetration_array) + "|")
        lines.append("  +" + "-" * (len(hdr) - 4) + "+")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# AUTHORITATIVE WEAPON & AMMO 2D DAMAGE MATRIX REGISTRY
# ══════════════════════════════════════════════════════════════════════════

TEMPLATE_REGISTRY: Dict[str, DamageTemplate] = {
    # 1. TVLG Guided Missile (5x5 Inverted-T Grid)
    "TVLG": DamageTemplate(
        name="TVLG Guided Missile",
        category="Guided Heavy Missile",
        description="5-column wide surface blast (2 rows) with a 3-row central penetrator stem (total 5 depth at impact col).",
        center_col=2,
        grid_matrix=[
            [1, 1, 1, 1, 1],  # Row 1 (5 cols wide)
            [1, 1, 1, 1, 1],  # Row 2 (5 cols wide)
            [0, 0, 1, 0, 0],  # Row 3 (center only)
            [0, 0, 1, 0, 0],  # Row 4 (center only)
            [0, 0, 1, 0, 0],  # Row 5 (center only)
        ]
    ),

    # 2. SMLM Guided Missile (4x2 Dual-Penetrator Grid)
    "SMLM": DamageTemplate(
        name="SMLM Guided Missile",
        category="Guided Light Missile",
        description="4-column wide blast (1 row) with dual 2-row penetrators at columns 2 and 3.",
        center_col=1,
        grid_matrix=[
            [1, 1, 1, 1],  # Row 1 (4 cols wide)
            [0, 1, 1, 0],  # Row 2 (inner cols only)
        ]
    ),

    # 3. 150mm Heavy Gauss Cannon (3x4 Wedge Grid)
    "150mm": DamageTemplate(
        name="150mm Heavy Gauss Cannon",
        category="Kinetic / Mass Driver",
        description="Heavy kinetic slug displacing 2 rows on flanks and 4 rows deep at the central apex.",
        center_col=1,
        grid_matrix=[
            [1, 1, 1],  # Row 1
            [1, 1, 1],  # Row 2
            [0, 1, 0],  # Row 3 (center only)
            [0, 1, 0],  # Row 4 (center only)
        ]
    ),

    # 4. 50mm Medium Gauss Cannon (3x2 Wedge Grid)
    "50mm": DamageTemplate(
        name="50mm Medium Gauss Cannon",
        category="Kinetic / Mass Driver",
        description="Medium kinetic projectile displacing 1 row on flanks and 2 rows at center.",
        center_col=1,
        grid_matrix=[
            [1, 1, 1],  # Row 1
            [0, 1, 0],  # Row 2 (center only)
        ]
    ),

    # 5. 200mm Super-Heavy Gauss / Siege Mass Driver (3x6 Deep Spearhead Grid)
    "200mm": DamageTemplate(
        name="200mm Super-Heavy Gauss Cannon",
        category="Kinetic / Mass Driver",
        description="Massive armor-piercing kinetic dart displacing 2 rows on flanks and punching 6 rows deep at center.",
        center_col=1,
        grid_matrix=[
            [1, 1, 1],  # Row 1
            [1, 1, 1],  # Row 2
            [0, 1, 0],  # Row 3
            [0, 1, 0],  # Row 4
            [0, 1, 0],  # Row 5
            [0, 1, 0],  # Row 6
        ]
    ),

    # 6. 5/6 Heavy Laser (1x5 Needle Beam Grid)
    "5/6 Laser": DamageTemplate(
        name="5/6 Heavy Laser",
        category="Direct Energy Thermal Beam",
        description="Coherent high-energy photon stream burning 5 rows deep in a single pinpoint column.",
        center_col=0,
        grid_matrix=[
            [1],  # Row 1
            [1],  # Row 2
            [1],  # Row 3
            [1],  # Row 4
            [1],  # Row 5
        ]
    ),

    # 7. 3/6 Medium Laser (1x4 Needle Beam Grid)
    "3/6 Laser": DamageTemplate(
        name="3/6 Medium Laser",
        category="Direct Energy Thermal Beam",
        description="Medium thermal laser stream burning 4 rows deep in a single pinpoint column.",
        center_col=0,
        grid_matrix=[
            [1],  # Row 1
            [1],  # Row 2
            [1],  # Row 3
            [1],  # Row 4
        ]
    ),

    # 8. Heavy Particle Projection Cannon / Plasma (3x3 Diamond Grid)
    "Heavy PPC": DamageTemplate(
        name="Heavy PPC / Plasma Cannon",
        category="High-Energy Particle Blast",
        description="Diamond-shaped ionized plasma blast melting a cross-section of armor.",
        center_col=1,
        grid_matrix=[
            [0, 1, 0],  # Row 1
            [1, 1, 1],  # Row 2
            [0, 1, 0],  # Row 3
        ]
    ),

    # 9. Vulcan III Point Defense (5x1 Linear Shrapnel Grid)
    "Vulcan III": DamageTemplate(
        name="Vulcan III Point Defense",
        category="Rapid-Fire Rotary Point Defense",
        description="High-velocity anti-missile pellet spread scouring 1 row deep across 5 adjacent columns.",
        center_col=2,
        grid_matrix=[
            [1, 1, 1, 1, 1],  # Row 1
        ]
    ),

    # 10. Vulcan II Point Defense (3x1 Linear Shrapnel Grid)
    "Vulcan II": DamageTemplate(
        name="Vulcan II Point Defense",
        category="Rapid-Fire Rotary Point Defense",
        description="Compact anti-missile pellet spread scouring 1 row deep across 3 adjacent columns.",
        center_col=1,
        grid_matrix=[
            [1, 1, 1],  # Row 1
        ]
    ),

    # 11. Heavy Mortar / Artillery HE (5x3 Hemispherical Blast Crater Grid)
    "Heavy Mortar": DamageTemplate(
        name="Heavy Mortar / Artillery HE",
        category="Indirect High-Explosive Shell",
        description="Hemispherical explosive crater carving wide surface damage graduating towards a 3-row center.",
        center_col=2,
        grid_matrix=[
            [1, 1, 1, 1, 1],  # Row 1 (5 cols wide)
            [0, 1, 1, 1, 0],  # Row 2 (3 cols wide)
            [0, 0, 1, 0, 0],  # Row 3 (center only)
        ]
    ),

    # 12. Heavy Armor-Piercing Bomb / Penetrator (3x5 T-Stem Grid)
    "AP Bomb": DamageTemplate(
        name="Armor-Piercing Guided Bomb",
        category="Heavy Kinetic Ordnance",
        description="Heavy ordnance creating a 3-column shock ring with a 5-row deep penetrator rod.",
        center_col=1,
        grid_matrix=[
            [1, 1, 1],  # Row 1
            [0, 1, 0],  # Row 2
            [0, 1, 0],  # Row 3
            [0, 1, 0],  # Row 4
            [0, 1, 0],  # Row 5
        ]
    )
}


def get_template(name: str) -> Optional[DamageTemplate]:
    """Retrieves damage template by weapon or ammo name."""
    low = name.lower()
    for key, tmpl in TEMPLATE_REGISTRY.items():
        if key.lower() in low or low in key.lower():
            return tmpl
    if "laser" in low:
        return TEMPLATE_REGISTRY.get("5/6 Laser")
    if "gauss" in low or "cannon" in low:
        return TEMPLATE_REGISTRY.get("150mm")
    if "vulcan" in low or "pd" in low:
        return TEMPLATE_REGISTRY.get("Vulcan III")
    if "tvlg" in low or "missile" in low:
        return TEMPLATE_REGISTRY.get("TVLG")
    return None
