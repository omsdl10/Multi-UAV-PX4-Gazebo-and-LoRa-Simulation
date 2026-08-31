import math


def delivery_probability(distance_m, maximum_range_m, rssi_dbm, sensitivity_dbm, snr_db, min_snr_db, channel_loss_scale):
    if distance_m > maximum_range_m:
        return 0.0
    rssi_margin = rssi_dbm - sensitivity_dbm
    snr_margin = snr_db - min_snr_db
    rssi_factor = 1.0 / (1.0 + math.exp(-rssi_margin / 4.0))
    snr_factor = 1.0 / (1.0 + math.exp(-snr_margin / 2.0))
    range_factor = max(0.0, 1.0 - (distance_m / maximum_range_m) ** 1.7)
    random_channel_floor = max(0.0, 1.0 - float(channel_loss_scale))
    return max(0.0, min(1.0, rssi_factor * snr_factor * (0.15 + 0.85 * range_factor) * random_channel_floor))


def classify_drop(distance_m, maximum_range_m, rssi_dbm, sensitivity_dbm, snr_db, min_snr_db):
    if distance_m > maximum_range_m:
        return "out_of_range"
    if rssi_dbm < sensitivity_dbm:
        return "low_rssi"
    if snr_db < min_snr_db:
        return "low_snr"
    return "channel_loss"
