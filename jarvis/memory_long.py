from __future__ import annotations

from jarvis.store import connect, migrate, utc_now


def add_memory(content: str, kind: str = "note", importance: int = 1) -> dict[str, object]:
    migrate()
    text = content.strip()
    if not text:
        raise ValueError("пусто")
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO memories(kind, content, importance, created_at, updated_at) VALUES(?,?,?,?,?)",
            (kind, text, max(1, min(5, importance)), now, now),
        )
        ident = int(cur.lastrowid or 0)
    return {"id": ident, "kind": kind, "content": text, "created_at": now}


def list_memories(query: str = "", limit: int = 50) -> list[dict[str, object]]:
    migrate()
    sql = "SELECT id, kind, content, importance, created_at, updated_at FROM memories"
    params: list[object] = []
    if query.strip():
        sql += " WHERE content LIKE ?"
        params.append(f"%{query.strip()}%")
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def delete_memory(ident: int) -> bool:
    migrate()
    with connect() as conn:
        cur = conn.execute("DELETE FROM memories WHERE id=?", (ident,))
        return cur.rowcount > 0


def recall_text(query: str = "") -> str:
    items = list_memories(query=query, limit=8)
    if not items:
        return "В долговременной памяти пока пусто."
    lines = ["Вот что я помню:"]
    for item in items:
        lines.append(f"— {item['content']}")
    return "\n".join(lines)
