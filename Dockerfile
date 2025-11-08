FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# 先安裝依賴（利用快取）
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 再把專案整包進來
COPY . /app

# 確保資料夾存在（你的程式會把檔案寫到 ./data）
RUN mkdir -p /app/data

# 讓 /app 成為匯入路徑根（保險起見）
ENV PYTHONPATH=/app

# 重點：module 路徑改用 app.main:app，port 用 Railway 的 $PORT
CMD sh -c "python -m uvicorn app.main:app --host 0.0.0.0 --port \${PORT:-8000}"

