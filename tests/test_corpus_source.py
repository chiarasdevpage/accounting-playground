"""Reading the list of standards off the PCAOB index page."""

from __future__ import annotations

from apg.corpus.source import INDEX_URL, parse_index


def test_the_whole_series_is_found(index_html):
    refs = parse_index(index_html)
    assert len(refs) == 51


def test_results_are_in_as_number_order(index_html):
    refs = parse_index(index_html)
    assert [r.as_number for r in refs] == sorted(r.as_number for r in refs)
    assert refs[0].as_number == "AS 1000"
    assert refs[-1].as_number == "AS 6115"


def test_both_url_slug_styles_are_handled(index_html):
    """The site uses tidy ids for most standards and long slugs for others.

    This is the reason the list is scraped rather than generated from the AS
    numbers: there is no rule that predicts which style a standard uses.
    """
    by_number = {r.as_number: r for r in parse_index(index_html)}
    assert by_number["AS 1101"].url.endswith("/AS1101")
    assert by_number["AS 2101"].url.endswith("/as-2101-audit-planning-2022")


def test_urls_are_absolute(index_html):
    assert all(r.url.startswith("https://") for r in parse_index(index_html))


def test_titles_have_the_as_number_stripped_off(index_html):
    by_number = {r.as_number: r for r in parse_index(index_html)}
    assert by_number["AS 2301"].title == (
        "The Auditor's Responses to the Risks of Material Misstatement"
    )


def test_series_are_assigned(index_html):
    refs = parse_index(index_html)
    series = {r.series for r in refs}
    assert "General Auditing Standards" in series
    assert "Other Audit-Related Matters" in series


def test_the_same_standard_linked_twice_is_counted_once():
    """The real page links some standards from both the list and the nav rail."""
    link = '<a href="/oversight/standards/auditing-standards/details/AS2301">'
    html = (
        f"<ul><li>{link}AS 2301: A Title</a></li>"
        f"<li>{link}AS 2301: A Title</a></li></ul>"
    )
    assert len(parse_index(html, base_url=INDEX_URL)) == 1


def test_links_that_are_not_standards_are_ignored():
    base = "/oversight/standards/auditing-standards/details"
    html = (
        "<ul>"
        '<li><a href="/careers">Careers</a></li>'
        f'<li><a href="{base}/AS2301">AS 2301: A Title</a></li>'
        f'<li><a href="{base}/interpretations">Interpretations</a></li>'
        "</ul>"
    )
    refs = parse_index(html)
    assert [r.as_number for r in refs] == ["AS 2301"]


def test_a_page_with_no_standards_yields_nothing():
    assert parse_index("<html><body>nothing here</body></html>") == []
