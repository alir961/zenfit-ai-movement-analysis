from __future__ import annotations

import logging
import os

import uvicorn

logging.basicConfig(level=os.getenv("ZENFIT_LOG_LEVEL", "INFO"))

if __name__ == "__main__":
    # Pass the app as an import string: the reloader imports it in a fresh worker
    # process, so the models are not also loaded in the watching parent.
    reload = os.getenv("ZENFIT_RELOAD", "0") == "1"
    uvicorn.run(
        "app.socket_server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8001")),
        reload=reload,
        reload_dirs=["app"] if reload else None,
    )
