class DoctrineProfileManager:
    """
    Retrieves and applies faction-specific tactical biases to influence planner action scoring.
    """
    def __init__(self):
        # In a full implementation, these profiles would be retrieved from RAG-Doll
        # For now, we stub the basic profiles as defined in the design doc.
        self.profiles = {
            "aggressive": {
                "fire": 1.5,
                "move": 0.8
            },
            "flexible": {
                "fire": 1.1,
                "move": 1.5
            },
            "guerrilla": {
                "fire": 1.0,
                "move": 2.0
            }
        }

    def get_action_modifier(self, faction: str, doctrine: str, action_type: str) -> float:
        """
        Returns a score modifier for a given action type based on the chosen doctrine.
        If doctrine or action type is not explicitly profiled, returns 1.0.
        """
        profile = self.profiles.get(doctrine, {})
        return profile.get(action_type, 1.0)
