from __future__ import annotations

import os

from .app import create_app

app = create_app(config_path=os.environ.get("AQBOX_CONFIG", "./config/config.yaml"))

