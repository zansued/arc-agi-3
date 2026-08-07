"""
Synaptic Network: Grafo de interações entre objetos (sinapses).
"""
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
import json

@dataclass
class Synapse:
    source: str
    target: str
    signal_type: str
    weight: float = 1.0
    activated_count: int = 0
    last_activated: Optional[str] = None

def save_network(network: List[Synapse], path: str):
    data = []
    for s in network:
        data.append({'source': s.source, 'target': s.target, 'signal_type': s.signal_type})
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def load_network(path: str) -> List[Synapse]:
    with open(path) as f:
        data = json.load(f)
    return [Synapse(**d) for d in data]
