from pydantic import BaseModel, Field

class SoftState(BaseModel):
    """
    Tracks float values (0.0 to 1.0) representing unit cohesion, morale,
    suppression, and supply variables that modulate probabilistic actions.
    """
    morale: float = Field(default=1.0, ge=0.0, le=1.0, description="Unit morale level")
    suppression: float = Field(default=0.0, ge=0.0, le=1.0, description="Current suppression level")
    command_cohesion: float = Field(default=1.0, ge=0.0, le=1.0, description="Command range alignment")
    supply_state: float = Field(default=1.0, ge=0.0, le=1.0, description="Logistical supply status")

    def apply_suppression(self, amount: float):
        """Increase suppression, bounded at 1.0."""
        added = round(min(1.0 - self.suppression, amount), 2)
        self.suppression = round(self.suppression + added, 2)
        # Suppressing a unit decreases its morale
        self.morale = round(max(0.0, self.morale - (added * 0.5)), 2)

    def decay_suppression(self, rate: float = 0.2):
        """Suppressions decays back to 0.0 at turn end."""
        self.suppression = round(max(0.0, self.suppression - rate), 2)

    def recover_morale(self, rate: float = 0.05):
        """Morale slowly recovers back to 1.0, unless suppressed."""
        if self.suppression == 0.0:
            self.morale = round(min(1.0, self.morale + rate), 2)

    def apply_casualty(self, ratio: float):
        """Applying casualties heavily impacts morale."""
        self.morale = max(0.0, self.morale - (ratio * 1.5))
