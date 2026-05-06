#!/bin/bash

# 1. 設定定時任務 (確保依照 TZ 變數執行的時間正確)[cite: 5, 9]
echo "0 15 * * 1-5 curl -X POST http://localhost:5001/api/update_data >> /var/log/cron.log 2>&1" > /etc/cron.d/stock-cron

# 2. 啟動 Cron 服務[cite: 9]
chmod 0644 /etc/cron.d/stock-cron
crontab /etc/cron.d/stock-cron
service cron start

# 3. 啟動後端 API (監聽 0.0.0.0)[cite: 10]
python app.py &

# 4. 啟動前端 UI (加上 0.0.0.0 綁定與 headless 模式)[cite: 9, 11]
streamlit run client.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true

# 保持腳本運行
wait -n