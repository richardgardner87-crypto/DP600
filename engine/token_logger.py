"""
Centralised token usage logger — PostgreSQL backend.

Writes one row per LLM API call to the token_usage table, keyed by
project_id for multi-app reuse.  query_df() returns the full history
for a project as a DataFrame.
"""

import warnings
from datetime import datetime

import pandas as pd

from engine.db import execute, query_df as db_query_df

_MODEL_PRICING = {
    "claude-sonnet-4-6":         {"in": 3.00,  "out": 15.0},
    "claude-haiku-4-5-20251001": {"in": 0.80,  "out":  4.0},
    "claude-opus-4-8":           {"in": 15.00, "out": 75.0},
    "claude-haiku-4-5":          {"in": 0.80,  "out":  4.0},
}

COLUMNS = [
    "project_id", "session_id", "logged_date", "logged_time",
    "page", "model", "in_tokens", "out_tokens", "api_calls", "cost_usd",
]


class TokenLogger:
    def __init__(self, project_id: str, **_kwargs):
        self.project_id = project_id

    def log(self, session_id: str, page: str, model: str, usage: dict) -> dict | None:
        """
        Insert one usage row into token_usage.
        Returns the row dict so callers can cache it in session state.
        Never raises — warns and returns None on failure.
        """
        if not usage:
            return None

        pricing = _MODEL_PRICING.get(model, {"in": 3.0, "out": 15.0})
        in_tok  = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        cost    = (in_tok * pricing["in"] + out_tok * pricing["out"]) / 1_000_000

        now = datetime.now()
        row = {
            "project_id": self.project_id,
            "session_id": session_id,
            "logged_date": now.strftime("%Y-%m-%d"),
            "logged_time": now.strftime("%H:%M:%S"),
            "page":        page,
            "model":       model,
            "in_tokens":   in_tok,
            "out_tokens":  out_tok,
            "api_calls":   usage.get("api_calls", 1),
            "cost_usd":    round(cost, 6),
        }

        try:
            execute(
                """INSERT INTO token_usage
                   (project_id, session_id, logged_date, logged_time, page, model,
                    in_tokens, out_tokens, api_calls, cost_usd)
                   VALUES (%(project_id)s, %(session_id)s, %(logged_date)s, %(logged_time)s,
                           %(page)s, %(model)s, %(in_tokens)s, %(out_tokens)s,
                           %(api_calls)s, %(cost_usd)s)""",
                row,
            )
        except Exception as exc:
            warnings.warn(f"TokenLogger: DB write failed — {exc}")
            return None

        return row

    def query_df(self) -> pd.DataFrame:
        """Return all usage rows for this project as a DataFrame."""
        try:
            return db_query_df(
                "SELECT * FROM token_usage WHERE project_id = %s ORDER BY logged_date, logged_time",
                (self.project_id,),
            )
        except Exception:
            return pd.DataFrame(columns=COLUMNS)
