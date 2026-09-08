#!/usr/bin/env bash
set -euo pipefail

CAMERA="${1:-overhead}"

case "$CAMERA" in
  overhead|wide)
    TOPIC="/world/uav_5km_world/model/audisys_camera_overhead_wide/link/link/sensor/camera/image"
    ;;
  base)
    TOPIC="/world/uav_5km_world/model/audisys_camera_uav_base/link/link/sensor/camera/image"
    ;;
  checkpoint|border)
    TOPIC="/world/uav_5km_world/model/audisys_camera_border_checkpoint/link/link/sensor/camera/image"
    ;;
  target|settlement)
    TOPIC="/world/uav_5km_world/model/audisys_camera_target_zone/link/link/sensor/camera/image"
    ;;
  *)
    echo "Usage: $0 [overhead|base|checkpoint|target]"
    exit 1
    ;;
esac

export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_PARTITION="${GZ_PARTITION:-multi_uav_lora_sim}"

echo "Opening camera: $CAMERA"
echo "Topic: $TOPIC"
gz topic -v -t "$TOPIC"
