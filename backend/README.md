
# SSVMI Backend

## Quick start

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Uploads and converted images are stored under `backend/data/uploads/{session_id}`.

Static files are exposed at `/static/{session_id}/{filename}` for page previews.

## VLM 設定

預設使用 stub 模式（不呼叫外部 API，只回傳示意資料）。

若要啟用 OpenAI 模型，可設定環境變數：

```bash
# Windows CMD
set VLM_PROVIDER=openai
set OPENAI_API_KEY=sk-xxx

# PowerShell
$env:VLM_PROVIDER='openai'
$env:OPENAI_API_KEY='sk-xxx'

# macOS / Linux
export VLM_PROVIDER=openai
export OPENAI_API_KEY=sk-xxx
```

目前示範使用 `gpt-4.1-mini` 並採用 Responses API，僅以文字 prompt 方式呼叫。
後續可擴充為 vision 模式，傳入圖面影像與座標資訊。
