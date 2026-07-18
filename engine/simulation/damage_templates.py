from typing import List, Dict
from pydantic import BaseModel

class DamageTemplate(BaseModel):
    name: str
    penetration_array: List[int]
    center_idx: int
    
    def get_penetration_at_offset(self, offset: int) -> int:
        """
        Returns the penetration depth at a given offset from the center.
        Offset 0 is the center_idx.
        """
        idx = self.center_idx + offset
        if 0 <= idx < len(self.penetration_array):
            return self.penetration_array[idx]
        return 0

# Hardcoded standard templates for demonstration / Phase 4 logic testing
TEMPLATE_REGISTRY: Dict[str, DamageTemplate] = {
    "150mm": DamageTemplate(
        name="150mm",
        # Example shape: drops 2, 4, 2
        penetration_array=[2, 4, 2],
        center_idx=1
    ),
    "50mm": DamageTemplate(
        name="50mm",
        # Example shape: drops 1, 2, 1
        penetration_array=[1, 2, 1],
        center_idx=1
    ),
    "Laser": DamageTemplate(
        name="Laser",
        # Lasers tend to penetrate deeply in a single column
        penetration_array=[5],
        center_idx=0
    ),
    "Vulcan III": DamageTemplate(
        name="Vulcan III",
        # Wide spread but shallow penetration
        penetration_array=[1, 1, 1, 1, 1],
        center_idx=2
    ),
    "TVLG": DamageTemplate(
        name="TVLG",
        # Missile hit, slightly wider spread
        penetration_array=[1, 3, 3, 1],
        center_idx=1 # Note: center is slightly off-center
    )
}
