from typing import Dict, List
from pydantic import BaseModel
from engine.kernel.world_state_manager import WorldStateManager

class SupplyStock(BaseModel):
    id: str
    current_amount: float
    max_amount: float
    replenishment_rate: float
    
class SystemDynamicsModeller:
    """
    Implements stock-and-flow feedback loops.
    Simulates supply line depletion, configurable lag, and readiness degradation.
    """
    def __init__(self, wsm: WorldStateManager):
        self.wsm = wsm
        self.stocks: Dict[str, SupplyStock] = {}
        # Tracks delayed supply updates: turn_to_apply -> List of functions or events
        self.lag_queue: Dict[int, List[Dict]] = {}
        
    def add_stock(self, stock_id: str, max_amount: float, replenishment: float):
        self.stocks[stock_id] = SupplyStock(
            id=stock_id, 
            current_amount=max_amount, 
            max_amount=max_amount, 
            replenishment_rate=replenishment
        )

    def trigger_supply_cut(self, prefect_unit_id: str, severity: float, lag_turns: int = 2):
        """
        Schedules a supply cut event to affect a unit after a certain number of Prefect turns.
        """
        current_turn = self.wsm.current_state.prefect_state.turn
        target_turn = current_turn + lag_turns
        
        if target_turn not in self.lag_queue:
            self.lag_queue[target_turn] = []
            
        self.lag_queue[target_turn].append({
            "type": "SUPPLY_CUT",
            "unit_id": prefect_unit_id,
            "severity": severity
        })

    def advance_turn(self):
        """
        Advances the system dynamics simulation.
        Applies lagged effects scheduled for the current Prefect turn.
        """
        current_turn = self.wsm.current_state.prefect_state.turn
        
        # Apply stock replenishment
        for stock in self.stocks.values():
            stock.current_amount = min(stock.max_amount, stock.current_amount + stock.replenishment_rate)
            
        # Process lag queue
        if current_turn in self.lag_queue:
            for event in self.lag_queue[current_turn]:
                if event["type"] == "SUPPLY_CUT":
                    unit_id = event["unit_id"]
                    severity = event["severity"]
                    unit = self.wsm.current_state.prefect_state.units.get(unit_id)
                    if unit:
                        # Degrading supply level based on severity
                        unit.supply_level = max(0.0, unit.supply_level - severity)
                        
                        # Severe supply cuts might immediately impact soft states
                        if unit.supply_level < 0.5:
                            unit.soft_state.apply_suppression(0.2)
                            
            # Clean up processed queue
            del self.lag_queue[current_turn]
