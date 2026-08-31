from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class Packet:
    packet_id: str
    source: int
    destination: int
    hop_count: int = 0
    ttl: int = 3
    visited: set = field(default_factory=set)


def new_packet(source, destination, ttl):
    return Packet(packet_id=str(uuid4()), source=source, destination=destination, ttl=ttl, visited={source})


class DuplicateFilter:
    def __init__(self, max_entries=4096):
        self.max_entries = max_entries
        self.seen = []
        self.index = set()

    def seen_before(self, packet_id, node_id):
        key = (packet_id, node_id)
        if key in self.index:
            return True
        self.index.add(key)
        self.seen.append(key)
        if len(self.seen) > self.max_entries:
            old = self.seen.pop(0)
            self.index.discard(old)
        return False
