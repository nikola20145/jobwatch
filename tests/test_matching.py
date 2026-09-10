from jobwatch.db.models import Keyword
from jobwatch.matching import posting_matches

from .conftest import make_scraped


def kw(field: str, term: str) -> Keyword:
    return Keyword(field=field, term=term)


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
