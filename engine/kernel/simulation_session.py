import asyncio
from typing import Dict
from engine.kernel.world_state_manager import WorldStateManager
from engine.kernel.cross_scale_event_bus import CrossScaleEventBus

class SimulationSession:
    """
    Manages the Parallel Temporal Control using asyncio.
    Synchronizes actors at Leviathan and Prefect boundaries.
    """
    def __init__(self, simulation_id: str):
        self.wsm = WorldStateManager(simulation_id)
        self.ceb = CrossScaleEventBus(self.wsm)
        
        # Gates
        self.leviathan_gate = asyncio.Barrier(parties=1)
        self.prefect_gate = asyncio.Barrier(parties=1)
        
        self.active_tasks: Dict[str, asyncio.Task] = {}
        
        # Scale clock
        self.tactical_time_minutes = 0
        self.prefect_time_hours = 0
        
        # Config (e.g. how many tactical turns per operational turn)
        self.minutes_per_prefect_turn = 60

    async def _wait_at_leviathan_gate(self):
        """Wait for all tactical scales to finish one minute of game time."""
        if self.leviathan_gate.parties > 0:
            await self.leviathan_gate.wait()
            
            # The last actor to arrive will release the barrier, but we also want the CEB to process here.
            # In a real system, the CEB might process all pending influence vectors here.

    async def run_centurion_actor(self, engagement_id: str, max_turns: int = 5):
        """Runs the Centurion tactical simulation actor loop (1 min/turn)."""
        scale = self.wsm.current_state.centurion_engagements.get(engagement_id)
        if not scale: return
        
        while scale.turn < max_turns:
            # 1. Action Planner evaluates
            # 2. Outcome Modeller resolves
            # 3. Advance clock
            scale.turn += 1
            print(f"[Centurion {engagement_id}] Turn {scale.turn} complete.")
            await asyncio.sleep(0.1)
            
            # Wait for other tactical actors (Leviathan, Interceptor)
            await self._wait_at_leviathan_gate()

    async def run_interceptor_actor(self, engagement_id: str, max_turns: int = 5):
        """Runs the Interceptor tactical simulation actor loop (1 min/turn)."""
        scale = self.wsm.current_state.interceptor_engagements.get(engagement_id)
        if not scale: return
        
        while scale.turn < max_turns:
            scale.turn += 1
            print(f"[Interceptor {engagement_id}] Turn {scale.turn} complete.")
            await asyncio.sleep(0.1)
            await self._wait_at_leviathan_gate()

    async def run_leviathan_actor(self, engagement_id: str, max_turns: int = 5):
        """Runs the Leviathan tactical simulation actor loop (1 min/turn)."""
        scale = self.wsm.current_state.leviathan_engagements.get(engagement_id)
        if not scale: return
        
        while scale.turn < max_turns:
            scale.turn += 1
            print(f"[Leviathan {engagement_id}] Turn {scale.turn} complete.")
            await asyncio.sleep(0.1)
            await self._wait_at_leviathan_gate()

    async def start(self):
        """Starts the main operational loop."""
        # Setup barriers based on active engagements
        num_tactical_actors = len(self.wsm.current_state.centurion_engagements) + \
                              len(self.wsm.current_state.interceptor_engagements) + \
                              len(self.wsm.current_state.leviathan_engagements)
                              
        # If no tactical actors, we can just run Prefect turns
        if num_tactical_actors == 0:
            self.wsm.current_state.prefect_state.turn += 1
            print(f"[Prefect] Turn {self.wsm.current_state.prefect_state.turn} complete.")
            return

        self.leviathan_gate = asyncio.Barrier(parties=num_tactical_actors)
        
        # Spawn tasks
        for eng_id in self.wsm.current_state.centurion_engagements.keys():
            self.active_tasks[f"centurion_{eng_id}"] = asyncio.create_task(self.run_centurion_actor(eng_id))
            
        for eng_id in self.wsm.current_state.interceptor_engagements.keys():
            self.active_tasks[f"interceptor_{eng_id}"] = asyncio.create_task(self.run_interceptor_actor(eng_id))

        for eng_id in self.wsm.current_state.leviathan_engagements.keys():
            self.active_tasks[f"leviathan_{eng_id}"] = asyncio.create_task(self.run_leviathan_actor(eng_id))
            
        await asyncio.gather(*self.active_tasks.values())
