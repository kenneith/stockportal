
import os
import threading
from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np

# 專案根目錄與資料路徑


def _to_native(v):
    """把 numpy scalar 轉成 Python 原生 int/float，其他維持原樣。"""
    if isinstance(v, np.generic):
        return v.item()
    return v

BASE_DIR = os.path.dirname(os.path.abspath(__file__))           # .../stockportal/services
ROOT_DIR = os.path.dirname(BASE_DIR)                            # .../stockportal
DATA_PATH = os.path.join(ROOT_DIR, "data", "mview.xlsx")

_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {
    "df": None,
    "counts": {f"M{i}": 0 for i in range(9)},
}

DAILY_BASES = [
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

MONTHLY_DOT1_BASES = [
    "KD 隨機指標1",
    "KD 隨機指標2",
    "RSI 相對強弱指標1",
    "RSI 相對強弱指標2",
    "MACD 平滑異同移動平均線",
    "PSY 心理線",
    "BIAS 乖離率",
    "W%R 威廉指標",
]

MONTHLY_RATIO_BASES = [
    "ROE 股東權益報酬率",
    "Debt Ratio 負債比率",
    "Current Ratio 流動比率",
    "Quick Ratio 速動比率",
]


def _color_from_signal(signal: Optional[str], score: Optional[float]) -> str:
    """
    根據「操作方向」與「得分」決定顏色：
    - 操作方向優先，其次才看得分。
    - 支援 B/S、買進/賣出、以及 1/0（含 1.0/0.0）。
    """
    # 標準化操作方向字串
    s = ""
    if signal is not None:
        s = str(signal).strip()
    s_upper = s.upper()

    # 標準化得分字串與數值
    sc_str = ""
    if score is not None:
        sc_str = str(score).strip()
    num = None
    if sc_str not in ("", "nan", "NaN", "None"):
        try:
            num = float(sc_str)
        except ValueError:
            num = None

    # 先根據操作方向判斷
    buy_signals = {"B", "BUY", "多", "偏多", "買進", "做多"}
    sell_signals = {"S", "SELL", "空", "偏空", "賣出", "做空"}

    if s_upper in buy_signals or s_upper == "1":
        return "red"
    if s_upper in sell_signals or s_upper == "0":
        return "green"

    # 再根據得分判斷（只要是 1 / 0，不論是字串或 1.0 / 0.0）
    if sc_str == "1" or num == 1.0:
        return "red"
    if sc_str == "0" or num == 0.0:
        return "green"

    # 其餘一律顯示為灰色
    return "gray"




def _normalize_action(raw: Optional[str]) -> str:
    """
    將各種操作方向代碼轉成統一的文案：
    - B / 買進 / 多 / BUY -> 「買進」
    - S / 賣出 / 空 / SELL -> 「賣出」
    - 其他或空值 -> 「觀望」
    """
    if raw is None:
        return "觀望"
    s = str(raw).strip()
    if not s:
        return "觀望"
    su = s.upper()
    if su in {"B", "BUY", "多", "偏多", "買進", "做多"}:
        return "買進"
    if su in {"S", "SELL", "空", "偏空", "賣出", "做空"}:
        return "賣出"
    # N / 觀望 / 其他 -> 統一視為觀望
    return "觀望"

def _empty_df() -> pd.DataFrame:
    # 給預設空資料時使用，欄位結構與實際 XLSX 主要欄位對齊
    cols = [
        "公司代號",
        "公司簡稱",
        "產業名稱",
        "上市櫃",
        "M9",
        "總結說明",
        "操作方向",
        "買進計數",
        "賣出計數",
        "日線時長",
        "當前交易日期",
        "當前股價",
    ]
    return pd.DataFrame(columns=cols)


def _load_df() -> pd.DataFrame:
    if not os.path.exists(DATA_PATH):
        return _empty_df()
    try:
        df = pd.read_excel(DATA_PATH, sheet_name="DailyScreening")
    except Exception as e:
        print("[mview_loader] read_excel error:", e)
        return _empty_df()

    # M9 分群欄位
    if "M9" in df.columns:
        df["M9"] = pd.to_numeric(df["M9"], errors="coerce").fillna(-1).astype(int)
    else:
        df["M9"] = -1

    # 文字欄位：統一轉成字串，NaN -> 空字串
    text_cols = ["公司代號", "公司簡稱", "產業名稱", "上市櫃", "總結說明", "操作方向"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).where(~df[col].isna(), "")

    # 若沒有出現的欄位，用預設值補齊
    for col in ["公司代號", "公司簡稱", "產業名稱", "上市櫃", "總結說明", "操作方向"]:
        if col not in df.columns:
            df[col] = ""

    return df


def _ensure_loaded() -> pd.DataFrame:
    with _LOCK:
        if _CACHE["df"] is not None:
            return _CACHE["df"]
        df = _load_df()
        counts = {f"M{i}": int((df["M9"] == i).sum()) for i in range(9)}
        _CACHE["df"] = df
        _CACHE["counts"] = counts
        print("[mview_loader] loaded rows=", df.shape[0], "from", DATA_PATH)
        return df


def reload_excel_from_bytes(b: bytes) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "wb") as f:
        f.write(b)
    with _LOCK:
        _CACHE["df"] = None
        _CACHE["counts"] = {f"M{i}": 0 for i in range(9)}
    _ensure_loaded()
    return {
        "path": DATA_PATH,
        "counts": _CACHE["counts"],
        "rows": int(_CACHE["df"].shape[0]) if _CACHE["df"] is not None else 0,
    }


def get_tabs() -> Dict[str, Any]:
    _ensure_loaded()
    return {
        "tabs": [f"M{i}" for i in range(9)],
        "counts": _CACHE["counts"],
    }


def list_stocks_by_tab(tab: int) -> List[Dict[str, Any]]:
    df = _ensure_loaded()
    if tab in range(9):
        sub = df[df["M9"] == tab]
    else:
        sub = df[df["M9"] < 0]
    out: List[Dict[str, Any]] = []
    for _, r in sub.iterrows():
        raw_action = r.get("操作方向", "")
        out.append(
            {
                "ticker": r.get("公司代號", ""),
                "name": r.get("公司簡稱", ""),
                "industry": r.get("產業名稱", ""),
                "action": _normalize_action(raw_action),
                "raw_action": raw_action,
            }
        )
    return out


def _daily_indicator(row: pd.Series, base: str) -> Optional[Dict[str, Any]]:
    v_col = f"{base}_數值"
    s_col = f"{base}_操作方向"
    val = row.get(v_col, None)
    sig = row.get(s_col, None)
    if pd.isna(val):
        val = None
    if pd.isna(sig):
        sig = None
    if val is None and sig is None:
        return None
    return {
        "name": base,
        "value": val,
        "signal": sig,
        "color": _color_from_signal(sig, None),
    }


def _monthly_indicator(row: pd.Series, base: str) -> Dict[str, Any]:
    """月指標：就算 val/score 都是空，也要回傳一筆指標名稱，顯示灰色。"""
    # 新版欄位命名：月{base}_數值 / 月{base}_得分
    v_col = f"月{base}_數值"
    s_col = f"月{base}_得分"
    val = row.get(v_col, None)
    score = row.get(s_col, None)
    if pd.isna(val):
        val = None
    if pd.isna(score):
        score = None
    # 轉成 Python 原生型別，避免 FastAPI JSON 編碼 numpy scalar 出錯
    val = _to_native(val)
    score = _to_native(score)
    color = _color_from_signal(None, score)
    return {
        "name": base,
        "value": val,
        "score": score,
        "color": color,
    }



def _ratio_indicator(row: pd.Series, base: str) -> Dict[str, Any]:
    """財務比率：即便沒有數值/得分，也一律回傳，方便前端整齊列出全部指標名稱。"""
    v_col = f"{base}_數值"
    s_col = f"{base}_得分"
    val = row.get(v_col, None)
    score = row.get(s_col, None)
    if pd.isna(val):
        val = None
    if pd.isna(score):
        score = None
    val = _to_native(val)
    score = _to_native(score)
    color = _color_from_signal(None, score)
    return {
        "name": base,
        "value": val,
        "score": score,
        "color": color,
    }



def get_stock_detail(ticker: str) -> Dict[str, Any]:
    """
    依據公司代號或簡稱取得單一股票的詳細資料：
    - 基本資訊：代號、名稱、操作方向、總結說明
    - 價格資訊：最新股價、當前交易日期、日線長度
    - 指標：日指標 / 月指標（含財務比率）
    """
    df = _ensure_loaded()
    t = str(ticker).strip()

    # 先用公司代號比對，若找不到再用公司簡稱
    sub = df[df["公司代號"].astype(str) == t]
    if sub.empty:
        sub = df[df["公司簡稱"].astype(str) == t]

    if sub.empty:
        return {
            "ticker": ticker,
            "name": "",
            "summary": "",
            "action": "觀望",
            "raw_action": "",
            "last_price": None,
            "trade_date": None,
            "daily_length": None,
            "daily": [],
            "monthly": [],
        }

    row = sub.iloc[0]

    # 日指標
    daily: List[Dict[str, Any]] = []
    for base in DAILY_BASES:
        it = _daily_indicator(row, base)
        if it:
            daily.append(it)

    # 月指標（技術 + 財務比率）
    monthly: List[Dict[str, Any]] = []
    for base in MONTHLY_DOT1_BASES:
        it = _monthly_indicator(row, base)
        if it:
            monthly.append(it)
    for base in MONTHLY_RATIO_BASES:
        it = _ratio_indicator(row, base)
        if it:
            monthly.append(it)

    # 文字總結
    summary = row.get("總結說明", "")
    try:
        if pd.isna(summary):
            summary = ""
    except Exception:
        pass
    if summary is None:
        summary = ""
    else:
        summary = str(summary)

    # 操作方向（正規化後給前端使用）
    raw_action = row.get("操作方向", "")
    try:
        if pd.isna(raw_action):
            raw_action = ""
    except Exception:
        pass
    if raw_action is None:
        raw_action = ""
    action = _normalize_action(raw_action)

    # 最新股價
    last_price = row.get("當前股價", None)
    try:
        if pd.isna(last_price):
            last_price = None
    except Exception:
        pass
    last_price = _to_native(last_price)
    if isinstance(last_price, float):
        last_price = round(last_price, 2)

    # 當前交易日期：轉成 YYYY-MM-DD 字串（若無法判斷就原樣字串）
    trade_date_raw = row.get("當前交易日期", None)
    trade_date_str: Optional[str] = None
    if trade_date_raw is not None:
        s = str(trade_date_raw).strip()
        if s:
            try:
                n = int(float(s))
                s_num = f"{n:08d}"
                trade_date_str = f"{s_num[0:4]}-{s_num[4:6]}-{s_num[6:8]}"
            except Exception:
                trade_date_str = s or None

    # 日線長度
    daily_len = row.get("日線時長", None)
    try:
        if pd.isna(daily_len):
            daily_len = None
    except Exception:
        pass
    daily_len = _to_native(daily_len)

    return {
        "ticker": row.get("公司代號", ""),
        "name": row.get("公司簡稱", ""),
        "summary": summary,
        "action": action,
        "raw_action": raw_action,
        "last_price": last_price,
        "trade_date": trade_date_str,
        "daily_length": daily_len,
        "daily": daily,
        "monthly": monthly,
    }


def _ensure_loaded() -> pd.DataFrame:
    with _LOCK:
        if _CACHE["df"] is not None:
            return _CACHE["df"]
        df = _load_df()
        counts = {f"M{i}": int((df["M9"] == i).sum()) for i in range(9)}
        _CACHE["df"] = df
        _CACHE["counts"] = counts
        print("[mview_loader] loaded rows=", df.shape[0], "from", DATA_PATH)
        return df


def reload_excel_from_bytes(b: bytes) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "wb") as f:
        f.write(b)
    with _LOCK:
        _CACHE["df"] = None
        _CACHE["counts"] = {f"M{i}": 0 for i in range(9)}
    _ensure_loaded()
    return {
        "path": DATA_PATH,
        "counts": _CACHE["counts"],
        "rows": int(_CACHE["df"].shape[0]) if _CACHE["df"] is not None else 0,
    }


def get_tabs() -> Dict[str, Any]:
    _ensure_loaded()
    return {
        "tabs": [f"M{i}" for i in range(9)],
        "counts": _CACHE["counts"],
    }


def list_stocks_by_tab(tab: int) -> List[Dict[str, Any]]:
    df = _ensure_loaded()
    if tab in range(9):
        sub = df[df["M9"] == tab]
    else:
        sub = df[df["M9"] < 0]
    out: List[Dict[str, Any]] = []
    for _, r in sub.iterrows():
        raw_action = r.get("操作方向", "")
        out.append(
            {
                "ticker": r.get("公司代號", ""),
                "name": r.get("公司簡稱", ""),
                "industry": r.get("產業名稱", ""),
                "action": _normalize_action(raw_action),
                "raw_action": raw_action,
            }
        )
    return out


def _daily_indicator(row: pd.Series, base: str) -> Optional[Dict[str, Any]]:
    v_col = f"{base}_數值"
    s_col = f"{base}_操作方向"
    val = row.get(v_col, None)
    sig = row.get(s_col, None)
    if pd.isna(val):
        val = None
    if pd.isna(sig):
        sig = None
    if val is None and sig is None:
        return None
    return {
        "name": base,
        "value": val,
        "signal": sig,
        "color": _color_from_signal(sig, None),
    }


def _monthly_indicator(row: pd.Series, base: str) -> Dict[str, Any]:
    """月指標：就算 val/score 都是空，也要回傳一筆指標名稱，顯示灰色。"""
    # 新版欄位命名：月{base}_數值 / 月{base}_得分
    v_col = f"月{base}_數值"
    s_col = f"月{base}_得分"
    val = row.get(v_col, None)
    score = row.get(s_col, None)
    if pd.isna(val):
        val = None
    if pd.isna(score):
        score = None
    # 轉成 Python 原生型別，避免 FastAPI JSON 編碼 numpy scalar 出錯
    val = _to_native(val)
    score = _to_native(score)
    color = _color_from_signal(None, score)
    return {
        "name": base,
        "value": val,
        "score": score,
        "color": color,
    }



def _ratio_indicator(row: pd.Series, base: str) -> Dict[str, Any]:
    """財務比率：即便沒有數值/得分，也一律回傳，方便前端整齊列出全部指標名稱。"""
    v_col = f"{base}_數值"
    s_col = f"{base}_得分"
    val = row.get(v_col, None)
    score = row.get(s_col, None)
    if pd.isna(val):
        val = None
    if pd.isna(score):
        score = None
    val = _to_native(val)
    score = _to_native(score)
    color = _color_from_signal(None, score)
    return {
        "name": base,
        "value": val,
        "score": score,
        "color": color,
    }



