from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .settings_store import load_settings

try:
    from neo4j import GraphDatabase, Driver  # type: ignore
except Exception:  # neo4j 為可選依賴
    GraphDatabase = None  # type: ignore
    Driver = None  # type: ignore

_driver: Optional["Driver"] = None


def get_driver() -> Optional["Driver"]:
    """
    依目前設定建立或取得 Neo4j driver。
    若未設定 URI / 帳號或未安裝 neo4j 套件，則回傳 None。
    """
    global _driver

    if GraphDatabase is None:  # type: ignore
        return None

    if _driver is not None:
        return _driver

    cfg = load_settings()
    uri = cfg.get("neo4j_uri") or ""
    user = cfg.get("neo4j_user") or ""
    password = cfg.get("neo4j_password") or ""

    if not uri or not user:
        return None

    try:
        _driver = GraphDatabase.driver(uri, auth=(user, password))  # type: ignore
    except Exception:
        _driver = None
    return _driver


def upsert_page_analysis(
    session_id: str,
    page_index: int,
    page_type: Optional[str],
    result: Dict[str, Any],
) -> None:
    """
    將單頁解析結果寫入圖譜（若 driver 不可用則直接略過）。
    """
    driver = get_driver()
    if driver is None:
        return

    payload = json.dumps(result, ensure_ascii=False)

    cypher = """
    MERGE (p:Project {session_id: $session_id})
    MERGE (pg:Page {session_id: $session_id, page_index: $page_index})
    MERGE (p)-[:HAS_PAGE]->(pg)
    SET pg.page_type = $page_type,
        pg.raw_json = $payload
    """

    with driver.session() as session:
        session.run(
            cypher,
            session_id=session_id,
            page_index=page_index,
            page_type=page_type or "",
            payload=payload,
        )


def upsert_report_summary(session_id: str, report: Dict[str, Any]) -> None:
    """
    將報表摘要寫入 Project 節點。
    """
    driver = get_driver()
    if driver is None:
        return

    payload = json.dumps(report, ensure_ascii=False)

    cypher = """
    MERGE (p:Project {session_id: $session_id})
    SET p.mto_summary = $payload
    """

    with driver.session() as session:
        session.run(
            cypher,
            session_id=session_id,
            payload=payload,
        )


def query_project_context(session_id: str) -> str:
    """
    從圖譜取得與指定 session 相關的摘要文字，提供給智能助理當作 context。
    """
    driver = get_driver()
    if driver is None:
        return ""

    cypher = """
    MATCH (p:Project {session_id: $session_id})
    OPTIONAL MATCH (p)-[:HAS_PAGE]->(pg:Page)
    RETURN p.mto_summary AS summary, collect(pg.raw_json) AS pages
    """

    summary = ""
    pages: list[str] = []

    with driver.session() as session:
        record = session.run(cypher, session_id=session_id).single()
        if record:
            summary = record.get("summary") or ""
            raw_pages = record.get("pages") or []
            pages = [p for p in raw_pages if isinstance(p, str)]

    parts: list[str] = []
    if summary:
        parts.append("專案彙總: " + summary)

    if pages:
        head = pages[:5]
        parts.append("部分頁面解析內容: " + "\n".join(head))

    return "\n\n".join(parts)
