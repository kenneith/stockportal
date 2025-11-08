
# [patched 2025-09-30] normalize Chinese XLSX headers
from services.field_mapper import normalize_row
import services.mview_loader as mview_loader
from fastapi import FastAPI, Request, Depends, UploadFile, File, HTTPException, Response
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine
import os, io, time, pandas as pd, requests, secrets
from datetime import datetime, timedelta
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(ROOT_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'app.db')
XLSX_PATH = os.path.join(DATA_DIR, 'indicators.xlsx')

app = FastAPI(title="Stock Portal")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR,"static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR,"templates"))

# --- XLSX helpers: normalize headers and sheets ---
STOCKS_STD = ["category","ticker","name","market","industry","latest_price","latest_date","說明"]
FUND_STD = ["ticker","指標","數值","判斷","規則","說明"]
TECH_STD = ["ticker","指標","數值","判斷","規則"]

# === Patched helpers (2025-09-30) ===
TECH_KEYS = ["MA","KD","MACD","RSI","PSY","BIAS","W%R","BBANDS","OBV"]
FUND_KEYS = ["ROE","負債比率","利息保障倍數","流動比率","速動比率","殖利率","本益比","P_B"]

def _from_stocks_sheet(df: pd.DataFrame):
    # df columns include meta + *_數值/*_分析
    # Build stocks (category,ticker,name,market,industry,latest)
    stocks = pd.DataFrame({
        "category": df.get("主標籤", df.get("模型", "")),
        "ticker": df.get("股票代號"),
        "name": df.get("股票簡稱"),
        "market": df.get("市場別"),
        "industry": df.get("產業名稱"),
        "latest_price": df.get("最新股價"),
        "latest_date": df.get("最新日期"),
        "說明": df.get("說明"),
    }).dropna(subset=["ticker"])

    def build_long(keys):
        rows = []
        for _, row in df.iterrows():
            t = str(row.get("股票代號", "")).strip()
            if not t: continue
            for key in keys:
                val = row.get(f"{key}_數值", None)
                judge = row.get(f"{key}_分析", None)
                if pd.isna(val) and pd.isna(judge):
                    continue
                rows.append({"ticker": t, "指標": key, "數值": val, "判斷": judge, "規則": ""})
        return pd.DataFrame(rows)

    fundamentals = build_long(FUND_KEYS)
    technicals = build_long(TECH_KEYS)
    return {"stocks": stocks, "fundamentals": fundamentals, "technicals": technicals}

def _normalize_columns(df: pd.DataFrame):
    # unify headers (lower/strip) and map common aliases
    alias = {
        "分類":"category","category":"category","類別":"category","主分類":"category",
        "ticker":"ticker","代碼":"ticker","股票代碼":"ticker","證券代號":"ticker","股票":"ticker",
        "name":"name","名稱":"name","股票名稱":"name","公司":"name","公司名稱":"name",
        # fundamentals/technicals common aliases
        "indicator":"指標","指標":"指標",
        "value":"數值","數值":"數值","值":"數值",
        "judge":"判斷","判斷":"判斷","結論":"判斷","分析":"判斷",
        "rule":"規則","規則":"規則","準則":"規則","判定規則":"規則"
    }
    new_cols = []
    for c in df.columns:
        key = str(c).strip().lower()
        mapped = alias.get(key, None)
        if mapped is None:
            # try raw header without lowering if Chinese present
            mapped = alias.get(str(c).strip(), str(c).strip())
        new_cols.append(mapped)
    df.columns = new_cols
    return df

def _sheet_like_stocks(df: pd.DataFrame) -> bool:
    cols = set(df.columns)
    return ("ticker" in cols) and (("category" in cols) or ("分類" in cols)) and (("name" in cols) or ("名稱" in cols))

def load_xlsx():
    if not os.path.exists(XLSX_PATH):
        return {"stocks": pd.DataFrame(columns=STOCKS_STD),
                "fundamentals": pd.DataFrame(columns=FUND_STD),
                "technicals": pd.DataFrame(columns=TECH_STD)}
    x = pd.ExcelFile(XLSX_PATH)
    sheets = {s: pd.read_excel(x, sheet_name=s) for s in x.sheet_names}
    # If only 'stocks' provided (wide), split into 3
    if set(sheets.keys()) == {'stocks'}:
        wide = sheets['stocks']
        # keep original headers (Chinese)
        split = _from_stocks_sheet(wide)
        return split
    # normalize generic
    sheets = {k: _normalize_columns(v if isinstance(v, pd.DataFrame) else pd.DataFrame(v)) for k,v in sheets.items()}

    # resolve stocks sheet
    stocks = sheets.get("stocks")
    if stocks is None or stocks.empty or not _sheet_like_stocks(stocks):
        # try to find a sheet that looks like stocks
        candidate = None
        for name, df in sheets.items():
            if isinstance(df, pd.DataFrame) and not df.empty and _sheet_like_stocks(df):
                candidate = df; break
        stocks = candidate if candidate is not None else pd.DataFrame(columns=STOCKS_STD)
    # enforce standard columns (safe subset/select + fill missing)
    if not stocks.empty:
        for need in STOCKS_STD:
            if need not in stocks.columns: stocks[need] = ""
        stocks = stocks[STOCKS_STD]

    # fundamentals
    fund = sheets.get("fundamentals", pd.DataFrame())
    if fund.empty:
        # try alternative names
        alt = ["fund","funds","fundamental","基本面","fundamental_indicators"]
        for a in alt:
            if a in sheets and isinstance(sheets[a], pd.DataFrame) and not sheets[a].empty:
                fund = sheets[a]; break
    if not fund.empty:
        for need in FUND_STD:
            if need not in fund.columns: fund[need] = ""
        fund = fund[FUND_STD]
    else:
        fund = pd.DataFrame(columns=FUND_STD)

    # technicals
    tech = sheets.get("technicals", pd.DataFrame())
    if tech.empty:
        alt = ["tech","technical","技術面","technicals_indicators"]
        for a in alt:
            if a in sheets and isinstance(sheets[a], pd.DataFrame) and not sheets[a].empty:
                tech = sheets[a]; break
    if not tech.empty:
        for need in TECH_STD:
            if need not in tech.columns: tech[need] = ""
        tech = tech[TECH_STD]
    else:
        tech = pd.DataFrame(columns=TECH_STD)

    return {"stocks": stocks, "fundamentals": fund, "technicals": tech}


# --- DB ---
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with engine.begin() as conn:
        conn.exec_driver_sql("""CREATE TABLE IF NOT EXISTS serials(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            level INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            active INTEGER NOT NULL DEFAULT 1
        );""")
        conn.exec_driver_sql("""CREATE TABLE IF NOT EXISTS sessions(
            token TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            level INTEGER NOT NULL,
            role TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );""")
        conn.exec_driver_sql("""CREATE TABLE IF NOT EXISTS config(
            k TEXT PRIMARY KEY,
            v TEXT
        );""")
        seed = [
            ("ADMIN-0000-TEST", 4, "admin", 1),
            ("LV1-TEST-0001", 1, "user", 1),
            ("LV4-TEST-9999", 4, "user", 1),
        ]
        for s in seed:
            try:
                conn.exec_driver_sql("INSERT INTO serials(code,level,role,active) VALUES(?,?,?,?)", s)
            except Exception:
                pass

init_db()

SESSION_COOKIE = "sp_session"

def get_session(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token: return None
    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT token,code,level,role,created_at FROM sessions WHERE token=?", (token,)).fetchone()
        if not row: return None
        return dict(row._mapping)

def require_user(request: Request):
    s = get_session(request)
    if not s: raise HTTPException(status_code=401, detail="unauth")
    return s

def require_admin(request: Request):
    s = get_session(request)
    if not s or s["role"] != "admin": raise HTTPException(status_code=401, detail="admin only")
    return s

# --- Pages ---
@app.get("/", response_class=HTMLResponse)
def page_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
def page_admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/mview", response_class=HTMLResponse)
def page_mview(request: Request):
    # 新的多頁籤指標檢視頁面
    return templates.TemplateResponse("mview.html", {"request": request})

# --- Auth ---
@app.post("/api/auth/login")
def auth_login(payload: dict, response: Response):
    code = (payload.get("serial") or "").strip()
    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT code, level, role, active FROM serials WHERE code=?", (code,)).fetchone()
        if not row or row.active != 1: raise HTTPException(401, "invalid serial")
        token = secrets.token_urlsafe(24)
        conn.exec_driver_sql("INSERT INTO sessions(token,code,level,role,created_at) VALUES(?,?,?,?,?)",
                             (token, row.code, row.level, row.role, int(time.time())))
    response = JSONResponse({"code": row.code, "level": row.level})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return response

@app.post("/api/admin/auth/login")
def admin_login(payload: dict, response: Response):
    code = (payload.get("serial") or "").strip()
    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT code, level, role, active FROM serials WHERE code=?", (code,)).fetchone()
        if not row or row.role != "admin" or row.active != 1: raise HTTPException(401, "invalid admin serial")
        token = secrets.token_urlsafe(24)
        conn.exec_driver_sql("INSERT INTO sessions(token,code,level,role,created_at) VALUES(?,?,?,?,?)",
                             (token, row.code, row.level, row.role, int(time.time())))
    response = JSONResponse({"code": row.code, "level": row.level})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return response

# --- XLSX ---
LEVEL_GATE = {"歷史":1, "價值型":2, "成長型":3, "題材型":4}

def _normalize_str(x):
    if x is None: return ""
    s = str(x).strip()
    # unify full-width/half-width spaces
    s = s.replace("\u3000"," ").strip()
    return s

def normalize_category_value(raw):
    s = _normalize_str(raw)
    # tolerate synonyms / partials
    mapping = {
        "歷史": "歷史",
        "價值": "價值型",
        "價值型": "價值型",
        "成長": "成長型",
        "成長型": "成長型",
        "題材": "題材型",
        "題材型": "題材型",
    }
    # direct match
    if s in mapping: return mapping[s]
    # contains match
    for k,v in mapping.items():
        if k in s: return v
    return s  # fallback to raw (will be filtered out if not in LEVEL_GATE)


@app.get("/api/categories")
def api_categories(s=Depends(require_user)):
    dfs = load_xlsx()
    df = dfs["stocks"]
    items = []
    if isinstance(df, pd.DataFrame) and not df.empty:
        if "category" in df.columns:
            df = df.copy()
            df["category"] = df["category"].apply(normalize_category_value)
            # drop rows missing ticker or name
            if "ticker" in df.columns:
                df = df[df["ticker"].astype(str).str.len()>0]
    for cat, need in LEVEL_GATE.items():
        if s["level"] >= need:
            rows = pd.DataFrame(columns=["ticker","name"])
            if isinstance(df, pd.DataFrame) and not df.empty and "category" in df.columns:
                rows = df[df["category"]==cat][[c for c in ["ticker","name","market","industry","latest_price","latest_date"] if c in df.columns]].fillna("") if set(["ticker","name"]).issubset(df.columns) else pd.DataFrame(columns=["ticker","name"])
            items.append({"name": cat, "stocks": rows.to_dict(orient="records")})
    return {"categories": items}

@app.get("/api/indicators/{ticker}")
def api_indicators(ticker: str, s=Depends(require_user)):
    dfs = load_xlsx()
    fund = dfs["fundamentals"]
    tech = dfs["technicals"]
    key = str(ticker).strip()
    try:
        fund2 = fund.copy()
        fund2["ticker"] = fund2["ticker"].astype(str).str.strip()
    except Exception:
        fund2 = fund
    try:
        tech2 = tech.copy()
        tech2["ticker"] = tech2["ticker"].astype(str).str.strip()
    except Exception:
        tech2 = tech
    frows = fund2[ fund2["ticker"] == key ].fillna("")
    trows = tech2[ tech2["ticker"] == key ].fillna("")

    logger.info(f"=== DEBUG: fundamentals row === {frows.iloc[0].to_dict()}")
    if not frows.empty:
        print(frows.iloc[0].to_dict())
    else:
        print("fundamentals row is EMPTY")

    # 先從 fundamentals、technicals 的「判斷」欄位推導 summary_txt
    def _cnt(df):
        try:
            col = df.get("判斷")
            if col is None:
                return 0, 0
            pos = int(col.astype(str).str.contains("偏多", na=False).sum())
            neg = int(col.astype(str).str.contains("偏空", na=False).sum())
            return pos, neg
        except Exception as e:
            print("=== DEBUG: _cnt exception ===", e)
            return 0, 0

    p1, n1 = _cnt(frows)
    p2, n2 = _cnt(trows)
    pos_total, neg_total = p1 + p2, n1 + n2
    if pos_total > neg_total:
        summary_txt = "偏多"
    elif neg_total > pos_total:
        summary_txt = "偏空"
    else:
        summary_txt = "觀望"

    # 從 fundamentals 嘗試讀取「綜合判斷」
    summary_val = None
    if not frows.empty:
        rfund = frows.iloc[0].to_dict()
        summary_val = rfund.get("綜合判斷") or rfund.get("summary")
        logger.info(f"=== DEBUG: summary_val from fundamentals === {summary_val}")

        # 取出「說明」欄位（若無則空字串）
    desc = ""
    if not frows.empty:
        try:
            desc = (frows.iloc[0].get("說明") or "").strip()
        except Exception:
            desc = ""

    # 若基本面無說明，嘗試從 stocks 取
    if not desc:
        try:
            dfs_all2 = load_xlsx()
            if "stocks" in dfs_all2 and not dfs_all2["stocks"].empty:
                s2 = dfs_all2["stocks"].copy()
                try:
                    s2["ticker"] = s2["ticker"].astype(str).str.strip()
                except Exception:
                    pass
                row = s2[ s2["ticker"] == key ]
                if not row.empty:
                    val = row.iloc[0].get("說明")
                    if val:
                        desc = str(val).strip()
        except Exception:
            pass

# 再組 meta
    meta = {}
    dfs_all = load_xlsx()
    if "stocks" in dfs_all and not dfs_all["stocks"].empty:
        row = dfs_all["stocks"][ dfs_all["stocks"]["ticker"] == ticker ]
        if not row.empty:
            r0 = row.iloc[0].to_dict()
            meta = {
                "ticker": r0.get("ticker"),
                "name": r0.get("name"),
                "market": r0.get("market") or r0.get("市場別"),
                "industry": r0.get("industry") or r0.get("產業名稱"),
                "latest_price": r0.get("最新股價") or r0.get("latest_price"),
                "latest_date": r0.get("最新日期") or r0.get("latest_date"),
                "summary": summary_val or r0.get("綜合判斷") or r0.get("summary") or summary_txt
            }

    logger.info(f"=== DEBUG: final meta === {meta}")

    return {
        "fundamentals": frows.to_dict(orient="records"),
        "technicals": trows.to_dict(orient="records"),
        "meta": meta,
        "summary": meta.get("summary") or summary_txt,
        "說明": desc
    }


# --- FinMind ---
def get_finmind_token():
    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT v FROM config WHERE k='finmind_token'").fetchone()
        return None if not row else row[0]

@app.get("/api/series/{ticker}")
def api_series(ticker: str, days: int = 60, s=Depends(require_user)):
    token = get_finmind_token()
    if not token:
        raise HTTPException(400, "FinMind token not set")
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": ticker.split('.')[0],
        "start_date": (datetime.today()-timedelta(days=days*2)).strftime("%Y-%m-%d"),
        "token": token
    }
    r = requests.get("https://api.finmindtrade.com/api/v4/data", params=params, timeout=20)
    if r.status_code != 200:
        raise HTTPException(502, "finmind error")
    js = r.json()
    if not js.get("data"):
        return []
    df = pd.DataFrame(js["data"]).tail(days)
    out = []
    for _, row in df.iterrows():
        out.append({
            "date": str(row["date"]),
            "open": float(row["open"]),
            "max": float(row["max"]),
            "min": float(row["min"]),
            "close": float(row["close"]),
            "volume_lots": float(row.get("Trading_Volume", 0))/1000.0
        })
    return out

# --- Admin APIs ---
@app.get("/api/admin/serials")
def admin_list_serials(a=Depends(require_admin)):
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("SELECT id,code,level,role,active FROM serials ORDER BY id DESC").fetchall()
        items = [dict(r._mapping) for r in rows]
    return {"items": items}

@app.post("/api/admin/serials")
def admin_add_serial(payload: dict, a=Depends(require_admin)):
    code = (payload.get("code") or "").strip()
    level = int(payload.get("level") or 1)
    if not code: raise HTTPException(400, "code required")
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO serials(code,level,role,active) VALUES(?,?,?,1)", (code, level, "user"))
    return {"ok": True}

@app.delete("/api/admin/serials/{sid}")
def admin_del_serial(sid: int, a=Depends(require_admin)):
    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM serials WHERE id=?", (sid,))
    return {"ok": True}

@app.get("/api/admin/finmind")
def admin_get_finmind(a=Depends(require_admin)):
    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT v FROM config WHERE k='finmind_token'").fetchone()
        return {"token": None if not row else row[0]}

@app.post("/api/admin/finmind")
def admin_set_finmind(payload: dict, a=Depends(require_admin)):
    token = (payload.get("token") or "").strip()
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO config(k,v) VALUES('finmind_token', ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (token,))
    return {"ok": True}

@app.get("/api/admin/xlsx/download")
def admin_download_xlsx(a=Depends(require_admin)):
    if not os.path.exists(XLSX_PATH):
        raise HTTPException(404, "no xlsx")
    return FileResponse(XLSX_PATH, filename="indicators.xlsx")

@app.post("/api/admin/xlsx/upload")
def admin_upload_xlsx(file: UploadFile = File(...), a=Depends(require_admin)):
    content = file.file.read()
    with open(XLSX_PATH, "wb") as f:
        f.write(content)
    return {"ok": True}




# --- M-View APIs ---
@app.get("/api/mview/tabs")
def api_mview_tabs(u=Depends(require_user)):
    """回傳 M0~M8 分頁與各分頁股票數量。"""
    return mview_loader.get_tabs()


@app.get("/api/mview/stocks")
def api_mview_stocks(tab: str = "M0", u=Depends(require_user)):
    if not tab.startswith("M") or not tab[1:].isdigit():
        raise HTTPException(status_code=400, detail="tab must be M0..M8")
    idx = int(tab[1:])
    return mview_loader.list_stocks_by_tab(idx)


@app.get("/api/mview/stock/{ticker}")
def api_mview_stock_detail(ticker: str, u=Depends(require_user)):
    return mview_loader.get_stock_detail(ticker)


@app.post("/api/admin/mxlsx/upload")
def api_admin_upload_mxlsx(file: UploadFile = File(...), a=Depends(require_admin)):
    """後台上傳 M-View 專用的 Excel（DailyScreening）。"""
    content = file.file.read()
    info = mview_loader.reload_excel_from_bytes(content)
    return {"ok": True, **info}

@app.get("/api/admin/xlsx/preview")
def admin_preview(a=Depends(require_admin)):
    dfs = load_xlsx()
    df = dfs["stocks"]
    if isinstance(df, pd.DataFrame) and not df.empty and "category" in df.columns:
        df = df.copy()
        df["category"] = df["category"].apply(normalize_category_value)
        counts = df["category"].value_counts().to_dict()
        sample = df.head(20).to_dict(orient="records")
    else:
        counts = {}
        sample = []
    return {"counts": counts, "sample": sample}
