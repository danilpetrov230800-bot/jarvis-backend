from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from nova.constants import AGENT_RETRY_LIMIT, AGENT_TIMEOUT_SEC, MAX_AGENT_STEPS
from nova.logging_service import LogService

ToolFn = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class AgentStep:
    title: str
    status: str
    detail: str = ""
    tool: str | None = None


@dataclass
class AgentRun:
    goal: str
    status: str = "planning"
    steps: list[AgentStep] = field(default_factory=list)
    result: str = ""
    error: str = ""


class AgentRuntime:
    def __init__(self, log: LogService, tool_runner: ToolFn) -> None:
        self.log = log
        self.tool_runner = tool_runner
        self.max_steps = MAX_AGENT_STEPS
        self.timeout = AGENT_TIMEOUT_SEC
        self.retry_limit = AGENT_RETRY_LIMIT

    async def run(self, goal: str, plan: list[dict[str, Any]] | None = None) -> AgentRun:
        run = AgentRun(goal=goal)
        started = time.monotonic()
        steps = plan or self.plan(goal)
        run.steps = [AgentStep(title=s.get("title") or s.get("tool") or "Шаг", status="pending", tool=s.get("tool")) for s in steps]
        self.log.agent("agent started", goal=goal[:120], steps=len(steps))
        results: list[str] = []
        try:
            for index, spec in enumerate(steps[: self.max_steps]):
                if time.monotonic() - started > self.timeout:
                    run.status = "timeout"
                    run.error = "Задача остановлена по таймеру."
                    run.steps.append(AgentStep(title="Таймаут", status="failed", detail=run.error))
                    self.log.agent("agent timeout")
                    return run
                run.steps[index].status = "running"
                run.status = "running"
                title = spec.get("title") or spec.get("tool") or f"Шаг {index + 1}"
                attempt = 0
                last_error = ""
                while attempt <= self.retry_limit:
                    try:
                        if spec.get("tool"):
                            result = await asyncio.wait_for(
                                self.tool_runner(spec["tool"], spec.get("args") or {}),
                                timeout=min(30, self.timeout),
                            )
                            detail = str(result.get("reply") or result.get("result") or result)
                            run.steps[index].status = "done" if result.get("ok", True) else "failed"
                            run.steps[index].detail = detail[:2000]
                            results.append(f"{title}: {detail}")
                            if not result.get("ok", True):
                                last_error = detail
                                attempt += 1
                                continue
                            break
                        run.steps[index].status = "done"
                        run.steps[index].detail = spec.get("detail") or "Готово"
                        results.append(f"{title}: {run.steps[index].detail}")
                        break
                    except Exception as exc:
                        last_error = str(exc)
                        attempt += 1
                        await asyncio.sleep(0.2)
                else:
                    run.steps[index].status = "failed"
                    run.steps[index].detail = last_error or "Не удалось выполнить шаг."
            run.status = "completed"
            run.result = self._summarize(goal, results, run.steps)
            run.steps.append(AgentStep(title="Проверка результата", status="done", detail="Шаги выполнены."))
        except Exception as exc:
            run.status = "failed"
            run.error = "Я не смог выполнить задачу."
            run.steps.append(AgentStep(title="Ошибка", status="failed", detail=str(exc)))
            self.log.agent("agent failed", error=str(exc))
        return run

    def plan(self, goal: str) -> list[dict[str, Any]]:
        text = goal.lower()
        steps: list[dict[str, Any]] = [{"title": "Планирую задачу"}]
        if any(word in text for word in ("файл", "pdf", "фото", "папк", "дубликат", "архив")):
            steps.append({"title": "Ищу файлы", "tool": "find_files", "args": {"query": goal}})
        if any(word in text for word in ("погод", "пробк", "новост", "найди информацию", "сравни")):
            steps.append({"title": "Ищу информацию", "tool": "web_search", "args": {"query": goal}})
        if any(word in text for word in ("компьютер", "тормоз", "процессор", "память", "диск")):
            steps.append({"title": "Смотрю систему", "tool": "system_info", "args": {}})
            steps.append({"title": "Смотрю процессы", "tool": "list_processes", "args": {}})
        if any(word in text for word in ("открой", "запусти")):
            steps.append({"title": "Запускаю программу", "tool": "open_app", "args": {"name": goal}})
        if len(steps) == 1:
            steps.append({"title": "Выполняю действие", "tool": "local_answer", "args": {"text": goal}})
        steps.append({"title": "Готовлю результат"})
        return steps

    def visualize(self, run: AgentRun) -> list[dict[str, str]]:
        mapping = {
            "planning": "Планирую задачу",
            "pending": "В очереди",
            "running": "Выполняю действие",
            "done": "Готово",
            "failed": "Нужна проверка",
            "timeout": "Остановлено по времени",
        }
        return [
            {
                "title": step.title,
                "status": mapping.get(step.status, step.status),
                "detail": step.detail[:400],
            }
            for step in run.steps
        ]

    def _summarize(self, goal: str, results: list[str], steps: list[AgentStep]) -> str:
        failed = [s for s in steps if s.status == "failed"]
        body = "\n".join(results[-6:]) or "Задача обработана."
        if failed:
            return f"Часть шагов не удалась.\n{body}"
        return f"Готово по задаче «{goal[:80]}».\n{body}"
