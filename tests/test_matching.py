from jobwatch.db.models import Keyword
from jobwatch.matching import posting_matches

from .conftest import make_scraped


def kw(field: str, term: str, whole_word: bool = False) -> Keyword:
    return Keyword(field=field, term=term, whole_word=whole_word)


def test_title_and_location_must_both_match():
    keywords = [kw("title", "intern"), kw("location", "amsterdam")]
    assert posting_matches(make_scraped(title="SWE Intern", location="Amsterdam"), keywords)
    assert not posting_matches(make_scraped(title="SWE Intern", location="Berlin"), keywords)
    assert not posting_matches(make_scraped(title="Account Manager", location="Amsterdam"), keywords)


def test_terms_within_a_field_are_ored():
    keywords = [kw("title", "intern"), kw("title", "software engineer")]
    assert posting_matches(make_scraped(title="Software Engineer, Payments", location=None), keywords)
    assert posting_matches(make_scraped(title="Machine Learning Intern", location=None), keywords)
    assert not posting_matches(make_scraped(title="Sales Lead", location=None), keywords)


def test_matching_is_case_insensitive():
    keywords = [kw("title", "intern")]
    assert posting_matches(make_scraped(title="INTERNSHIP - Backend", location=None), keywords)


def test_unconstrained_field_always_passes():
    assert posting_matches(make_scraped(title="Anything", location=None), [kw("location", "amsterdam")]) is False
    assert posting_matches(make_scraped(title="Anything", location="Amsterdam HQ"), [kw("location", "amsterdam")])
    # no location keywords at all -> location unconstrained
    assert posting_matches(make_scraped(title="SWE Intern", location=None), [kw("title", "intern")])


def test_missing_location_fails_location_constraint():
    keywords = [kw("location", "amsterdam")]
    assert not posting_matches(make_scraped(location=None), keywords)


def test_substring_keyword_hits_inside_words():
    # The documented default: recall over precision.
    keywords = [kw("title", "intern")]
    assert posting_matches(make_scraped(title="Internal Developer Platform", location=None), keywords)
    assert posting_matches(make_scraped(title="Internship - Backend", location=None), keywords)


def test_whole_word_keyword_stops_at_boundaries():
    keywords = [kw("title", "intern", whole_word=True)]
    assert posting_matches(make_scraped(title="Software Intern, Payments", location=None), keywords)
    assert posting_matches(make_scraped(title="Intern (Backend)", location=None), keywords)
    assert not posting_matches(make_scraped(title="Internal Developer Platform", location=None), keywords)
    assert not posting_matches(make_scraped(title="Internship - Backend", location=None), keywords)


def test_whole_word_multiword_term():
    keywords = [kw("title", "software engineer", whole_word=True)]
    assert posting_matches(make_scraped(title="Senior Software Engineer (Java)", location=None), keywords)
    assert not posting_matches(make_scraped(title="Software Engineering Manager", location=None), keywords)


def test_whole_word_term_with_regex_chars_is_escaped():
    keywords = [kw("title", "c++", whole_word=True)]
    # Needs lookarounds, not \b: \b after "+" would require an adjacent word
    # character, so "c++" would never match at all.
    assert posting_matches(make_scraped(title="C++ Developer", location=None), keywords)
    assert posting_matches(make_scraped(title="Developer (C++)", location=None), keywords)
    assert not posting_matches(make_scraped(title="C Developer", location=None), keywords)
