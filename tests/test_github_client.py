import pytest
from pr_reviewer.github_client import parse_pr_identifier
from pr_reviewer.models import ReviewVerdict


def test_parse_pr_identifier_url():
    repo, pr_num = parse_pr_identifier("https://github.com/torvalds/linux/pull/42")
    assert repo == "torvalds/linux"
    assert pr_num == 42


def test_parse_pr_identifier_url_with_trailing():
    repo, pr_num = parse_pr_identifier("https://github.com/pallets/flask/pull/99/files")
    assert repo == "pallets/flask"
    assert pr_num == 99


def test_parse_pr_identifier_hash():
    repo, pr_num = parse_pr_identifier("psf/requests#1234")
    assert repo == "psf/requests"
    assert pr_num == 1234


def test_parse_pr_identifier_slash():
    repo, pr_num = parse_pr_identifier("django/django/567")
    assert repo == "django/django"
    assert pr_num == 567


def test_parse_pr_identifier_space():
    repo, pr_num = parse_pr_identifier("encode/httpx 88")
    assert repo == "encode/httpx"
    assert pr_num == 88


def test_parse_pr_identifier_invalid():
    with pytest.raises(ValueError):
        parse_pr_identifier("random_string_without_repo")


def test_review_verdict_to_github_event():
    assert ReviewVerdict.APPROVED.to_github_event() == "APPROVE"
    assert ReviewVerdict.REQUEST_CHANGES.to_github_event() == "REQUEST_CHANGES"
    assert ReviewVerdict.COMMENT.to_github_event() == "COMMENT"
