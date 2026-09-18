"""Keyword matching: does a posting fit the saved criteria?"""

import re
from typing import Protocol, Sequence

from jobwatch.db.models import Keyword


class PostingLike(Protocol):
    title: str
    location: str | None


def term_hits(keyword: Keyword, text: str) -> bool:
    """Case-insensitive match of one term against one lowercased text.

    Default is substring (recall over precision). A whole_word keyword only
    matches at word boundaries, so "intern" stops hitting "Internal" — and
    also "Internship", which is why it is opt-in per term.
    """
    term = keyword.term.lower()
    if keyword.whole_word:
        # Lookarounds instead of \b: \b breaks on terms that start or end
        # with a non-word character ("c++" would never match, because \b
        # after "+" requires an adjacent word character).
        return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None
    return term in text


def posting_matches(posting: PostingLike, keywords: Sequence[Keyword]) -> bool:
    """True when the posting satisfies every keyword field that has terms.

    Terms within one field are OR'd, fields are AND'd: with title terms
    ("intern", "software engineer") and location term ("amsterdam"), a posting
    must hit at least one title term AND the location. A field with no saved
    terms is unconstrained.
    """
    title_keywords = [k for k in keywords if k.field == "title"]
    location_keywords = [k for k in keywords if k.field == "location"]

    title = posting.title.lower()
    location = (posting.location or "").lower()

    title_ok = not title_keywords or any(term_hits(k, title) for k in title_keywords)
    location_ok = not location_keywords or any(term_hits(k, location) for k in location_keywords)
    return title_ok and location_ok
