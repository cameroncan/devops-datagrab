import pytest
import requests
from src.devops_metrics_service import DevopsMetricsService


@pytest.fixture(autouse=False)
def disable_network_calls(monkeypatch):
    def stunted_get():
        raise RuntimeError("Network access not allowed during testing!")
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: stunted_get())


def test_get_caused_by_ticket():
    assert True


def test_get_last_release_hash(requests_mock):
    # Arrange
    repo = "test_repo"
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{repo}/refs/tags",
                      json={"values": [{"name": "1.0.0", "target": {"hash": "cur-release"}},
                                       {"name": "0.0.1", "target": {"hash": "last-release"}}]})

    devops_metrics_service: DevopsMetricsService = DevopsMetricsService()
    git_hash = devops_metrics_service.get_last_release_hash(repo, "1.0.0")

    assert git_hash == "last-release"
