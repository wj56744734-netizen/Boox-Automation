from pathlib import Path

import yaml

device_list = {}
_devices_dir = Path(__file__).resolve().parent / "models"
for yaml_file in sorted(_devices_dir.glob("*.yaml")):
    with open(yaml_file, encoding="utf-8") as f:
        device_list.update(yaml.safe_load(f))
