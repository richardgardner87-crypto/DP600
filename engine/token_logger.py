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
        self._conn_str_override = connection_string  # explicit override; env is read lazily
        self._svc = None  # lazy — avoids import cost at module load

    def _conn_str(self) -> str:
        """Read connection string lazily so Streamlit Cloud secrets are available."""
        conn = self._conn_str_override or os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
        if not conn:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING not set")
        return conn

    # ── internals ──────────────────────────────────────────────────────────────

    def _service(self):
        if self._svc is None:
            from azure.storage.blob import BlobServiceClient
            self._svc = BlobServiceClient.from_connection_string(self._conn_str())
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

    def connection_status(self) -> tuple[bool, str]:
        """Return (ok, message) — used by the UI to surface Azure errors."""
        try:
            conn = self._conn_str()
            container_client = self._service().get_container_client(_CONTAINER)
            list(container_client.list_blobs(name_starts_with=f"{self.project_id}/", max_results=1))
            return True, "Connected"
        except Exception as exc:
            return False, str(exc)

    def query_df(self) -> pd.DataFrame:
        """
        Return all usage rows for this project as a DataFrame.
        Tries DuckDB first (more efficient); falls back to downloading each
        daily blob directly via azure-storage-blob if DuckDB's Azure extension
        is unavailable (e.g. Streamlit Cloud sandbox).
        """
        # ── Primary: DuckDB wildcard query ────────────────────────────────────
        try:
            import duckdb
            db = duckdb.connect()
            db.execute("INSTALL azure; LOAD azure;")
            db.execute(f"SET azure_storage_connection_string='{self._conn_str()}';")
            return db.sql(
                f"SELECT * FROM 'azure://{_CONTAINER}/{self.project_id}/*.parquet'"
                f" ORDER BY date, time"
            ).df()
        except Exception:
            pass

        # ── Fallback: download blobs one by one ───────────────────────────────
        try:
            container_client = self._service().get_container_client(_CONTAINER)
            prefix = f"{self.project_id}/"
            frames = []
            for blob in container_client.list_blobs(name_starts_with=prefix):
                if blob.name.endswith(".parquet"):
                    raw = container_client.get_blob_client(blob.name).download_blob().readall()
                    frames.append(pd.read_parquet(io.BytesIO(raw)))
            if frames:
                return pd.concat(frames, ignore_index=True).sort_values(["date", "time"], ignore_index=True)
        except Exception:
            pass

        return pd.DataFrame(columns=COLUMNS)
