from __future__ import annotations

import logging
import os

import uvicorn

from .socket_server import app

logging.basicConfig(level=os.getenv("ZENFIT_LOG_LEVEL", "INFO"))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
