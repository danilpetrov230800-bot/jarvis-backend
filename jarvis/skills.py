from __future__ import annotations

import json
import re
from typing import Any

from jarvis.desktop import ActionResult, open_app, open_url
from jarvis.pc_control import handle_pc_intent
from jarvis.store import connect, migrate, utc_now


def parse_actions(text: str) -> list[dict[str, str]]:
    chunk = re.sub(r"^(то\s+)?(открой|запусти|делай|выполняй)\s+", "", text.strip(), flags=re.I)
    parts = re.split(r"\s+(?:и|потом|затем|,)\s+", chunk, flags=re.I)
    actions: list[dict[str, str]] = []
    for part in parts:
        item = part.strip(" .")
        if not item:
            continue
        lower = item.lower()
        if lower.startswith("http") or "." in item and " " not in item:
            actions.append({"type": "open_url", "value": item})
        elif "блок" in lower or "заблок" in lower:
            actions.append({"type": "lock", "value": ""})
        elif any(word in lower for word in ("громче", "тише", "ярче", "темнее", "mute", "пауза")):
            actions.append({"type": "pc", "value": lower})
        else:
            actions.append({"type": "open_app", "value": item})
    return actions or [{"type": "say", "value": chunk}]


def create_skill(name: str, trigger: str, actions: list[dict[str, str]] | None = None, action_text: str = "") -> dict[str, Any]:
    migrate()
    payload = actions or parse_actions(action_text)
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO skills(name, trigger_text, actions_json, enabled, version, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (name.strip() or trigger.strip(), trigger.strip().lower(), json.dumps(payload, ensure_ascii=False), 1, 1, now, now),
        )
        ident = int(cur.lastrowid or 0)
    return get_skill(ident)


def get_skill(ident: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM skills WHERE id=?", (ident,)).fetchone()
    if not row:
        raise KeyError("skill not found")
    data = dict(row)
    data["actions"] = json.loads(data.pop("actions_json"))
    data["enabled"] = bool(data["enabled"])
    return data


def list_skills() -> list[dict[str, Any]]:
    migrate()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM skills ORDER BY id DESC").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["actions"] = json.loads(item.pop("actions_json"))
        item["enabled"] = bool(item["enabled"])
        result.append(item)
    return result


def delete_skill(ident: int) -> bool:
    migrate()
    with connect() as conn:
        cur = conn.execute("DELETE FROM skills WHERE id=?", (ident,))
        return cur.rowcount > 0


def toggle_skill(ident: int) -> dict[str, Any]:
    skill = get_skill(ident)
    enabled = 0 if skill["enabled"] else 1
    with connect() as conn:
        conn.execute(
            "UPDATE skills SET enabled=?, version=version+1, updated_at=? WHERE id=?",
            (enabled, utc_now(), ident),
        )
    return get_skill(ident)


def run_skill(ident: int | None = None, trigger: str = "") -> ActionResult:
    migrate()
    skill = None
    if ident:
        skill = get_skill(ident)
    else:
        needle = trigger.strip().lower()
        for item in list_skills():
            if item["enabled"] and item["trigger_text"] and item["trigger_text"] in needle:
                skill = item
                break
    if not skill:
        return ActionResult(reply="Такой навык не найден.", tools=["skill_miss"])
    if not skill["enabled"]:
        return ActionResult(reply=f"Навык «{skill['name']}» выключен.", tools=["skill_off"])
    replies = []
    for action in skill["actions"]:
        kind = action.get("type")
        value = action.get("value") or ""
        if kind == "open_url":
            open_url(value)
            replies.append(f"открыла {value}")
        elif kind == "open_app":
            launched = open_app(value)
            replies.append(f"запустила {launched or value}")
        elif kind == "pc":
            pc = handle_pc_intent(value)
            replies.append(pc.reply if pc else value)
        elif kind == "lock":
            from jarvis.desktop import lock_workstation

            replies.append(lock_workstation())
        else:
            replies.append(value)
    return ActionResult(reply="Навык выполнен: " + "; ".join(replies), tools=["skill"])


def match_skill(text: str) -> ActionResult | None:
    lowered = text.strip().lower()
    for item in list_skills():
        trigger = (item.get("trigger_text") or "").strip()
        if item["enabled"] and trigger and (lowered == trigger or lowered.endswith(trigger)):
            return run_skill(ident=int(item["id"]))
    return None
