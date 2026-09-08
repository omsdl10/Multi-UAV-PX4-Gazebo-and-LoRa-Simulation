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


def material(visual, ambient, diffuse=None, specular="0.08 0.08 0.08 1"):
    mat = add(visual, "material")
    add(mat, "ambient", ambient)
    add(mat, "diffuse", diffuse or ambient)
    add(mat, "specular", specular)


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


def segment_box(world, name, x1, y1, x2, y2, width, height, z, color, collision=False):
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    yaw = math.atan2(dy, dx)
    x = (x1 + x2) / 2.0
    y = (y1 + y2) / 2.0
    static_box(world, name, f"{x:.2f} {y:.2f} {z:.2f} 0 0 {yaw:.4f}", f"{length:.2f} {width:.2f} {height:.2f}", color, collision)


def road_segment(world, name, p1, p2, width=18, paved=False):
    color = "0.08 0.075 0.065 1" if paved else "0.38 0.29 0.19 1"
    segment_box(world, name, p1[0], p1[1], p2[0], p2[1], width, 0.06, 0.035, color, False)


def make_polyline(world, prefix, points, width, height, z, color, collision=False):
    for i in range(len(points) - 1):
        segment_box(world, f"{prefix}_{i:02d}", points[i][0], points[i][1], points[i + 1][0], points[i + 1][1], width, height, z, color, collision)


def terrain_patch(world, name, x, y, sx, sy, color, yaw=0.0, z=0.015):
    static_box(world, name, f"{x:.1f} {y:.1f} {z:.3f} 0 0 {yaw:.3f}", f"{sx:.1f} {sy:.1f} 0.03", color, False)


def hill(world, name, x, y, sx, sy, h, color, yaw=0.0):
    static_box(world, name, f"{x:.1f} {y:.1f} {h/2 - 0.15:.1f} 0 0 {yaw:.3f}", f"{sx:.1f} {sy:.1f} {h:.1f}", color, False)


def ridge(world, name, x, y, sx, sy, h, yaw):
    hill(world, name, x, y, sx, sy, h, "0.36 0.31 0.24 1", yaw)
    segment_box(world, f"{name}_rocky_crest", x - sx * 0.35 * math.cos(yaw), y - sx * 0.35 * math.sin(yaw), x + sx * 0.35 * math.cos(yaw), y + sx * 0.35 * math.sin(yaw), sy * 0.22, 1.2, h + 0.3, "0.30 0.29 0.27 1", False)


def tree(world, name, x, y, scale=1.0):
    static_cylinder(world, f"{name}_trunk", f"{x:.1f} {y:.1f} {2.5*scale:.1f} 0 0 0", 0.45 * scale, 5.0 * scale, "0.22 0.13 0.07 1", False)
    static_cylinder(world, f"{name}_canopy", f"{x:.1f} {y:.1f} {7.2*scale:.1f} 0 0 0", 3.2 * scale, 5.3 * scale, "0.08 0.22 0.10 1", False)


def shrub(world, name, x, y, scale=1.0):
    static_cylinder(world, name, f"{x:.1f} {y:.1f} {1.0*scale:.1f} 0 0 0", 1.6 * scale, 2.0 * scale, "0.20 0.28 0.12 1", False)


def rock(world, name, x, y, scale, yaw=0.0):
    static_box(world, name, f"{x:.1f} {y:.1f} {0.45*scale:.2f} 0.14 0.07 {yaw:.3f}", f"{3.2*scale:.1f} {2.1*scale:.1f} {0.9*scale:.1f}", "0.31 0.30 0.28 1", False)


def simple_building(world, name, x, y, sx, sy, h, color, yaw=0.0, damaged=False):
    static_box(world, name, f"{x:.1f} {y:.1f} {h/2:.1f} 0 0 {yaw:.3f}", f"{sx:.1f} {sy:.1f} {h:.1f}", color, True)
    roof_h = 0.5 if not damaged else 0.35
    roof_color = "0.22 0.20 0.18 1" if not damaged else "0.16 0.15 0.14 1"
    static_box(world, f"{name}_roof", f"{x:.1f} {y:.1f} {h + roof_h/2:.1f} 0 0 {yaw:.3f}", f"{sx + 1.0:.1f} {sy + 1.0:.1f} {roof_h:.1f}", roof_color, False)


def tower(world, name, x, y, h=28):
    static_box(world, f"{name}_base", f"{x:.1f} {y:.1f} 0.6 0 0 0", "5 5 1.2", "0.28 0.28 0.25 1", True)
    for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
        static_cylinder(world, f"{name}_leg_{dx}_{dy}", f"{x+dx:.1f} {y+dy:.1f} {h/2:.1f} 0 0 0", 0.18, h, "0.18 0.18 0.17 1", False)
    static_box(world, f"{name}_platform", f"{x:.1f} {y:.1f} {h+1.1:.1f} 0 0 0", "9 9 2.2", "0.32 0.32 0.30 1", False)
    static_cylinder(world, f"{name}_antenna", f"{x:.1f} {y:.1f} {h+8:.1f} 0 0 0", 0.12, 14, "0.05 0.05 0.05 1", False)


def floodlight(world, name, x, y, yaw=0.0):
    static_cylinder(world, f"{name}_pole", f"{x:.1f} {y:.1f} 5.0 0 0 0", 0.15, 10, "0.12 0.12 0.12 1", False)
    static_box(world, f"{name}_lamp", f"{x:.1f} {y:.1f} 10.4 0 0 {yaw:.3f}", "2.2 0.8 0.8", "0.95 0.88 0.55 1", False)


def sign(world, name, x, y, yaw, label_color="0.95 0.82 0.25 1"):
    static_cylinder(world, f"{name}_post", f"{x:.1f} {y:.1f} 1.5 0 0 0", 0.08, 3, "0.12 0.12 0.12 1", False)
    static_box(world, name, f"{x:.1f} {y:.1f} 3.2 0 0 {yaw:.3f}", "3.4 0.12 1.5", label_color, False)


def vehicle(world, name, x, y, yaw=0.0, color="0.18 0.22 0.18 1"):
    static_box(world, name, f"{x:.1f} {y:.1f} 0.8 0 0 {yaw:.3f}", "5.2 2.2 1.6", color, True)
    static_box(world, f"{name}_cab", f"{x+1.0*math.cos(yaw):.1f} {y+1.0*math.sin(yaw):.1f} 1.9 0 0 {yaw:.3f}", "2.1 2.0 1.1", color, False)


def audisys_target(world):
    model = add(world, "model", name="audisys_target")
    add(model, "static", "false")
    add(model, "pose", "-980 -520 0.75 0 0 0.2")
    link = add(model, "link", name="link")
    inertial = add(link, "inertial")
    add(inertial, "mass", "35")
    inertia = add(inertial, "inertia")
    add(inertia, "ixx", "8")
    add(inertia, "iyy", "8")
    add(inertia, "izz", "4")
    visual = add(link, "visual", name="body_visual")
    geometry = add(visual, "geometry")
    box = add(geometry, "box")
    add(box, "size", "3.2 1.5 1.5")
    material(visual, "0.70 0.15 0.10 1", "0.85 0.20 0.12 1")
    marker_visual = add(link, "visual", name="mast_visual")
    marker_geometry = add(marker_visual, "geometry")
    cylinder = add(marker_geometry, "cylinder")
    add(cylinder, "radius", "0.09")
    add(cylinder, "length", "3.0")
    add(marker_visual, "pose", "0 0 2.25 0 0 0")
    material(marker_visual, "0.95 0.80 0.15 1", "1.0 0.88 0.18 1")


def observer_camera(world, name, pose, horizontal_fov=1.15):
    model = add(world, "model", name=name)
    add(model, "static", "true")
    add(model, "pose", pose)
    link = add(model, "link", name="link")
    sensor = add(link, "sensor", name="camera", type="camera")
    add(sensor, "always_on", "1")
    add(sensor, "update_rate", "15")
    camera = add(sensor, "camera")
    add(camera, "horizontal_fov", f"{horizontal_fov:.3f}")
    image = add(camera, "image")
    add(image, "width", "1280")
    add(image, "height", "720")
    add(image, "format", "R8G8B8")
    clip = add(camera, "clip")
    add(clip, "near", "0.5")
    add(clip, "far", "9000")


def add_observer_cameras(world):
    observer_camera(world, "audisys_camera_overhead_wide", "0 0 3000 0 1.5708 0", 1.25)
    observer_camera(world, "audisys_camera_uav_base", "-180 430 170 0 0.92 -0.78", 1.05)
    observer_camera(world, "audisys_camera_border_checkpoint", "-360 290 260 0 0.88 -0.45", 1.10)
    observer_camera(world, "audisys_camera_target_zone", "-1040 -250 230 0 0.86 -0.35", 1.05)


def add_camera_gui_panels(world):
    gui = add(world, "gui", fullscreen="0")
    topics = [
        ("AuDiSys Overhead Wide", "/world/uav_5km_world/model/audisys_camera_overhead_wide/link/link/sensor/camera/image"),
        ("AuDiSys UAV Base", "/world/uav_5km_world/model/audisys_camera_uav_base/link/link/sensor/camera/image"),
        ("AuDiSys Border Checkpoint", "/world/uav_5km_world/model/audisys_camera_border_checkpoint/link/link/sensor/camera/image"),
        ("AuDiSys Target Zone", "/world/uav_5km_world/model/audisys_camera_target_zone/link/link/sensor/camera/image"),
    ]
    for title, topic in topics:
        plugin = add(gui, "plugin", filename="ImageDisplay", name=title)
        gz_gui = add(plugin, "gz-gui")
        add(gz_gui, "property", "docked", key="state", type="string")
        add(plugin, "topic", topic)


def sandbag_wall(world, name, x, y, yaw, length=18):
    for i in range(int(length // 3)):
        offset = (i - length / 6) * 3.0
        bx = x + offset * math.cos(yaw)
        by = y + offset * math.sin(yaw)
        static_box(world, f"{name}_{i:02d}", f"{bx:.1f} {by:.1f} 0.35 0 0 {yaw:.3f}", "2.4 0.9 0.7", "0.47 0.40 0.26 1", False)


def add_border(world):
    border = [(-2500, -210), (-1900, -170), (-1320, -245), (-760, -120), (-210, -55), (350, -95), (950, 25), (1480, 95), (2050, 55), (2500, 125)]
    make_polyline(world, "border_buffer_north_edge", [(x, y + 150) for x, y in border], 3, 0.05, 0.07, "0.55 0.45 0.24 1", False)
    make_polyline(world, "border_buffer_south_edge", [(x, y - 150) for x, y in border], 3, 0.05, 0.08, "0.55 0.45 0.24 1", False)

    for i in range(len(border) - 1):
        x1, y1 = border[i]
        x2, y2 = border[i + 1]
        segment_box(world, f"border_reinforced_fence_{i:02d}", x1, y1, x2, y2, 1.0, 3.8, 1.9, "0.20 0.22 0.22 1", False)
        if i in (1, 2, 5, 6):
            segment_box(world, f"border_double_layer_fence_{i:02d}", x1, y1 + 30, x2, y2 + 30, 0.8, 3.2, 1.6, "0.18 0.20 0.20 1", False)
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        yaw = math.atan2(dy, dx)
        post_count = max(2, int(length // 95))
        for j in range(post_count + 1):
            t = j / post_count
            px = x1 + dx * t
            py = y1 + dy * t
            static_cylinder(world, f"border_post_{i:02d}_{j:02d}", f"{px:.1f} {py:.1f} 2.0 0 0 0", 0.16, 4.0, "0.12 0.13 0.13 1", False)
            if j % 3 == 1:
                sign(world, f"border_warning_sign_{i:02d}_{j:02d}", px + 6 * math.sin(yaw), py - 6 * math.cos(yaw), yaw)
            if j % 4 == 2:
                static_box(world, f"border_marker_{i:02d}_{j:02d}", f"{px-8*math.sin(yaw):.1f} {py+8*math.cos(yaw):.1f} 1.2 0 0 {yaw:.3f}", "1.1 1.1 2.4", "0.78 0.75 0.68 1", False)

    for i, x in enumerate([-1980, -980, 180, 1180, 2100]):
        y = -120 + 70 * math.sin(i * 1.7)
        tower(world, f"border_observation_tower_{i:02d}", x, y + 55, 30)
        floodlight(world, f"border_floodlight_{i:02d}", x + 35, y + 45, -0.6)
        sandbag_wall(world, f"border_sandbag_position_{i:02d}", x - 30, y + 38, 0.15, 15)


def add_checkpoint(world):
    x0, y0 = 120, -60
    static_box(world, "checkpoint_compound_wall_n", f"{x0} {y0+95} 1.4 0 0 0", "230 3 2.8", "0.42 0.40 0.35 1", True)
    static_box(world, "checkpoint_compound_wall_s", f"{x0} {y0-95} 1.4 0 0 0", "230 3 2.8", "0.42 0.40 0.35 1", True)
    static_box(world, "checkpoint_compound_wall_e", f"{x0+115} {y0} 1.4 0 0 0", "3 190 2.8", "0.42 0.40 0.35 1", True)
    static_box(world, "checkpoint_compound_wall_w", f"{x0-115} {y0} 1.4 0 0 0", "3 190 2.8", "0.42 0.40 0.35 1", True)
    road_segment(world, "checkpoint_primary_paved_road", (-260, -60), (500, -60), 28, True)
    for lane_y in [-76, -60, -44]:
        segment_box(world, f"checkpoint_lane_marking_{lane_y}", -60, lane_y, 315, lane_y, 0.7, 0.04, 0.08, "0.88 0.82 0.55 1", False)
    simple_building(world, "checkpoint_security_building_main", 55, 40, 42, 28, 9, "0.58 0.55 0.48 1")
    simple_building(world, "checkpoint_security_building_ops", 165, 36, 34, 24, 8, "0.50 0.51 0.48 1")
    simple_building(world, "checkpoint_guard_booth_west", -50, -26, 12, 10, 5, "0.62 0.58 0.48 1")
    simple_building(world, "checkpoint_guard_booth_east", 280, -28, 12, 10, 5, "0.62 0.58 0.48 1")
    for i, gx in enumerate([-5, 110, 225]):
        static_box(world, f"checkpoint_boom_gate_{i}", f"{gx} -38 1.3 0 0 0.05", "28 0.5 0.5", "0.85 0.16 0.12 1", False)
        static_box(world, f"checkpoint_concrete_barrier_{i}", f"{gx+32} -84 0.7 0 0 0", "14 1.8 1.4", "0.48 0.47 0.43 1", True)
    tower(world, "checkpoint_watchtower_north", -92, 74, 24)
    tower(world, "checkpoint_watchtower_south", 318, -88, 24)
    for i, (lx, ly) in enumerate([(-80, 80), (10, -88), (220, 82), (330, -82)]):
        floodlight(world, f"checkpoint_floodlight_{i}", lx, ly)
    for i, (cx, cy) in enumerate([(205, 74), (230, 74), (255, 74), (230, 50)]):
        static_box(world, f"checkpoint_cargo_container_{i}", f"{cx} {cy} 1.4 0 0 0", "18 6 2.8", "0.45 0.30 0.18 1", True)
    static_cylinder(world, "checkpoint_communication_antenna", "130 90 18 0 0 0", 0.18, 36, "0.05 0.05 0.05 1", False)
    static_box(world, "checkpoint_generator", "88 78 1.0 0 0 0.2", "7 3 2", "0.18 0.22 0.18 1", True)
    for i, (vx, vy, yaw) in enumerate([(20, -86, 0.05), (185, -88, 0.0), (250, -14, 3.1)]):
        vehicle(world, f"checkpoint_parked_utility_vehicle_{i}", vx, vy, yaw)


def add_outpost(world, name, x, y, yaw):
    terrain_patch(world, f"{name}_cleared_ground", x, y, 95, 75, "0.39 0.31 0.21 1", yaw)
    simple_building(world, f"{name}_temporary_shelter", x - 20, y - 8, 22, 14, 5, "0.39 0.42 0.34 1", yaw)
    static_box(world, f"{name}_tent", f"{x+22:.1f} {y-12:.1f} 2.2 0 0 {yaw:.3f}", "18 12 4.4", "0.28 0.35 0.24 1", False)
    static_box(world, f"{name}_camouflage_net_structure", f"{x+10:.1f} {y+20:.1f} 3.0 0 0 {yaw:.3f}", "34 22 0.4", "0.12 0.25 0.11 1", False)
    tower(world, f"{name}_observation_tower", x - 38, y + 24, 22)
    static_cylinder(world, f"{name}_communication_antenna", f"{x+42:.1f} {y+24:.1f} 13 0 0 0", 0.12, 26, "0.06 0.06 0.06 1", False)
    sandbag_wall(world, f"{name}_sandbag_wall_n", x, y + 36, yaw, 35)
    sandbag_wall(world, f"{name}_sandbag_wall_s", x, y - 36, yaw, 25)
    for i in range(5):
        static_box(world, f"{name}_storage_crate_{i}", f"{x+random.uniform(-30,35):.1f} {y+random.uniform(-26,28):.1f} 0.7 0 0 {random.uniform(-0.4,0.4):.2f}", "3 2.2 1.4", "0.30 0.24 0.16 1", False)
    static_box(world, f"{name}_small_generator", f"{x+34:.1f} {y-26:.1f} 0.7 0 0 {yaw:.3f}", "4.5 2.4 1.4", "0.16 0.18 0.15 1", True)
    vehicle(world, f"{name}_parked_nonfunctional_vehicle", x - 8, y + 22, yaw + 0.2, "0.23 0.27 0.20 1")


def add_abandoned_zone(world):
    cx, cy = -680, -720
    terrain_patch(world, "damaged_settlement_dusty_ground", cx, cy, 520, 410, "0.35 0.30 0.24 1", 0.18)
    road_segment(world, "abandoned_access_road", (-1090, -510), (-255, -860), 13, False)
    for i in range(26):
        x = cx + random.uniform(-235, 235)
        y = cy + random.uniform(-180, 185)
        yaw = random.uniform(-0.55, 0.55)
        sx = random.choice([18, 22, 28, 34, 42])
        sy = random.choice([16, 20, 26, 32])
        h = random.choice([5, 7, 9, 12])
        damaged = i % 3 != 0
        simple_building(world, f"damaged_abandoned_building_{i:02d}", x, y, sx, sy, h, random.choice(["0.50 0.46 0.39 1", "0.42 0.40 0.36 1", "0.56 0.52 0.45 1"]), yaw, damaged)
        if damaged:
            static_box(world, f"damaged_abandoned_building_{i:02d}_collapsed_wall", f"{x+sx*0.32:.1f} {y-sy*0.25:.1f} 1.0 0 0 {yaw+0.3:.3f}", f"{sx*0.55:.1f} 1.0 2.0", "0.36 0.34 0.31 1", False)
            static_box(world, f"damaged_abandoned_building_{i:02d}_broken_roof", f"{x-sx*0.18:.1f} {y+sy*0.18:.1f} {h+0.45:.1f} 0.12 0.18 {yaw:.3f}", f"{sx*0.65:.1f} {sy*0.50:.1f} 0.35", "0.14 0.14 0.13 1", False)
    for i in range(38):
        rock(world, f"damaged_zone_rubble_pile_{i:02d}", cx + random.uniform(-255, 255), cy + random.uniform(-205, 205), random.uniform(0.7, 2.4), random.uniform(0, 3.14))
    for i in range(7):
        vehicle(world, f"damaged_zone_abandoned_vehicle_{i:02d}", cx + random.uniform(-230, 230), cy + random.uniform(-180, 180), random.uniform(-3.14, 3.14), "0.19 0.18 0.15 1")
    for i in range(8):
        static_box(world, f"damaged_zone_storage_container_{i:02d}", f"{cx+random.uniform(-230,230):.1f} {cy+random.uniform(-180,180):.1f} 1.3 0 0 {random.uniform(-0.6,0.6):.2f}", "14 5 2.6", "0.35 0.24 0.17 1", True)
    for i in range(12):
        static_cylinder(world, f"damaged_zone_broken_streetlight_{i:02d}", f"{cx+random.uniform(-250,250):.1f} {cy+random.uniform(-205,205):.1f} 2.7 0.8 0.1 {random.uniform(-0.5,0.5):.2f}", 0.08, 5.4, "0.10 0.10 0.10 1", False)


def add_roads_and_infrastructure(world):
    paved = [(-2500, -1120), (-1780, -980), (-1180, -740), (-360, -610), (160, -60), (820, 160), (1620, 260), (2500, 520)]
    for i in range(len(paved) - 1):
        road_segment(world, f"primary_paved_road_{i:02d}", paved[i], paved[i + 1], 24, True)
    rural_roads = [
        [(-2200, 760), (-1580, 620), (-920, 410), (-210, -55)],
        [(-330, -610), (-710, -1020), (-1260, -1380), (-2060, -1580)],
        [(210, -60), (550, -490), (1020, -920), (1580, -1220)],
        [(980, 120), (1230, 680), (1570, 1030), (2150, 1370)],
        [(-1420, 850), (-1110, 1120), (-720, 1510), (-240, 1940)],
    ]
    for idx, path in enumerate(rural_roads):
        for i in range(len(path) - 1):
            road_segment(world, f"secondary_rural_road_{idx:02d}_{i:02d}", path[i], path[i + 1], 13, False)
    for i, x in enumerate(range(-2300, 2301, 310)):
        y = -1120 + 0.18 * (x + 1200)
        static_cylinder(world, f"power_pole_{i:02d}", f"{x} {y:.1f} 5.0 0 0 0", 0.16, 10, "0.19 0.12 0.07 1", False)
        segment_box(world, f"power_line_visual_{i:02d}", x, y + 1.2, min(x + 310, 2500), y + 57, 0.12, 0.12, 10.2, "0.04 0.04 0.04 1", False)
    for i, (x, y) in enumerate([(-1220, -980), (-880, -535), (610, -440), (1350, 780)]):
        static_box(world, f"small_bridge_or_culvert_{i:02d}", f"{x} {y} 0.25 0 0 {random.uniform(-0.4,0.4):.2f}", "42 18 0.5", "0.34 0.34 0.32 1", True)
        static_box(world, f"drainage_channel_{i:02d}", f"{x} {y-22} 0.02 0 0 0", "85 5 0.04", "0.12 0.11 0.09 1", False)


def generate():
    random.seed(84)
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
    add_camera_gui_panels(world)

    physics = add(world, "physics", type="ode")
    add(physics, "max_step_size", "0.004")
    add(physics, "real_time_factor", "1.0")
    add(physics, "real_time_update_rate", "250")

    add(world, "gravity", "0 0 -9.8")
    add(world, "magnetic_field", "6e-06 2.3e-05 -4.2e-05")
    add(world, "atmosphere", type="adiabatic")
    scene = add(world, "scene")
    add(scene, "ambient", "0.48 0.44 0.38 1")
    add(scene, "background", "0.82 0.70 0.56 1")
    add(scene, "shadows", "true")
    add(scene, "grid", "false")

    light = add(world, "light", name="late_afternoon_sun", type="directional")
    add(light, "pose", "-1100 -1500 900 0.55 0.25 -0.55")
    add(light, "cast_shadows", "true")
    add(light, "intensity", "1.05")
    add(light, "direction", "0.45 0.28 -0.85")
    add(light, "diffuse", "1.0 0.78 0.52 1")
    add(light, "specular", "0.35 0.28 0.18 1")

    spherical = add(world, "spherical_coordinates")
    add(spherical, "surface_model", "EARTH_WGS84")
    add(spherical, "world_frame_orientation", "ENU")
    add(spherical, "latitude_deg", "47.397971057728974")
    add(spherical, "longitude_deg", "8.546163739800146")
    add(spherical, "elevation", "0")

    static_box(world, "base_5km_semi_arid_ground", "0 0 -0.06 0 0 0", "5000 5000 0.12", "0.42 0.34 0.23 1", True)

    for i in range(44):
        x = random.uniform(-2380, 2380)
        y = random.uniform(-2380, 2380)
        sx = random.uniform(260, 780)
        sy = random.uniform(180, 620)
        color = random.choice(["0.46 0.36 0.22 1", "0.32 0.28 0.21 1", "0.28 0.34 0.19 1", "0.55 0.47 0.30 1", "0.38 0.30 0.20 1"])
        terrain_patch(world, f"terrain_material_patch_{i:02d}", x, y, sx, sy, color, random.uniform(-3.14, 3.14))

    for i, args in enumerate([
        (-1780, 1850, 850, 360, 88, 0.28), (-1050, 2100, 980, 420, 135, -0.18),
        (-120, 1850, 760, 330, 72, 0.36), (760, 2140, 980, 470, 120, 0.08),
        (1600, 1720, 720, 350, 82, -0.42), (-2100, 880, 660, 290, 55, 0.55),
        (2200, 980, 640, 300, 48, -0.26), (-1550, -1420, 820, 390, 42, 0.2),
        (1120, -1510, 760, 340, 36, -0.35), (340, -2050, 900, 420, 50, 0.18),
    ]):
        ridge(world, f"low_poly_hill_ridge_{i:02d}", *args)

    for i in range(24):
        x = random.uniform(-2300, 2300)
        y = random.choice([random.uniform(900, 2350), random.uniform(-2350, -1350)])
        ridge(world, f"erosion_like_terrain_ridge_{i:02d}", x, y, random.uniform(120, 320), random.uniform(22, 55), random.uniform(5, 16), random.uniform(-1.0, 1.0))
    for i in range(16):
        terrain_patch(world, f"shallow_valley_dry_wash_{i:02d}", random.uniform(-2200, 2200), random.uniform(-2200, 2200), random.uniform(260, 720), random.uniform(18, 42), "0.27 0.23 0.17 1", random.uniform(-1.2, 1.2), 0.04)

    add_roads_and_infrastructure(world)
    add_border(world)
    add_checkpoint(world)
    add_abandoned_zone(world)

    for i, (x, y, yaw) in enumerate([(-1380, 940, 0.35), (1510, 1020, -0.25), (-1710, -1180, 0.62), (980, -1380, -0.45), (2140, 410, 0.1)]):
        add_outpost(world, f"fictional_observation_outpost_{i:02d}", x, y, yaw)

    static_box(world, "uav_base_pad_border_surveillance", "0 180 0.08 0 0 0", "105 76 0.16", "0.12 0.12 0.13 1", False)
    static_box(world, "uav_base_marking_x", "0 180 0.18 0 0 0", "78 4 0.05", "0.94 0.86 0.55 1", False)
    static_box(world, "uav_base_marking_y", "0 180 0.19 0 0 0", "4 56 0.05", "0.94 0.86 0.55 1", False)
    audisys_target(world)
    add_observer_cameras(world)

    for i in range(95):
        x = random.uniform(-2400, 2400)
        y = random.uniform(-2350, 2350)
        if -1050 < x < -320 and -1050 < y < -430:
            continue
        if abs(y) < 260 and random.random() < 0.45:
            continue
        if random.random() < 0.42:
            shrub(world, f"semi_arid_shrub_{i:02d}", x, y, random.uniform(0.6, 1.5))
        else:
            tree(world, f"scattered_tree_{i:02d}", x, y, random.uniform(0.55, 1.25))

    for i in range(130):
        rock(world, f"scattered_rock_{i:03d}", random.uniform(-2420, 2420), random.uniform(-2380, 2380), random.uniform(0.35, 1.9), random.uniform(-3.14, 3.14))

    WORLD_FILE.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(sdf, space="  ")
    ET.ElementTree(sdf).write(WORLD_FILE, encoding="utf-8", xml_declaration=True)
    print(WORLD_FILE)


if __name__ == "__main__":
    generate()
