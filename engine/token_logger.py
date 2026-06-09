"""
Centralised token usage logger.

Appends one row per LLM API call to a daily Parquet file on Azure Blob Storage,
partitioned by project:  token-logs/{project_id}/{YYYY-MM-DD}.parquet

Any app imports TokenLogger, passes a project_id, and calls .log() after every
Anthropic SDK call.  The .query_df() method returns the full history via DuckDB.
"""

import io
import os
import warnings
from datetime import date, datetime

import pandas as pd

_CONTAINER = "token-logs"

_MODEL_PRICING = {
    "claude-sonnet-4-6":         {"in": 3.00,  "out": 15.0},
    "claude-haiku-4-5-20251001": {"in": 0.80,  "out":  4.0},
    "claude-opus-4-8":           {"in": 15.00, "out": 75.0},
    "claude-haiku-4-5":          {"in": 0.80,  "out":  4.0},
}

COLUMNS = [
    "project_id", "session_id", "date", "time",
    "page", "model", "in_tokens", "out_tokens", "api_calls", "cost_usd",
]


class TokenLogger:
    def __init__(self, project_id: str, connection_string: str | None = None):
        self.project_id = project_id
        conn_str = connection_string or os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
        if not conn_str:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING not set")
        self._conn_str = conn_str
        self._svc = None  # lazy — avoids import cost at module load

    # ── internals ──────────────────────────────────────────────────────────────

    def _service(self):
        if self._svc is None:
            from azure.storage.blob import BlobServiceClient
            self._svc = BlobServiceClient.from_connection_string(self._conn_str)
        return self._svc

    def _blob_path(self) -> str:
        return f"{self.project_id}/{date.today().isoformat()}.parquet"

    # ── public API ─────────────────────────────────────────────────────────────

    def log(self, session_id: str, page: str, model: str, usage: dict) -> dict | None:
        """
        Append one usage row to today's Parquet on Azure.
        Returns the row dict so callers can cache it in session state.
        Never raises — logs a warning and returns None if Azure is unreachable.
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
            "date":       now.strftime("%Y-%m-%d"),
            "time":       now.strftime("%H:%M:%S"),
            "page":       page,
            "model":      model,
            "in_tokens":  in_tok,
            "out_tokens": out_tok,
            "api_calls":  usage.get("api_calls", 1),
            "cost_usd":   round(cost, 6),
        }

        try:
            blob_path   = self._blob_path()
            blob_client = self._service().get_blob_client(_CONTAINER, blob_path)

            try:
                raw         = blob_client.download_blob().readall()
                existing_df = pd.read_parquet(io.BytesIO(raw))
                df          = pd.concat([existing_df, pd.DataFrame([row])], ignore_index=True)
            except Exception:
                df = pd.DataFrame([row])

            buf = io.BytesIO()
            df.to_parquet(buf, index=False)
            buf.seek(0)
            blob_client.upload_blob(buf, overwrite=True)

        except Exception as exc:
            warnings.warn(f"TokenLogger: Azure write failed — {exc}")
            return None

        return row

    def query_df(self) -> pd.DataFrame:
        """
        Return all usage rows for this project as a DataFrame.
        Uses DuckDB to read directly from Azure Blob Storage via wildcard.
        Returns an empty DataFrame (correct columns) if no data exists yet.
        """
        try:
            import duckdb
            db = duckdb.connect()
            db.execute("INSTALL azure; LOAD azure;")
            db.execute(f"SET azure_storage_connection_string='{self._conn_str}';")
            df = db.sql(
                f"SELECT * FROM 'azure://{_CONTAINER}/{self.project_id}/*.parquet'"
                f" ORDER BY date, time"
            ).df()
            return df
        except Exception:
            return pd.DataFrame(columns=COLUMNS)
