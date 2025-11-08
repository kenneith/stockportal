
# Stock Portal — M-View Patch (Tabs M0~M8 from Excel)

This patch **adds a new front-end page and back-end APIs** to your existing Stock Portal without modifying existing logic.
It introduces an **M-View** page (`/mview`) that organizes stocks into tabs **M0–M8** based on the Excel column **`M9`** and shows
**Daily** and **Monthly** indicators below the price chart. It also adds an **admin upload** API to ingest the Excel.

> Works with your uploaded Excel (sheet `DailyScreening`) like `stock-daily_update.xlsx`.
> The file will be stored at `data/mview.xlsx` (new).

---

## Files in this patch

- `app/services/mview_loader.py` — Load & cache Excel, expose query helpers.
- `app/routers/router_mview.py` — Public APIs for tabs, stock lists and indicators.
- `app/routers/router_admin_mxlsx.py` — Admin API to upload/refresh the M-View Excel.
- `app/templates/mview.html` — New page UI with tabs M0~M8 + left list + chart + indicators.
- `app/static/mview.js` — Page logic (fetch APIs, render, color rules).
- `app/static/mview.css` — Minimal styles for the new page.
- `data/.gitkeep` — Ensure `data/` exists for `mview.xlsx`.

---

## How to apply

1) **Copy** the patch folders/files into your project root, preserving paths.  
   Your tree should contain the new files under `app/services`, `app/routers`, `app/templates`, `app/static`, and `data/`.

2) **Install dependencies** (if not already present):
```
pip install pandas openpyxl
```

3) **Wire the routers** in `app/main.py` (add the two `include_router` lines):
```python
# app/main.py (add near other imports)
from app.routers.router_mview import router as mview_router
from app.routers.router_admin_mxlsx import router as admin_mxlsx_router

# ... inside create_app() or after app init:
app.include_router(mview_router, prefix="/api/mview", tags=["mview"])
app.include_router(admin_mxlsx_router, prefix="/api/admin/mxlsx", tags=["admin-mxlsx"])
```

4) **Add a route to the page** if you use Starlette/Jinja routing (example, in your existing main/router file):
```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

page_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@page_router.get("/mview", response_class=HTMLResponse)
def mview_page(request: Request):
    return templates.TemplateResponse("mview.html", {"request": request})

app.include_router(page_router)
```

> If your project already has a pattern for registering template pages, follow that style and only ensure `/mview` serves `mview.html`.

5) **Upload the Excel** in admin:
- `POST /api/admin/mxlsx/upload` with form field `file` (xlsx).  
  The service will store it as `data/mview.xlsx` and reload the cache.  
  It returns counts per tab (M0–M8) and total rows.

6) **Open the new page** at: `http://localhost:8080/mview` (adjust port to yours).

---

## API Summary

- `GET /api/mview/tabs` → `{"tabs":["M0",...,"M8"], "counts":{"M0":12,...}}`
- `GET /api/mview/stocks?tab=Mx` → `[{ticker, name, industry, action}]`
- `GET /api/mview/stock/{ticker}` → indicators:
```json
{
  "ticker": "2330",
  "name": "台積電",
  "daily": [{"name":"RSI1","value": 63.2, "signal":"B","color":"red"}, ...],
  "monthly": [{"name":"ROE","value": 26.4, "score":1, "color":"red"}, ...]
}
```

- `POST /api/admin/mxlsx/upload` → multipart form (`file=...xlsx`), returns stats.

---

## Color Rules

- **Red**: signal in `{"B","1"}` or (score==1)
- **Green**: signal in `{"S","0"}` or (score==0)
- **Gray**: others or NA

---

## Notes

- The loader looks for sheet **`DailyScreening`** and fields: `公司代號` (ticker), `公司簡稱` (name), `產業名稱`, `M9`, `操作方向` and the indicators you listed.
- For **Monthly** indicators, columns with suffix **`.1`** are treated as monthly variants; financial ratios (ROE, Debt Ratio, Current Ratio, Quick Ratio) are also monthly.
- Missing columns are skipped gracefully.
