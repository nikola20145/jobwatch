"""Keyword matching: does a posting fit the saved criteria?"""

from typing import Protocol, Sequence

from jobwatch.db.models import Keyword


class PostingLike(Protocol):
    title: str
    location: str | None


def posting_matches(posting: PostingLike, keywords: Sequence[Keyword]) -> bool:
    """True when the posting satisfies every keyword field that has terms.

    Terms within one field are OR'd, fields are AND'd: with title terms
    ("intern", "software engineer") and location term ("amsterdam"), a posting
    must hit at least one title term AND the location. A field with no saved
    terms is unconstrained. Matching is case-insensitive substring.
    """
    title_terms = [k.term.lower() for k in keywords if k.field == "title"]
    location_terms = [k.term.lower() for k in keywords if k.field == "location"]

    title = posting.title.lower()
    location = (posting.location or "").lower()

    title_ok = not title_terms or any(term in title for term in title_terms)
    location_ok = not location_terms or any(term in location for term in location_terms)
    return title_ok and location_ok
