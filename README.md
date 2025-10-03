# Stock Portal (序號分級存取 + 前後台 + XLSX 管理 + FinMind 圖表)
- Docker on Railway（不使用 .env 儲存序號/Token）。
- 前台：序號登入（Lv1~Lv4），分類標籤（歷史/價值型/成長型/題材型）→ 股票清單 → K線/收盤/量（張）→ 基本面/技術面表格（hover 顯示規則）。
- 後台：管理序號、FinMind Token、XLSX 下載/上傳。

## 本機啟動
```
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```
- 前台：/   後台：/admin

## 預設序號
- 管理者：`ADMIN-0000-TEST`
- 使用者：`LV1-TEST-0001`, `LV4-TEST-9999`

## XLSX 結構
- stocks: category(歷史/價值型/成長型/題材型), ticker, name
- fundamentals: ticker, 指標, 數值, 判斷, 規則
- technicals: ticker, 指標, 數值, 判斷, 規則
