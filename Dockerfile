# 使用輕量版 Python
FROM python:3.11-slim

# 讓 Python 在容器裡輸出立即刷新（log 不卡）
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 建立工作目錄 /app（後續所有路徑都相對這裡）
WORKDIR /app

# 先把 requirements.txt 複製進來並安裝依賴（這樣有快取，加速 build）
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 再把專案整包進來
COPY . /app

# 確保資料夾存在（等等要 mount Volume 到這個路徑）
RUN mkdir -p /app/stockportal/data

# Railway 會注入 PORT 環境變數；我們用 shell 指令展開 ${PORT}
# 這裡使用 sh -c 方式，能吃到動態的 PORT；本地沒 PORT 時就用 8000
CMD sh -c "uvicorn stockportal.app.main:app --host 0.0.0.0 --port \${PORT:-8000}"