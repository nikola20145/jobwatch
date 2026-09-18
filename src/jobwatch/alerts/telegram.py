"""Telegram alert channel via the Bot API."""

import html
from typing import Sequence

import httpx

from jobwatch.db.models import Posting

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def format_posting(posting: Posting) -> str:
    source_name = posting.source.name if posting.source else "unknown source"
    lines = [f"<b>{html.escape(posting.title)}</b>"]
    detail = html.escape(source_name)
    if posting.location:
        detail += f" — {html.escape(posting.location)}"
    lines.append(detail)
    if posting.posted_at:
        lines.append(f"Posted: {posting.posted_at:%Y-%m-%d}")
    lines.append(posting.url)
    return "\n".join(lines)


def format_digest(postings: Sequence[Posting]) -> str:
    count = len(postings)
    plural = "" if count == 1 else "s"
    lines = [f"<b>{count} new matching posting{plural}</b>"]
    for posting in postings:
        source_name = posting.source.name if posting.source else "?"
        entry = (
            f'• <a href="{html.escape(posting.url, quote=True)}">'
            f"{html.escape(posting.title)}</a> — {html.escape(source_name)}"
        )
        if posting.location:
            entry += f", {html.escape(posting.location)}"
        lines.append(entry)
    return "\n".join(lines)


class TelegramAlerter:
    channel = "telegram"

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._url = API_URL.format(token=bot_token)
        self._chat_id = chat_id
        self._client = client or httpx.Client(timeout=timeout)

    def send(self, posting: Posting) -> None:
        self._send_text(format_posting(posting))

    def send_digest(self, postings: Sequence[Posting]) -> None:
        self._send_text(format_digest(postings))

    def _send_text(self, text: str) -> None:
        response = self._client.post(
            self._url,
            json={
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()
        body = response.json()
        if not body.get("ok"):
            raise RuntimeError(f"Telegram API rejected message: {body}")
