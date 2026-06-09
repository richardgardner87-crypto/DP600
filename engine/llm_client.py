"""
TrackedClient — drop-in replacement for anthropic.Anthropic() that logs every
messages.create() call to Azure Blob Storage automatically.

Usage (any engine module or app):
    client = TrackedClient(
        project_id="iherb-gcc",
        session_id=session_id,
        page="Compliance Chat",
        session_log=st.session_state.session_calls,  # optional, for in-session display
    )
    response = client.messages.create(model=..., messages=..., ...)
"""

import os

import anthropic

from engine.token_logger import TokenLogger


class _TrackedMessages:
    """Wraps anthropic.messages, logging usage after every create() call."""

    def __init__(self, raw_client, logger: TokenLogger, session_id: str, page: str, session_log: list | None):
        self._raw         = raw_client
        self._logger      = logger
        self._session_id  = session_id
        self._page        = page
        self._session_log = session_log

    def create(self, **kwargs) -> anthropic.types.Message:
        response = self._raw.messages.create(**kwargs)
        row = self._logger.log(
            session_id=self._session_id,
            page=self._page,
            model=response.model,
            usage={
                "input_tokens":  response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "api_calls":     1,
            },
        )
        if row is not None and self._session_log is not None:
            self._session_log.append(row)
        return response


class TrackedClient:
    """
    Instantiate once per logical action (one chat turn, one classification).
    Set `page` to the page/feature name so the Token Usage dashboard can break
    costs down by feature.
    """

    def __init__(
        self,
        project_id: str,
        session_id: str,
        page: str,
        session_log: list | None = None,
        connection_string: str | None = None,
    ):
        raw = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        logger = TokenLogger(project_id, connection_string)
        self.messages = _TrackedMessages(raw, logger, session_id, page, session_log)
