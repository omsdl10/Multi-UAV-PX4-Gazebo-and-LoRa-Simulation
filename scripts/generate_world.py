#!/usr/bin/env python3
from pathlib import Path
import math
import random
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
WORLD_FILE = ROOT / "gazebo" / "worlds" / "uav_5km_world.sdf"


def add(parent, tag, text=None, **attrs):
    node = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})
    if text is not None:
        node.text = str(text)
    return node


def material(visual, ambient, diffuse=None):
    mat = add(visual, "material")
    add(mat, "ambient", ambient)
    add(mat, "diffuse", diffuse or ambient)


def static_box(world, name, pose, size, color, collision=True):
    model = add(world, "model", name=name)
    add(model, "static", "true")
    add(model, "pose", pose)
    link = add(model, "link", name="link")
    if collision:
        col = add(link, "collision", name="collision")
        geom = add(col, "geometry")
        box = add(geom, "box")
        add(box, "size", size)
    vis = add(link, "visual", name="visual")
    geom = add(vis, "geometry")
    box = add(geom, "box")
    add(box, "size", size)
    material(vis, color)
    return model


def static_cylinder(world, name, pose, radius, length, color, collision=True):
    model = add(world, "model", name=name)
    add(model, "static", "true")
    add(model, "pose", pose)
    link = add(model, "link", name="link")
    if collision:
        col = add(link, "collision", name="collision")
        geom = add(col, "geometry")
        cyl = add(geom, "cylinder")
        add(cyl, "radius", radius)
        add(cyl, "length", length)
    vis = add(link, "visual", name="visual")
    geom = add(vis, "geometry")
    cyl = add(geom, "cylinder")
    add(cyl, "radius", radius)
    add(cyl, "length", length)
    material(vis, color)
    return model


def road(world, name, x, y, sx, sy, yaw=0):
    z = 0.025
    static_box(world, name, f"{x} {y} {z} 0 0 {yaw}", f"{sx} {sy} 0.05", "0.05 0.05 0.05 1", False)


def tree(world, name, x, y):
    static_cylinder(world, f"{name}_trunk", f"{x} {y} 3 0 0 0", 0.7, 6, "0.22 0.12 0.06 1", False)
    static_cylinder(world, f"{name}_canopy", f"{x} {y} 9 0 0 0", 4.0, 7, "0.03 0.28 0.08 1", False)


def rock(world, name, x, y, scale):
    static_box(world, name, f"{x} {y} {0.4*scale} 0.2 0.1 0.4", f"{3*scale} {2*scale} {0.8*scale}", "0.28 0.27 0.25 1", False)


def hill(world, name, x, y, sx, sy, h, color):
    static_box(world, name, f"{x} {y} {h/2 - 0.2} 0 0 0", f"{sx} {sy} {h}", color, False)


def generate():
    random.seed(42)
    sdf = ET.Element("sdf", version="1.9")
    world = add(sdf, "world", name="uav_5km_world")

    add(world, "plugin", filename="gz-sim-physics-system", name="gz::sim::systems::Physics")
    add(world, "plugin", filename="gz-sim-user-commands-system", name="gz::sim::systems::UserCommands")
    add(world, "plugin", filename="gz-sim-scene-broadcaster-system", name="gz::sim::systems::SceneBroadcaster")
    add(world, "plugin", filename="gz-sim-imu-system", name="gz::sim::systems::Imu")
    add(world, "plugin", filename="gz-sim-air-pressure-system", name="gz::sim::systems::AirPressure")
    add(world, "plugin", filename="gz-sim-navsat-system", name="gz::sim::systems::NavSat")
    add(world, "plugin", filename="gz-sim-magnetometer-system", name="gz::sim::systems::Magnetometer")
    sensors = add(world, "plugin", filename="gz-sim-sensors-system", name="gz::sim::systems::Sensors")
    add(sensors, "render_engine", "ogre2")

    physics = add(world, "physics", type="ode")
    add(physics, "max_step_size", "0.004")
    add(physics, "real_time_factor", "1.0")
    add(physics, "real_time_update_rate", "250")

    add(world, "gravity", "0 0 -9.8")
    add(world, "magnetic_field", "6e-06 2.3e-05 -4.2e-05")
    add(world, "atmosphere", type="adiabatic")
    scene = add(world, "scene")
    add(scene, "ambient", "0.58 0.62 0.66 1")
    add(scene, "background", "0.70 0.82 0.92 1")
    add(scene, "shadows", "false")

    light = add(world, "light", name="sun", type="directional")
    add(light, "pose", "0 0 800 0.7 0.2 0.2")
    add(light, "cast_shadows", "false")
    add(light, "intensity", "0.8")
    add(light, "direction", "-0.4 0.2 -0.9")

    spherical = add(world, "spherical_coordinates")
    add(spherical, "surface_model", "EARTH_WGS84")
    add(spherical, "world_frame_orientation", "ENU")
    add(spherical, "latitude_deg", "47.397971057728974")
    add(spherical, "longitude_deg", "8.546163739800146")
    add(spherical, "elevation", "0")

    static_box(world, "base_5km_ground", "0 0 -0.06 0 0 0", "5000 5000 0.12", "0.18 0.36 0.18 1")
    static_box(world, "north_hill_band", "0 1700 3 0 0 0", "5000 1600 6", "0.24 0.32 0.20 1", False)
    static_box(world, "south_agriculture_band", "0 -1700 0.02 0 0 0", "5000 1600 0.04", "0.38 0.46 0.20 1", False)
    static_box(world, "east_industrial_band", "1700 0 0.03 0 0 0", "1600 1600 0.06", "0.29 0.30 0.30 1", False)
    static_box(world, "west_forest_band", "-1700 0 0.03 0 0 0", "1600 1600 0.06", "0.08 0.24 0.10 1", False)

    for i, (x, y, sx, sy, h) in enumerate([
        (-1500, 1850, 650, 430, 55), (-650, 2100, 800, 520, 95),
        (420, 1900, 780, 500, 75), (1350, 2180, 900, 540, 120),
        (-2100, 1200, 620, 360, 42), (2100, 1250, 700, 420, 50),
    ]):
        hill(world, f"low_poly_hill_{i:02d}", x, y, sx, sy, h, "0.26 0.34 0.22 1")

    road(world, "main_east_west_road", 0, 0, 5000, 24)
    road(world, "main_north_south_road", 0, 0, 24, 5000)
    road(world, "industrial_access_road", 1250, 350, 1900, 18, 0.22)
    road(world, "forest_rural_road", -1450, -220, 1800, 14, -0.28)
    road(world, "farm_service_road", -450, -1550, 2600, 12, 0.12)
    road(world, "hill_pass_road", 550, 1420, 2200, 12, -0.2)

    static_box(world, "uav_base_pad", "0 0 0.08 0 0 0", "90 70 0.16", "0.12 0.12 0.13 1", False)
    static_box(world, "uav_base_marking_x", "0 0 0.18 0 0 0", "70 4 0.05", "0.95 0.95 0.75 1", False)
    static_box(world, "uav_base_marking_y", "0 0 0.19 0 0 0", "4 50 0.05", "0.95 0.95 0.75 1", False)

    colors = ["0.52 0.55 0.58 1", "0.62 0.57 0.50 1", "0.48 0.50 0.54 1", "0.68 0.66 0.60 1"]
    idx = 0
    for gx in range(-5, 6):
        for gy in range(-4, 5):
            if idx >= 68:
                break
            x = gx * 95 + random.uniform(-14, 14)
            y = gy * 85 + random.uniform(-12, 12)
            if abs(x) < 70 and abs(y) < 60:
                continue
            sx = random.choice([28, 34, 42, 50])
            sy = random.choice([24, 32, 38])
            h = random.choice([10, 14, 18, 24, 32])
            static_box(world, f"urban_low_poly_building_{idx:02d}", f"{x:.1f} {y:.1f} {h/2:.1f} 0 0 0", f"{sx} {sy} {h}", random.choice(colors))
            idx += 1

    for i in range(14):
        x = random.uniform(950, 2250)
        y = random.uniform(-700, 750)
        sx = random.choice([70, 90, 120, 150])
        sy = random.choice([45, 60, 75])
        h = random.choice([12, 16, 20])
        static_box(world, f"east_warehouse_{i:02d}", f"{x:.1f} {y:.1f} {h/2:.1f} 0 0 {random.uniform(-0.2,0.2):.2f}", f"{sx} {sy} {h}", "0.42 0.43 0.42 1")

    for i in range(16):
        x = random.uniform(-2200, -850)
        y = random.uniform(-1050, 900)
        static_box(world, f"west_rural_house_{i:02d}", f"{x:.1f} {y:.1f} 4 0 0 {random.uniform(-0.5,0.5):.2f}", "24 18 8", "0.55 0.40 0.30 1")

    for i in range(14):
        x = -2100 + i * 285
        static_box(world, f"south_field_{i:02d}", f"{x} -1750 0.04 0 0 0", "230 520 0.05", random.choice(["0.44 0.50 0.19 1", "0.30 0.44 0.18 1", "0.54 0.46 0.22 1"]), False)

    for i in range(80):
        tree(world, f"forest_tree_{i:02d}", random.uniform(-2400, -900), random.uniform(-1200, 1050))

    for i in range(34):
        rock(world, f"north_rock_{i:02d}", random.uniform(-2300, 2300), random.uniform(1100, 2400), random.uniform(0.7, 1.8))

    WORLD_FILE.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(sdf, space="  ")
    ET.ElementTree(sdf).write(WORLD_FILE, encoding="utf-8", xml_declaration=True)
    print(WORLD_FILE)


if __name__ == "__main__":
    generate()
