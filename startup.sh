#!/bin/bash

# setup daily update task and cron
echo "0 15 * * 1-5 curl -X POST http://localhost:5001/api/update_data >> /var/log/cron.log 2>&1" > /etc/cron.d/stock-cron

chmod 0644 /etc/cron.d/stock-cron
crontab /etc/cron.d/stock-cron
service cron start

python app.py &
streamlit run client.py --server.port=8501 --server.address=0.0.0.0