import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Obstacle:
    name: str
    kind: str
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float


def distance_3d(a, b):
    return math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2 + (b.z - a.z) ** 2)


def free_space_path_loss_db(distance_m, frequency_hz):
    d = max(distance_m, 1.0)
    return 20.0 * math.log10(d) + 20.0 * math.log10(frequency_hz) - 147.55


def log_distance_path_loss_db(distance_m, frequency_hz, path_loss_exponent):
    d0 = 1.0
    return free_space_path_loss_db(d0, frequency_hz) + 10.0 * float(path_loss_exponent) * math.log10(max(distance_m, d0) / d0)


def received_power_dbm(tx_power_dbm, path_loss_db, extra_loss_db=0.0):
    return float(tx_power_dbm) - float(path_loss_db) - float(extra_loss_db)


def snr_db(rssi_dbm, noise_floor_dbm):
    return float(rssi_dbm) - float(noise_floor_dbm)


def line_intersects_aabb(a, b, obstacle):
    start = (a.x, a.y, a.z)
    end = (b.x, b.y, b.z)
    bounds = (
        (obstacle.min_x, obstacle.max_x),
        (obstacle.min_y, obstacle.max_y),
        (obstacle.min_z, obstacle.max_z),
    )
    tmin = 0.0
    tmax = 1.0
    for axis in range(3):
        delta = end[axis] - start[axis]
        if abs(delta) < 1e-9:
            if start[axis] < bounds[axis][0] or start[axis] > bounds[axis][1]:
                return False
            continue
        inv = 1.0 / delta
        t1 = (bounds[axis][0] - start[axis]) * inv
        t2 = (bounds[axis][1] - start[axis]) * inv
        t1, t2 = min(t1, t2), max(t1, t2)
        tmin = max(tmin, t1)
        tmax = min(tmax, t2)
        if tmin > tmax:
            return False
    return True


def los_obstructions(a, b, obstacles):
    buildings = []
    terrain_blocked = False
    for obstacle in obstacles:
        if line_intersects_aabb(a, b, obstacle):
            if obstacle.kind == "terrain":
                terrain_blocked = True
            else:
                buildings.append(obstacle.name)
    return buildings, terrain_blocked


def _parse_pose(text):
    values = [float(v) for v in (text or "0 0 0 0 0 0").split()]
    values += [0.0] * (6 - len(values))
    return values[:6]


def _parse_size(model):
    box = model.find(".//visual/geometry/box/size")
    if box is None:
        box = model.find(".//collision/geometry/box/size")
    if box is None or not box.text:
        return None
    values = [float(v) for v in box.text.split()]
    values += [1.0] * (3 - len(values))
    return values[:3]


def load_obstacles_from_sdf(path):
    path = Path(path)
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    obstacles = []
    for model in root.findall(".//model"):
        name = model.attrib.get("name", "")
        if not any(key in name for key in ("building", "warehouse", "house", "hill")):
            continue
        size = _parse_size(model)
        if not size:
            continue
        x, y, z, _roll, _pitch, _yaw = _parse_pose(model.findtext("pose"))
        sx, sy, sz = size
        kind = "terrain" if "hill" in name else "building"
        obstacles.append(
            Obstacle(
                name=name,
                kind=kind,
                min_x=x - sx / 2.0,
                max_x=x + sx / 2.0,
                min_y=y - sy / 2.0,
                max_y=y + sy / 2.0,
                min_z=max(0.0, z - sz / 2.0),
                max_z=z + sz / 2.0,
            )
        )
    return obstacles
