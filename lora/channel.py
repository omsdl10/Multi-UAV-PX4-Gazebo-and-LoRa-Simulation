from dataclasses import dataclass

from .airtime import lora_airtime_ms
from .packet_loss import classify_drop, delivery_probability
from .propagation import (
    distance_3d,
    free_space_path_loss_db,
    log_distance_path_loss_db,
    los_obstructions,
    received_power_dbm,
    snr_db,
)


@dataclass
class LinkResult:
    sender: int
    receiver: int
    distance: float
    rssi: float
    snr: float
    los: bool
    building_obstacles: list
    terrain_blocked: bool
    packet_status: str
    drop_reason: str
    latency_ms: float
    delivery_probability: float


class LoRaChannel:
    def __init__(self, config, obstacles, rng):
        self.config = config
        self.radio = config["radio"]
        self.loss = config["loss"]
        self.obstacles = obstacles
        self.rng = rng

    def evaluate(self, sender_state, receiver_state, payload_bytes):
        distance = distance_3d(sender_state, receiver_state)
        building_obstacles, terrain_blocked = los_obstructions(sender_state, receiver_state, self.obstacles)
        extra_loss = 0.0
        if building_obstacles:
            extra_loss += float(self.loss["building_loss_db"])
        if terrain_blocked:
            extra_loss += float(self.loss["terrain_loss_db"])

        if self.radio.get("path_loss_model", "log_distance") == "free_space":
            path_loss = free_space_path_loss_db(distance, self.radio["frequency_hz"])
        else:
            path_loss = log_distance_path_loss_db(distance, self.radio["frequency_hz"], self.radio["path_loss_exponent"])

        rssi = received_power_dbm(self.radio["tx_power_dbm"], path_loss, extra_loss)
        snr = snr_db(rssi, self.radio["noise_floor_dbm"])
        pdr = delivery_probability(
            distance,
            self.radio["maximum_range_m"],
            rssi,
            self.radio["receiver_sensitivity_dbm"],
            snr,
            self.radio["min_snr_db"],
            self.loss["channel_loss_scale"],
        )
        received = self.rng.random() <= pdr
        latency_ms = (
            (distance / 299_792_458.0) * 1000.0
            + lora_airtime_ms(
                payload_bytes,
                self.radio["spreading_factor"],
                self.radio["bandwidth_hz"],
                self.radio["coding_rate"],
            )
            + self.rng.uniform(self.loss["processing_delay_ms_min"], self.loss["processing_delay_ms_max"])
        )
        drop_reason = "" if received else classify_drop(
            distance,
            self.radio["maximum_range_m"],
            rssi,
            self.radio["receiver_sensitivity_dbm"],
            snr,
            self.radio["min_snr_db"],
        )
        return LinkResult(
            sender=sender_state.drone_id,
            receiver=receiver_state.drone_id,
            distance=distance,
            rssi=rssi,
            snr=snr,
            los=not building_obstacles and not terrain_blocked,
            building_obstacles=building_obstacles,
            terrain_blocked=terrain_blocked,
            packet_status="received" if received else "dropped",
            drop_reason=drop_reason,
            latency_ms=latency_ms,
            delivery_probability=pdr,
        )
