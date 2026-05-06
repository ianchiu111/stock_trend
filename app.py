import os
import time
import threading
import numpy as np
import pandas as pd
import pytz
import logging
import traceback
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, abort
from flask_cors import CORS


# ====================================================

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

taiwan_tz = pytz.timezone("Asia/Taipei")
current_time_taiwan = datetime.now(taiwan_tz)
version = current_time_taiwan.strftime("v%Y-%m%d-%H%M")

# ====================================================


class APIResponse:
    """Static class for generating API responses"""

    @staticmethod
    def success(
        data: Any = None, message: str = "Success", meta: Optional[Dict] = None
    ):
        response = {
            "success": True,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        if data is not None:
            response["data"] = data
        if meta:
            response["meta"] = meta
        return response

    @staticmethod
    def error(
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[str] = None,
    ):
        response = {
            "success": False,
            "error": {
                "message": message,
                "code": error_code,
                "timestamp": datetime.now().isoformat(),
            },
        }
        if details:
            response["error"]["details"] = details
        return response, status_code


@app.route("/api/fetch_data", methods=["POST"])
def fetch_data():
    """
    Endpoint to fetch twse stock data

    """

@app.route("/api/update_data", methods=["POST"])
def update_data():
    """
    Endpoint to update twse stock data

    """

@app.get("/health")
def health():
    return {"status": f"server is running {version}"}


if __name__ == "__main__":
    port = 5001  # Default port
    logger.info(f"Starting Flask app on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)