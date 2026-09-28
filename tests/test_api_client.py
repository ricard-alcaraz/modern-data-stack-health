import pytest
import responses
from ingestion.utils.api_client import GitHubAPIClient

@pytest.fixture
def client():
    return GitHubAPIClient(token="fake_token")

@responses.activate
def test_pagination_handles_next_link(client):
    # Mock first page with Link header
    responses.add(
        responses.GET,
        "https://api.github.com/repos/test/repo/issues?per_page=100",
        json=[{"id": 1}, {"id": 2}],
        headers={"Link": '<https://api.github.com/repos/test/repo/issues?per_page=100&page=2>; rel="next"'},
        status=200
    )
    # Mock second page without Link header
    responses.add(
        responses.GET,
        "https://api.github.com/repos/test/repo/issues?per_page=100&page=2",
        json=[{"id": 3}],
        status=200
    )
    
    results = list(client.paginate("/repos/test/repo/issues"))
    assert len(results) == 3
    assert [r["id"] for r in results] == [1, 2, 3]

@responses.activate
def test_rate_limit_retries_on_429(client):
    # Mock a 429 response with Retry-After
    responses.add(
        responses.GET,
        "https://api.github.com/repos/test/repo/issues?per_page=100",
        status=429,
        headers={"Retry-After": "1"}
    )
    # Mock the subsequent successful retry request
    responses.add(
        responses.GET,
        "https://api.github.com/repos/test/repo/issues?per_page=100",
        json=[{"id": 1}],
        status=200
    )
    
    results = list(client.paginate("/repos/test/repo/issues"))
    assert len(results) == 1
    assert len(responses.calls) == 2 # Called twice (failed, then retried)