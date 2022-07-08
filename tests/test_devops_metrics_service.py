import pytest
import pytz
from datetime import datetime
from dateutil import parser
from devops_metrics_service import DevopsMetricsService
from devops_metrics_info import DevopsMetricsInfo, DeploymentInfo, DeployedTicket
from freezegun import freeze_time

devops_metrics_service: DevopsMetricsService = DevopsMetricsService()


@freeze_time("2020, 3, 27")
def test_get_devops_metrics_information(mocker, requests_mock):
    # Arrange
    data_dict: dict = _setup_mocks_all_base_mocks_for_get_devops_metrics_information(mocker, requests_mock)
    expected_result = data_dict["expected_result"]

    # Act
    metrics_info = devops_metrics_service.get_devops_metrics_information(data_dict["repo"], data_dict["version"],
                                                                         data_dict["deploy_datetime"],
                                                                         data_dict["deployed_by"])

    # Assert
    assert metrics_info.to_pretty_str() == expected_result.to_pretty_str()


@freeze_time("2020, 3, 27")
def test_get_devops_metrics_information__then_deployment_and_ticket_share_same_deployment_id(mocker, requests_mock):
    # Arrange
    data_dict: dict = _setup_mocks_all_base_mocks_for_get_devops_metrics_information(mocker, requests_mock)
    expected_result = data_dict["expected_result"]

    # Act
    metrics_info: DevopsMetricsInfo = devops_metrics_service.get_devops_metrics_information(data_dict["repo"], data_dict["version"],
                                                                                            data_dict["deploy_datetime"],
                                                                                            data_dict["deployed_by"])

    # Assert
    assert metrics_info.deployment_info.id == metrics_info.deployed_tickets[0].deployment_id


@freeze_time("2020, 3, 27")
def test_get_devops_metrics_information__when_ticket_not_in_release__then_ignore(mocker, requests_mock):
    # Arrange
    data_dict: dict = _setup_mocks_all_base_mocks_for_get_devops_metrics_information(mocker, requests_mock)
    mocker.patch("devops_metrics_service.DevopsMetricsService.get_released_tickets", return_value=[
        {"ticket_id": "different_ticket_id", "type": "Story", "created_datetime": data_dict["ticket_created_datetime"], "caused_by": ""}
    ])
    expected_result = data_dict["expected_result"]
    expected_result.deployed_tickets = []

    # Act
    metrics_info: DevopsMetricsInfo = devops_metrics_service.get_devops_metrics_information(data_dict["repo"], data_dict["version"],
                                                                                            data_dict["deploy_datetime"],
                                                                                            data_dict["deployed_by"])

    # Assert
    assert metrics_info.to_pretty_str() == expected_result.to_pretty_str()


def test_get_devops_metrics_information__when_bug_is_caused_by_another_ticket__then_record_in_info(mocker, requests_mock):
    # Arrange
    data_dict: dict = _setup_mocks_all_base_mocks_for_get_devops_metrics_information(mocker, requests_mock)
    caused_by_ticket_id = "CV-20"
    mocker.patch("devops_metrics_service.DevopsMetricsService.get_released_tickets", return_value=[
        {"ticket_id": data_dict["ticket_id"], "type": "Story", "created_datetime": data_dict["ticket_created_datetime"], "caused_by": "CV-20"}
    ])
    expected_result = data_dict["expected_result"]
    expected_result.deployed_tickets[0].caused_by = caused_by_ticket_id

    # Act
    metrics_info: DevopsMetricsInfo = devops_metrics_service.get_devops_metrics_information(data_dict["repo"], data_dict["version"],
                                                                                            data_dict["deploy_datetime"],
                                                                                            data_dict["deployed_by"])

    # Assert
    assert metrics_info.to_pretty_str() == expected_result.to_pretty_str()



@freeze_time("2020, 3, 27")
def test_get_devops_metrics_information__when_ticket_is_in_both_app_and_dependency__then_report_both_repos_for_single_ticket(mocker, requests_mock):
    # Arrange
    data_dict: dict = _setup_mocks_all_base_mocks_for_get_devops_metrics_information(mocker, requests_mock)
    dependency_repo_name = "dep_domain"
    app_repo_name = data_dict["repo"]
    commit_response_app: dict = _get_base_commit_response()
    commit_response_dep: dict = _get_base_commit_response()
    mocker.patch("devops_metrics_service.DevopsMetricsService._get_repos_to_check", return_value=[dependency_repo_name])
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{app_repo_name}/commits/master", json=commit_response_app)
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{dependency_repo_name}/commits/master", json=commit_response_dep)
    expected_result: DevopsMetricsInfo = data_dict["expected_result"]
    expected_result.deployed_tickets[0].repositories_affected = [app_repo_name, dependency_repo_name]

    # Act
    metrics_info = devops_metrics_service.get_devops_metrics_information(data_dict["repo"], data_dict["version"],
                                                                         data_dict["deploy_datetime"],
                                                                         data_dict["deployed_by"])

    # Assert
    assert metrics_info.to_pretty_str() == expected_result.to_pretty_str()


@freeze_time("2020, 3, 27")
def test_get_devops_metrics_information__when_ticket_merged_only_in_dependency__then_report_dependency_tickets(mocker, requests_mock):
    # Arrange
    data_dict: dict = _setup_mocks_all_base_mocks_for_get_devops_metrics_information(mocker, requests_mock)
    dependency_repo_name = "dep_domain"
    app_repo_name = data_dict["repo"]
    commit_response: dict = _get_base_commit_response()
    mocker.patch("devops_metrics_service.DevopsMetricsService._get_repos_to_check", return_value=[dependency_repo_name])
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{app_repo_name}/commits/master", json={"values": []})
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{dependency_repo_name}/commits/master", json=commit_response)
    expected_result: DevopsMetricsInfo = data_dict["expected_result"]
    expected_result.deployed_tickets[0].repositories_affected = [dependency_repo_name]

    # Act
    metrics_info = devops_metrics_service.get_devops_metrics_information(data_dict["repo"], data_dict["version"],
                                                                         data_dict["deploy_datetime"],
                                                                         data_dict["deployed_by"])

    # Assert
    assert metrics_info.to_pretty_str() == expected_result.to_pretty_str()


@pytest.mark.skip(reason="Don't know how to mock JIRA sdk objects")
def test_get_released_tickets(mocker):
    repo = "cv-management-web"
    version = "1.0.3"
    mocker.patch("devops_metrics_service.JIRA")
    mocker.patch("devops_metrics_service.JIRA", "search_issues", return_value=[

    ])
    released_tickets = devops_metrics_service.get_released_tickets(repo, version)

    assert len(released_tickets) == 0


def test_extract_ticket_merge_info_from_commits(requests_mock):
    repo = "test_repo"
    author_email = "guido@imging.com"
    commit_ticket = "CV-22"
    commit_message = f"some message ({commit_ticket})"
    commit: dict = _get_base_commit_response(author_email=author_email, commit_message=commit_message)
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{repo}/commits/master", json=commit)
    commit_datetime = parser.parse(commit["values"][0]["date"])

    merge_info_map = devops_metrics_service.extract_ticket_merge_info_from_commits(repo, "previous_release_hash")

    assert merge_info_map[commit_ticket] == {"date": commit_datetime, "author": author_email, "repositories": [repo]}


def test_extract_ticket_merge_info_from_commits__when_message_having_multiple_tickets__then_all_tickets_are_extracted(requests_mock):
    repo = "test_repo"
    author_email = "guido@imging.com"
    commit_tickets = ["CV-2", "CV-22", "IQ-10", "IMGING-11"]
    commit_message = f"{commit_tickets[0]} Some commit message ({commit_tickets[1]}, {commit_tickets[2]}) {commit_tickets[3]}"
    commit: dict = _get_base_commit_response(author_email=author_email, commit_message=commit_message)
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{repo}/commits/master", json=commit)
    commit_datetime = parser.parse(commit["values"][0]["date"])
    expected_info = {"date": commit_datetime, "author": author_email, "repositories": [repo]}
    expected_merge_info_map = {
        commit_tickets[0]: expected_info,
        commit_tickets[1]: expected_info,
        commit_tickets[2]: expected_info,
        commit_tickets[3]: expected_info
    }

    merge_info_map = devops_metrics_service.extract_ticket_merge_info_from_commits(repo, "previous_release_hash")

    assert merge_info_map == expected_merge_info_map


def test__extract_ticket_merge_info_from_commits__when_commit_from_jenkins__then_ignore_commit(requests_mock):
    repo = "test_repo"
    author_email = "jenkins@someipaddress.com"
    commit: dict = _get_base_commit_response(author_email=author_email)
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{repo}/commits/master",
                      json=commit)

    merge_info_map = devops_metrics_service.extract_ticket_merge_info_from_commits(repo, "previous_release_hash")

    assert len(merge_info_map) == 0


def test__extract_ticket_merge_info_from_commits__when_previous_release_hash_reached__then_stop_searching(requests_mock):
    repo = "test_repo"
    commit: dict = _get_base_commit_response()
    commit["values"][0]["hash"] = "previous_release_hash"
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{repo}/commits/master",
                      json=commit)

    merge_info_map = devops_metrics_service.extract_ticket_merge_info_from_commits(repo, commit["values"][0]["hash"])

    assert len(merge_info_map) == 0


@freeze_time("2020, 3, 27")
def test__extract_ticket_merge_info_from_commits__when_timeframe_reached_and_no_previous_release___then_stop_searching(requests_mock):
    repo = "test_repo"
    commit: dict = _get_base_commit_response()
    commit["values"][0]["date"] = "2020-02-26T00:00:00+00:00"
    devops_metrics_service.git_search_timeframe_in_months = 1

    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{repo}/commits/master",
                      json=commit)

    merge_info_map = devops_metrics_service.extract_ticket_merge_info_from_commits(repo, "")

    assert len(merge_info_map) == 0


def test_get_last_release_hash(requests_mock):
    repo = "test_repo"
    tags_response = _get_base_tag_response()
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{repo}/refs/tags",
                     json=tags_response)

    git_hash = devops_metrics_service.get_last_release_hash(repo, "1.0.0")

    assert "last-release" == git_hash


def _get_base_commit_response(author_email: str = "robin@batcave.org",
                              commit_message: str = "Some commit message (CV-22)"):
    return {"values": [{"date": "2020-03-27 00:00:00+00:00",
                        "author": {"raw": f"Robin <{author_email}>"},
                        "name": "1.0.3",
                        "target": {"hash": "cur-release"},
                        "message": commit_message,
                        "hash": "some_other_hash"}]}


def _get_base_tag_response():
    return {"values": [{"name": "1.0.3", "target": {"hash": "cur-release"}},
                       {"name": "1.0.2", "target": {"hash": "most_recent_last-release"}},
                       {"name": "1.0.1", "target": {"hash": "last-release"}}]}


def _get_base_data_for_mocking():
    mock_commit = _get_base_commit_response()
    return {
        "repo": "app_repo",
        "version": "1.0.3",
        "deploy_datetime": datetime(2020, 3, 28, 0, tzinfo=pytz.utc),
        "ticket_created_datetime": datetime(2020, 2, 20, 0, tzinfo=pytz.utc),
        "deployed_by": "batman",
        "ticket_id": "CV-22",
        "author_email": "robin@batcave.org",
        "commit": mock_commit
    }


def _setup_mocks_all_base_mocks_for_get_devops_metrics_information(mocker, requests_mock, data_dict=None):

    if data_dict is None:
        data_dict = _get_base_data_for_mocking()

    # mock the entire function since I don't know how to mock JIRA sdk objects in the test
    mocker.patch("devops_metrics_service.DevopsMetricsService.get_released_tickets", return_value=[
        {"ticket_id": data_dict["ticket_id"], "type": "Story", "created_datetime": data_dict["ticket_created_datetime"], "caused_by": ""}
    ])
    mocker.patch("devops_metrics_service.DevopsMetricsService._get_repos_to_check", return_value=[])
    commit_message: str = "some commit (" + data_dict["ticket_id"] + ")"
    commit_response: dict = _get_base_commit_response(author_email=data_dict["author_email"], commit_message=commit_message)
    tag_response: dict = _get_base_tag_response()
    repo = data_dict["repo"]
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{repo}/commits/master", json=commit_response)
    requests_mock.get(f"https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{repo}/refs/tags",
                      json=tag_response)

    expected_deployment_info = DeploymentInfo(data_dict["repo"], data_dict["version"], data_dict["deploy_datetime"],
                                              data_dict["deployed_by"])
    expected_deployed_tickets = [DeployedTicket(expected_deployment_info.id, repo, data_dict["ticket_id"], "Story", "",
                                                data_dict["ticket_created_datetime"],
                                                commit_response["values"][0]["date"], data_dict["author_email"],
                                                [data_dict["repo"]])]
    data_dict["expected_result"] = DevopsMetricsInfo(expected_deployment_info, expected_deployed_tickets)
    return data_dict
