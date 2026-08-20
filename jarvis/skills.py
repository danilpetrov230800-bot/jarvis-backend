from __future__ import annotations

import time
from typing import Any

from jarvis.desktop import ActionResult, handle_intent
from jarvis.storage import audit


def matching_skill(text: str) -> dict[str, Any] | None:
    from jarvis.core import list_records

    normalized = text.casefold().strip(" .,!?:")
    for skill in list_records("skills"):
        trigger = str(skill.get("trigger_text", "")).casefold().strip()
        if skill.get("enabled") and trigger and normalized == trigger:
            return skill
    return None


def execute_skill(skill: dict[str, Any], *, max_actions: int = 20) -> ActionResult:
    replies: list[str] = []
    tools: list[str] = ["skill"]
    actions = list(skill.get("actions", []))
    if not actions or len(actions) > max_actions:
        raise ValueError("Skill пуст или превышает лимит действий")
    for action in actions:
        action_type = str(action.get("type", "command"))
        if action_type == "delay":
            seconds = min(max(float(action.get("seconds", 0)), 0), 10)
            time.sleep(seconds)
            replies.append(f"Пауза {seconds:g} сек.")
            continue
        if action_type != "command":
            raise ValueError(f"Неизвестное действие Skill: {action_type}")
        result = handle_intent(str(action.get("value", "")))
        if result is None or "open_unknown" in result.tools:
            raise ValueError(f"Skill не смог выполнить: {action.get('value', '')}")
        replies.append(result.reply)
        tools.extend(result.tools)
    audit("skill_executed", str(skill.get("name", "")), category="SKILL")
    return ActionResult(reply="\n".join(replies), tools=list(dict.fromkeys(tools)))
