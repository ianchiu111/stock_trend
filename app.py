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
import asyncio
from flask import Flask, request, jsonify, abort
from flask_cors import CORS

from stock.twse import TWSE


# ====================================================
twse = TWSE()

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
    部署時初始化：抓取近兩年資料
    """
    try:
        two_years_ago = (pd.Timestamp.now() - pd.DateOffset(years=2)).strftime("%Y%m%d")
        now = pd.Timestamp.now().strftime("%Y%m%d")
        
        # 在同步 Flask 中執行非同步函式
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            twse.process_range(two_years_ago, now, for_update=False)
        )
        loop.close()

        return jsonify(APIResponse.success(message=f"Initialization complete: {result}"))
    except Exception as e:
        logger.error(traceback.format_exc())
        return APIResponse.error(message="Fetch failed", details=str(e))

@app.route("/api/update_data", methods=["POST"])
def update_data():
    """
    每日更新：抓取當日資料 (或指定範圍)
    body:{
           "date": "YYYYMMDD" # default as today
    }
    """
    try:
        data = request.json or {}
        target_date = data.get("date", pd.Timestamp.now().strftime("%Y%m%d"))
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # 使用 for_update=True 確保是追加到檔案末尾
        result = loop.run_until_complete(
            twse.process_range(target_date, target_date, for_update=True)
        )
        loop.close()

        return jsonify(APIResponse.success(message=f"Update complete: {result}"))
    except Exception as e:
        logger.error(traceback.format_exc())
        return APIResponse.error(message="Update failed", details=str(e))


@app.get("/health")
def health():
    return {"status": f"server is running {version}"}


if __name__ == "__main__":
    port = 5001  # Default port
    logger.info(f"Starting Flask app on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)