# 使用輕量級 Python 映像檔 (my python interpreter is 3.13.12)
FROM python:3.13-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統套件：curl (觸發API用) 與 cron (定時任務用)
RUN apt-get update && apt-get install -y \
    curl \
    cron \
    && rm -rf /var/lib/apt/lists/*

# 複製需求文件並安裝 Python 函式庫
# 建議先建立 requirements.txt 包含 streamlit, pandas, plotly, flask/fastapi 等
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案所有原始碼到容器內
COPY . .

# 給予啟動腳本執行權限
RUN chmod +x startup.sh

# 開放 Streamlit 預設埠號與後端 API 埠號
EXPOSE 8501
EXPOSE 5001

# 使用啟動腳本作為入口點
CMD ["./startup.sh"]