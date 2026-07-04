# -*- coding: utf-8 -*-
"""Message processing pipeline for Qtine.

Pipeline stages:
  1. PRE    – preprocessing (auth, blacklist, rate-limit, etc.)
  2. HANDLER – command / regex / keyword matching
  3. POST   – postprocessing (repeat detection, logging, etc.)

Each middleware receives (ctx, next_fn).
Calling next_fn(ctx) passes control to the next middleware in the same stage.
Returning a string sets the response and short-circuits the pipeline.
"""

from typing import Callable, List, Optional

from qtine.utils.models import Message
from qtine.utils.logger import get_logger


class PipelineContext:
    def __init__(self, message: Message):
        self.message = message
        self._data: dict = {}
        self._aborted: bool = False
        self._response: Optional[str] = None

    @property
    def aborted(self) -> bool:
        return self._aborted

    def abort(self, reason: str = ""):
        self._aborted = True
        self._data["abort_reason"] = reason

    def reply(self, text: str):
        self._response = text

    @property
    def response(self) -> Optional[str]:
        return self._response

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value


# A middleware receives (ctx, next_fn) and returns Optional[str]
Middleware = Callable[["PipelineContext", Callable], Optional[str]]


class MessagePipeline:
    def __init__(self):
        self.logger = get_logger()
        self._pre: List[Middleware] = []
        self._handlers: List[Middleware] = []
        self._post: List[Middleware] = []

    def pre(self, mw: Middleware) -> Middleware:
        self._pre.append(mw)
        return mw

    def handler(self, mw: Middleware) -> Middleware:
        self._handlers.append(mw)
        return mw

    def post(self, mw: Middleware) -> Middleware:
        self._post.append(mw)
        return mw

    def process(self, message: Message) -> Optional[str]:
        ctx = PipelineContext(message)

        # ── PRE stage ────────────────────────────────────────────────
        if not self._run_stage(self._pre, ctx):
            return ctx.response

        # ── HANDLER stage ────────────────────────────────────────────
        self._run_stage(self._handlers, ctx)
        if ctx.aborted:
            return ctx.response

        # ── POST stage ───────────────────────────────────────────────
        self._run_stage(self._post, ctx)

        return ctx.response

    def _run_stage(
        self, middlewares: List[Middleware], ctx: PipelineContext
    ) -> bool:
        """Run a list of middlewares in sequence with proper next_fn chaining.

        Returns False if the pipeline should stop (aborted or short-circuited).
        """
        if not middlewares:
            return True

        # Build a chain: each middleware calls next_fn to invoke the next one.
        # We do it iteratively using an index.
        idx = 0
        length = len(middlewares)

        def make_next(index: int):
            """Return a next_fn that, when called, runs middleware at `index`."""

            def next_step(c: PipelineContext) -> Optional[str]:
                nonlocal index
                if index >= length or c.aborted:
                    return None
                mw = middlewares[index]
                index += 1
                try:
                    result = mw(c, make_next(index))
                except Exception as e:
                    self.logger.error(f"Middleware error: {e}")
                    return None
                return result

            return next_step

        try:
            make_next(idx)(ctx)
        except Exception as e:
            self.logger.error(f"Pipeline stage error: {e}")

        return not ctx.aborted
