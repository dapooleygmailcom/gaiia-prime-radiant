from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseScale(ABC):
    """
    Abstract base class defining the contract for a simulation scale.
    Each scale manages its own slice of the world state and turn clock.
    """
    
    @abstractmethod
    def initialize_state(self, initial_data: Dict[str, Any]) -> None:
        """Initializes the world state for this scale."""
        pass
        
    @abstractmethod
    def advance_turn(self) -> None:
        """Advances the clock and resolves end-of-turn mechanics for this scale."""
        pass
        
    @abstractmethod
    def get_state(self) -> Any:
        """Returns the current state representation for this scale."""
        pass
