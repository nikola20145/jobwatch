"""Alert channel interface."""

from typing import Protocol, Sequence, runtime_checkable

from jobwatch.db.models import Posting


@runtime_checkable
class Alerter(Protocol):
    channel: str

    def send(self, posting: Posting) -> None:
        """Deliver one alert. Raise on failure; the pipeline then leaves the
        posting unrecorded so it is retried next run."""
        ...

    def send_digest(self, postings: Sequence[Posting]) -> None:
        """Deliver one combined message covering several postings. Raise on
        failure; the pipeline then records none of them."""
        ...
