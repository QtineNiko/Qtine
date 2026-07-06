# -*- coding: utf-8 -*-
"""Simple cron-style task scheduler for Qtine."""

import time
import threading
from typing import Callable, Dict, List, Optional
from qtine.utils.logger import get_logger


def parse_cron(expr: str) -> List[int]:
    """Parse a 5-field cron expression into list of [min, hour, day, month, weekday] as allowed sets.

    Returns list of 5 sets: [minutes, hours, days, months, weekdays]
    Supports: *, */n, a-b, a,b,c, a-b/n
    """
    fields = expr.strip().split()
    if len(fields) != 5:
        raise ValueError(f"Invalid cron expression (need 5 fields): {expr}")

    ranges = [
        (0, 59),   # minute
        (0, 23),   # hour
        (1, 31),   # day of month
        (1, 12),   # month
        (0, 6),    # day of week (0=Mon or 0=Sun? we use 0=Monday)
    ]

    result = []
    for i, (field, (min_val, max_val)) in enumerate(zip(fields, ranges)):
        allowed = set()
        for part in field.split(","):
            part = part.strip()
            if part == "*":
                allowed.update(range(min_val, max_val + 1))
            elif part.startswith("*/"):
                step = int(part[2:])
                if step <= 0:
                    raise ValueError(f"Invalid step in cron: {part}")
                allowed.update(range(min_val, max_val + 1, step))
            elif "-" in part and "/" in part:
                rng, step = part.split("/")
                a, b = rng.split("-")
                a, b, step = int(a), int(b), int(step)
                allowed.update(range(a, b + 1, step))
            elif "-" in part:
                a, b = part.split("-")
                a, b = int(a), int(b)
                if a < min_val: a = min_val
                if b > max_val: b = max_val
                allowed.update(range(a, b + 1))
            else:
                v = int(part)
                if min_val <= v <= max_val:
                    allowed.add(v)
        if not allowed:
            raise ValueError(f"No valid values for cron field {i}: {field}")
        result.append(allowed)

    return result


def matches_cron(parsed: List[set], t: Optional[time.struct_time] = None) -> bool:
    """Check if current time matches a parsed cron expression."""
    if t is None:
        t = time.localtime()
    return (
        t.tm_min in parsed[0]
        and t.tm_hour in parsed[1]
        and t.tm_mday in parsed[2]
        and t.tm_mon in parsed[3]
        and (t.tm_wday in parsed[4])
    )


class ScheduledTask:
    def __init__(self, name: str, cron_expr: str, callback: Callable,
                 plugin: str = "", description: str = ""):
        self.name = name
        self.cron_expr = cron_expr
        self.callback = callback
        self.plugin = plugin
        self.description = description
        self.parsed = parse_cron(cron_expr)
        self.last_run_minute: Optional[int] = None
        self.run_count = 0
        self.last_run_time: Optional[float] = None

    def should_run(self, t: time.struct_time) -> bool:
        minute_key = t.tm_hour * 60 + t.tm_min
        if minute_key == self.last_run_minute:
            return False
        if matches_cron(self.parsed, t):
            self.last_run_minute = minute_key
            return True
        return False

    def run(self):
        try:
            self.callback()
            self.run_count += 1
            self.last_run_time = time.time()
        except Exception as e:
            get_logger().error(f"Scheduled task '{self.name}' error: {e}")


class TaskScheduler:
    _instance: "TaskScheduler" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._tasks: Dict[str, ScheduledTask] = {}
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.logger = get_logger()
        self._bot = None

    def set_bot(self, bot):
        self._bot = bot

    def add_task(self, name: str, cron_expr: str, callback: Callable,
                 plugin: str = "", description: str = "") -> bool:
        """Register a scheduled task. Returns True if added."""
        try:
            task = ScheduledTask(name, cron_expr, callback, plugin, description)
        except ValueError as e:
            self.logger.error(f"Failed to add task '{name}': {e}")
            return False
        with self._lock:
            self._tasks[name] = task
        self.logger.info(f"Scheduled task added: {name} ({cron_expr})")
        return True

    def remove_task(self, name: str) -> bool:
        with self._lock:
            return self._tasks.pop(name, None) is not None

    def list_tasks(self, plugin: Optional[str] = None) -> List[dict]:
        with self._lock:
            tasks = list(self._tasks.values())
        if plugin:
            tasks = [t for t in tasks if t.plugin == plugin]
        return [
            {
                "name": t.name,
                "cron": t.cron_expr,
                "plugin": t.plugin,
                "description": t.description,
                "run_count": t.run_count,
                "last_run": t.last_run_time,
            }
            for t in tasks
        ]

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="qtine-scheduler")
        self._thread.start()
        self.logger.info("Task scheduler started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        self.logger.info("Task scheduler stopped")

    def _loop(self):
        while self._running:
            now = time.localtime()
            # Run at the start of each second; only fire when second == 0
            if now.tm_sec == 0:
                with self._lock:
                    tasks = list(self._tasks.values())
                for task in tasks:
                    if task.should_run(now):
                        self.logger.debug(f"Running scheduled task: {task.name}")
                        threading.Thread(
                            target=task.run,
                            daemon=True,
                            name=f"task-{task.name}"
                        ).start()
            # Sleep ~0.5s to catch the next second
            time.sleep(0.5)
