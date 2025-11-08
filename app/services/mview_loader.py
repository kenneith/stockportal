
import os
import threading
from typing import Dict, List, Optional, Any
import pandas as pd

# Resolve data path robustly
_ENV_PATH = os.environ.get("MVIEW_XLSX_PATH", "").strip()

# project base = .../app/services/ -> go up two -> project root
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))

_CANDIDATES = []
if _ENV_PATH:
    _CANDIDATES.append(_ENV_PATH)
# common locations relative to project
_CANDIDATES.append(os.path.join(_PROJ_ROOT, "data", "mview.xlsx"))
# cwd/data for cases uvicorn runs from another cwd
_CANDIDATES.append(os.path.join(os.getcwd(), "data", "mview.xlsx"))
# also allow app/data (if someone placed it there)
_CANDIDATES.append(os.path.join(_PROJ_ROOT, "app", "data", "mview.xlsx"))

def _resolve_data_file() -> str:
    for p in _CANDIDATES:
        if p and os.path.exists(p):
            return p
    # default to project-root/data
    return os.path.join(_PROJ_ROOT, "data", "mview.xlsx")

_DATA_FILE = _resolve_data_file()
_SHEET = "DailyScreening"

_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {
    "df": None,
    "counts": {f"M{i}": 0 for i in range(9)},
}

DAILY_NAME_MAP = [
    "KD 隨機指標1",
    "KD 隨機指標2",
    "RSI 相對強弱指標1",
    "RSI 相對強弱指標2",
    "MACD 平滑異同移動平均線",
    "PSY 心理線",
    "BIAS 乖離率",
    "W%R 威廉指標",
    "MA 移動平均",
]

MONTHLY_NAME_MAP_BASED_ON_DOT1 = [
    "KD 隨機指標1",
    "KD 隨機指標2",
    "RSI 相對強弱指標1",
    "RSI 相對強弱指標2",
    "MACD 平滑異同移動平均線",
    "PSY 心理線",
    "BIAS 乖離率",
    "W%R 威廉指標",
    "MA 移動平均",
]

MONTHLY_FIN_RATIO = [
    "ROE 股東權益報酬率",
    "Debt Ratio 負債比率",
    "Current Ratio 流動比率",
    "Quick Ratio 速動比率",
]

def _color_from_signal(signal: Optional[str], score: Optional[float]) -> str:
    s = None if signal is None else str(signal).strip().upper()
    if s in {"B", "1"} or (score is not None and str(score).strip() == "1"):
        return "red"
    if s in {"S", "0"} or (score is not None and str(score).strip() == "0"):
        return "green"
    return "gray"

def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["公司代號","公司簡稱","產業名稱","M9","操作方向"])

def _safe_read_excel(path: str) -> pd.DataFrame:
    try:
        return pd.read_excel(path, sheet_name=_SHEET)
    except Exception as e:
        print(f"[mview_loader] WARN: read_excel failed for '{path}': {e}")
        return _empty_df()

def _ensure_loaded() -> pd.DataFrame:
    with _LOCK:
        if _CACHE["df"] is not None:
            return _CACHE["df"]
        path = _resolve_data_file()
        if not os.path.exists(path):
            print(f"[mview_loader] INFO: data file not found, using empty frame. tried: {path}")
            df = _empty_df()
        else:
            df = _safe_read_excel(path)

        if "M9" in df.columns:
            df["M9"] = pd.to_numeric(df["M9"], errors="coerce").fillna(-1).astype(int)
        else:
            df["M9"] = -1

        for col in ["公司代號","公司簡稱","產業名稱","操作方向"]:
            if col in df.columns:
                df[col] = df[col].astype(str)
            else:
                df[col] = ""

        counts = {f"M{i}": int((df["M9"] == i).sum()) for i in range(9)}
        _CACHE["df"] = df
        _CACHE["counts"] = counts
        print(f"[mview_loader] INFO: loaded rows={df.shape[0]} from {_resolve_data_file()} counts={counts}")
        return df

def reload_excel_from_bytes(b: bytes) -> Dict[str, Any]:
    path = _resolve_data_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b)
    with _LOCK:
        _CACHE["df"] = None
        _CACHE["counts"] = {f"M{i}": 0 for i in range(9)}
    _ensure_loaded()
    return {
        "path": path,
        "counts": _CACHE["counts"],
        "rows": int(_CACHE["df"].shape[0]) if _CACHE["df"] is not None else 0
    }

def get_tabs() -> Dict[str, Any]:
    _ensure_loaded()
    return {"tabs":[f"M{i}" for i in range(9)], "counts": _CACHE["counts"]}

def list_stocks_by_tab(tab: int) -> List[Dict[str, Any]]:
    df = _ensure_loaded()
    sub = df[df["M9"] == tab] if tab in range(9) else df[df["M9"] < 0]
    out = []
    for _, r in sub.iterrows():
        out.append({
            "ticker": r.get("公司代號", ""),
            "name": r.get("公司簡稱", ""),
            "industry": r.get("產業名稱", ""),
            "action": r.get("操作方向", ""),
        })
    return out

def _get_indicator(df_row: pd.Series, base: str, monthly: bool=False) -> Optional[Dict[str, Any]]:
    if monthly:
        val_col = f"{base}_數值.1"
        score_col = f"{base}_得分"
        sig_col = f"{base}_操作方向.1"
        value = df_row.get(val_col, None)
        score = df_row.get(score_col, None)
        signal = df_row.get(sig_col, None)
        if pd.isna(value): value = None
        if pd.isna(score): score = None
        if pd.isna(signal): signal = None
        if value is None and score is None and signal is None:
            return None
        return {
            "name": base,
            "value": value,
            "score": score,
            "signal": signal,
            "color": _color_from_signal(signal, score),
        }
    else:
        val_col = f"{base}_數值"
        sig_col = f"{base}_操作方向"
        value = df_row.get(val_col, None)
        signal = df_row.get(sig_col, None)
        if pd.isna(value): value = None
        if pd.isna(signal): signal = None
        if value is None and signal is None:
            return None
        return {
            "name": base,
            "value": value,
            "signal": signal,
            "color": _color_from_signal(signal, None),
        }

def _get_ratio(df_row: pd.Series, base: str) -> Optional[Dict[str, Any]]:
    val_col = f"{base}_數值"
    score_col = f"{base}_得分"
    value = df_row.get(val_col, None)
    score = df_row.get(score_col, None)
    if pd.isna(value): value = None
    if pd.isna(score): score = None
    if value is None and score is None:
        return None
    return {"name": base, "value": value, "score": score, "color": _color_from_signal(None, score)}

def get_stock_detail(ticker: str) -> Dict[str, Any]:
    df = _ensure_loaded()
    sub = df[df["公司代號"].astype(str) == str(ticker)]
    if sub.empty:
        sub = df[df["公司簡稱"].astype(str) == str(ticker)]
    if sub.empty:
        return {"ticker": ticker, "name": "", "daily": [], "monthly": []}
    row = sub.iloc[0]

    daily = []
    for base in DAILY_NAME_MAP:
        it = _get_indicator(row, base, monthly=False)
        if it: daily.append(it)

    monthly = []
    for base in MONTHLY_NAME_MAP_BASED_ON_DOT1:
        it = _get_indicator(row, base, monthly=True)
        if it: monthly.append(it)
    for base in MONTHLY_FIN_RATIO:
        it = _get_ratio(row, base)
        if it: monthly.append(it)

    return {
        "ticker": row.get("公司代號", ""),
        "name": row.get("公司簡稱", ""),
        "daily": daily,
        "monthly": monthly,
    }
