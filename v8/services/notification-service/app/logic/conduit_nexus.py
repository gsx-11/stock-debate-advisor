import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket
from datetime import datetime, timezone


class ConduitNexus:
    """Manages conduit connections and pulse routing"""
    
    def __init__(self):
        self.active_conduits: Dict[str, Set[WebSocket]] = {}
        self.conduit_chronicles: Dict[WebSocket, dict] = {}
        self.pulse_queue: asyncio.Queue = asyncio.Queue()
    
    async def establish_conduit(self, receptor_id: str, conduit_wire: WebSocket):
        """Establish new conduit connection"""
        await conduit_wire.accept()
        
        if receptor_id not in self.active_conduits:
            self.active_conduits[receptor_id] = set()
        
        self.active_conduits[receptor_id].add(conduit_wire)
        self.conduit_chronicles[conduit_wire] = {
            "receptor": receptor_id,
            "established": datetime.now(timezone.utc),
            "pulse_tally": 0
        }
    
    def sever_conduit(self, receptor_id: str, conduit_wire: WebSocket):
        """Sever conduit connection"""
        if receptor_id in self.active_conduits:
            self.active_conduits[receptor_id].discard(conduit_wire)
            
            if not self.active_conduits[receptor_id]:
                del self.active_conduits[receptor_id]
        
        if conduit_wire in self.conduit_chronicles:
            del self.conduit_chronicles[conduit_wire]
    
    async def transmit_pulse_to_receptor(
        self,
        receptor_id: str,
        pulse_cargo: dict
    ):
        """Transmit pulse to specific receptor"""
        if receptor_id not in self.active_conduits:
            return
        
        serialized_pulse = json.dumps(pulse_cargo)
        severed_wires = []
        
        for conduit_wire in self.active_conduits[receptor_id]:
            try:
                await conduit_wire.send_text(serialized_pulse)
                self.conduit_chronicles[conduit_wire]["pulse_tally"] += 1
            except Exception:
                severed_wires.append(conduit_wire)
        
        for conduit_wire in severed_wires:
            self.sever_conduit(receptor_id, conduit_wire)
    
    async def broadcast_pulse_cascade(
        self,
        receptor_roster: list[str],
        pulse_cargo: dict
    ):
        """Broadcast pulse to multiple receptors"""
        transmission_tasks = [
            self.transmit_pulse_to_receptor(receptor, pulse_cargo)
            for receptor in receptor_roster
        ]
        await asyncio.gather(*transmission_tasks, return_exceptions=True)
    
    def compile_nexus_metrics(self) -> dict:
        """Compile metrics about nexus state"""
        total_wires = sum(len(wires) for wires in self.active_conduits.values())
        
        return {
            "receptor_count": len(self.active_conduits),
            "conduit_count": total_wires,
            "receptor_roster": list(self.active_conduits.keys())
        }


conduit_nexus_singleton = ConduitNexus()
