import math


def lora_airtime_ms(payload_bytes, spreading_factor, bandwidth_hz, coding_rate, preamble_symbols=8, crc=True, explicit_header=True):
    sf = int(spreading_factor)
    bw = float(bandwidth_hz)
    cr = int(coding_rate) - 4
    cr = max(1, min(cr, 4))
    low_data_rate = 1 if sf >= 11 and bw <= 125000 else 0
    header_disabled = 0 if explicit_header else 1
    crc_enabled = 1 if crc else 0

    symbol_time = (2 ** sf) / bw
    numerator = 8 * int(payload_bytes) - 4 * sf + 28 + 16 * crc_enabled - 20 * header_disabled
    denominator = 4 * (sf - 2 * low_data_rate)
    payload_symbols = 8 + max(math.ceil(numerator / denominator) * (cr + 4), 0)
    preamble_time = (preamble_symbols + 4.25) * symbol_time
    payload_time = payload_symbols * symbol_time
    return (preamble_time + payload_time) * 1000.0
