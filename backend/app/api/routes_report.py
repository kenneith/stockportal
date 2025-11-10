
from typing import Dict, Any
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from ..core.graph_client import upsert_report_summary

router = APIRouter(tags=["report"])

@router.post("/sessions/{session_id}/report/graph-sync")
async def sync_report_to_graph(session_id: str, payload: Dict[str, Any] = Body(...)):
    """
    預留給報表頁面呼叫：將調整後的 MTO 報表摘要寫入 Neo4j。
    """
    try:
        upsert_report_summary(session_id, payload or {})
    except Exception:
        # 圖譜更新失敗不致命
        pass
    return JSONResponse({"status": "ok", "session_id": session_id})


from fastapi.responses import StreamingResponse
from io import BytesIO
from datetime import datetime

try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None  # type: ignore


@router.post("/sessions/{session_id}/report/export-excel")
async def export_report_excel(session_id: str, payload: Dict[str, Any] = Body(...)):
    """
    依目前估料報表內容匯出簡單的 Excel 檔案：
    - 一個工作表包含大梁 / 小梁 / 柱三種型態
    """
    report = payload.get("report") if isinstance(payload, dict) else None
    if report is None:
        report = payload or {}

    if Workbook is None:
        # 若環境尚未安裝 openpyxl，回傳明確錯誤訊息
        return JSONResponse(
            {
                "status": "error",
                "message": "後端尚未安裝 openpyxl，請先安裝 `pip install openpyxl` 後重新啟動。",
            },
            status_code=500,
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "估料彙總"

    # 標題列
    headers = ["分類", "構件名稱", "規格/型號", "長度 (m)", "數量", "重量 (t)"]
    ws.append(headers)

    def append_rows(section_key: str, label: str):
        rows = report.get(section_key) or []
        for r in rows:
            ws.append(
                [
                    label,
                    r.get("name", ""),
                    r.get("spec", ""),
                    r.get("length", 0),
                    r.get("quantity", 0),
                    r.get("weight", 0),
                ]
            )

    append_rows("majorBeams", "大梁")
    append_rows("minorBeams", "小梁")
    append_rows("columns", "柱")

    # 自動調整欄寬（簡單估計）
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                v = str(cell.value) if cell.value is not None else ""
            except Exception:
                v = ""
            max_len = max(max_len, len(v))
        ws.column_dimensions[col_letter].width = max(10, min(max_len + 2, 40))

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    filename = f"mto_report_{session_id}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    headers_resp = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers_resp,
    )

