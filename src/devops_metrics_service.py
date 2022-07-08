import array
import base64
import jira.client
import json
import logging
import os
import re

import pytz
import requests
from datetime import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta
from src.devops_metrics_info import DevopsMetricsInfo, DeploymentInfo, DeployedTicket
from jira import JIRA
from typing import List


class DevopsMetricsService:

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel("INFO")
        self.jira_project_str = "CV"
        self.jira_possible_projects = ["CV", "IMGING", "IQ"]
        self.git_search_timeframe_in_months = 3
        self.bitbucket_auth_header = self._get_auth_header(os.environ.get("bitbucket_user_id"),
                                                     os.environ.get("bitbucket_api_password"))

    def get_devops_metrics_information(self, project_name: str, project_version: str, deployed_instant: datetime,
                                       deployed_by_user_id: str) -> DevopsMetricsInfo:
        dependency_repos = self._get_repos_to_check(project_name)
        released_tickets = self.get_released_tickets(project_name, project_version)
        released_ticket_ids = [ticket["ticket_id"] for ticket in released_tickets]

        merge_info_by_ticket_id = self._get_ticket_merge_dates(project_name, dependency_repos, project_version,
                                                              released_ticket_ids)

        deployment_info: DeploymentInfo = DeploymentInfo(project_name, project_version, deployed_instant,
                                                         deployed_by_user_id)
        deployed_tickets: List[DeployedTicket] = []

        self.logger.info("-----------------------------------------------------------------------")
        tickets_with_no_merge = []
        for released_ticket in released_tickets:
            ticket_id = released_ticket["ticket_id"]
            ticket_type = released_ticket["type"]
            ticket_created_datetime = released_ticket["created_datetime"]
            caused_by_ticket_id = released_ticket["caused_by"]

            if ticket_id not in merge_info_by_ticket_id:
                tickets_with_no_merge.append(ticket_id)
            else:
                merge_date = merge_info_by_ticket_id[ticket_id]["date"]
                merge_author = merge_info_by_ticket_id[ticket_id]["author"]
                repositories_touched = merge_info_by_ticket_id[ticket_id]["repositories"]
                deployed_ticket = DeployedTicket(deployment_info.id, project_name, ticket_id, ticket_type,
                                                 caused_by_ticket_id, ticket_created_datetime, merge_date, merge_author,
                                                 repositories_touched)
                deployed_tickets.append(deployed_ticket)
                self.logger.info("{}: type={} merged_instant={} merge_author={} repositories_touched={}"
                                 .format(deployed_ticket.ticket_id, deployed_ticket.ticket_type,
                                         deployed_ticket.merged_instant, deployed_ticket.merge_author,
                                         deployed_ticket.repositories_affected))

        self.logger.info("-----------------------------------------------------------------------")
        metrics_info: DevopsMetricsInfo = DevopsMetricsInfo(deployment_info, deployed_tickets)

        if len(tickets_with_no_merge) > 0:
            self.logger.warning("Tickets with no merge info found={}".format(tickets_with_no_merge))

        return metrics_info

    def get_released_tickets(self, project_name: str, project_version: str) -> List:

        jira: jira.client.JIRA = JIRA(server="https://lovelandinnovations.atlassian.net/",
                    basic_auth=(os.environ.get("jira_user_id"), os.environ.get("jira_api_key")))
        jira_version_str = self._get_jira_release_version_str(project_name, project_version)
        self.logger.info("Pulling tickets for project={} and version={}".format(self.jira_project_str,
                                                                                jira_version_str))
        version = jira.get_project_version_by_name(self.jira_project_str, jira_version_str)
        if version is None:
            self.logger.error("Version not found in JIRA. project={} and version={}".format(self.jira_project_str,
                                                                                            jira_version_str))
            exit(1)

        query_str = "project=" + self.jira_project_str + " AND fixVersion=" + jira_version_str
        released_tickets = jira.search_issues(jql_str=query_str)
        return self._convert_released_tickets_to_dicts(released_tickets)

    def _convert_released_tickets_to_dicts(self, released_tickets: array):
        released_ticket_dicts = []
        for ticket in released_tickets:
            caused_by_ticket_id = ""
            if ticket_type == "Bug":
                caused_by_ticket = self._get_caused_by_ticket(released_ticket)
                caused_by_ticket_id = str(caused_by_ticket) if caused_by_ticket is not "None" else ""

            ticket_dict = {
                "ticket_id": str(ticket),
                "type": str(released_ticket.fields.issuetype),
                "created_datetime": parser.parse(released_ticket.fields.created),
                "caused_by": caused_by_ticket_id
            }
            released_ticket_dicts.append(ticket_dict)

        return released_ticket_dicts

    def extract_ticket_merge_info_from_commits(self, repository: str, previous_release_hash: str) -> dict:
        commits_url = "https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{}/commits/master?" \
                      "fields=pagelen,values.message,values.date,values.author.raw,values.hash,next".format(repository)

        merge_info_by_ticket = {}

        while commits_url is not None:
            self.logger.info("requesting commit info at {}".format(commits_url))
            response = requests.get(url=commits_url, headers=self.bitbucket_auth_header)
            self._handle_response(response)

            commits_dict = json.loads(response.content)
            for commit in commits_dict["values"]:
                commit_date = parser.parse(commit["date"])
                # short cicuit the loop if we've reached the previous release in our search
                if self._is_finished_searching_commits(commit, commit_date, previous_release_hash):
                    self.logger.info("Stopping search in git for ticket matches. "
                                     "repo={} tickets_found={}".format(repository, len(merge_info_by_ticket)))
                    break

                # parse message for the tickets found in the commit message
                author_raw = commit["author"]["raw"]
                author_email = re.findall(r"[^<]*<([^>]*)>", author_raw)[0]

                # ignore commits by jenkins
                if "jenkins" not in author_email.lower():
                    commit_tickets = self._get_tickets_referenced_in_commit(commit)
                    for ticket in commit_tickets:
                        if ticket not in merge_info_by_ticket:
                            # ignore case if there are later commits with the ticket number, we only want the
                            # most recent
                            merge_info_by_ticket[ticket] = {"date": commit_date, "author": author_email,
                                                            "repositories": [repository]}

            commits_url = commits_dict.get("next", None)

        return merge_info_by_ticket

    def get_last_release_hash(self, repository: str, new_version: str) -> str:
        tags_url = "https://api.bitbucket.org/2.0/repositories/lovelandinnovations/{}/refs/tags?" \
                   "fields=values.name,values.target.hash,values.target.date&sort=-target.date".format(repository)

        version_pattern = re.compile(r"^\d+\.\d+\.\d+$")
        version_tags_count = 0

        while tags_url is not None:
            self.logger.info("requesting tag info at {}".format(tags_url))
            response = requests.get(url=tags_url, headers=self.bitbucket_auth_header)
            self._handle_response(response)

            tags_dict = json.loads(response.content)
            for tag in tags_dict["values"]:
                if re.match(version_pattern, tag["name"]):
                    # go back two release versions to manage overlap on QA window
                    if tag["name"] != new_version and version_tags_count > 1:
                        self.logger.info("found next version tag {} at hash={}"
                                         .format(tag["name"], tag["target"]["hash"]))
                        return tag["target"]["hash"]
                    version_tags_count += 1

            tags_url = tags_dict.get("next", None)

    # Guide search in other repos by tickets associated with the release, limit to most recent 3 months
    # There's an "app" search which is implemented here, then a dependency search for other tickets using the above
    # criteria
    def _get_ticket_merge_dates(self, repository: str, internal_repos_to_check: array, new_version: str,
                                release_tickets: array) -> dict:

        previous_release_hash = self.get_last_release_hash(repository, new_version)
        app_ticket_info_map = self.extract_ticket_merge_info_from_commits(repository, previous_release_hash)
        for internal_repo in internal_repos_to_check:
            cur_repo_ticket_info = self.extract_ticket_merge_info_from_commits(internal_repo, '')
            for ticket_id in cur_repo_ticket_info:
                if ticket_id in release_tickets:
                    if ticket_id in app_ticket_info_map:
                        if cur_repo_ticket_info[ticket_id]["date"] > app_ticket_info_map[ticket_id]["date"]:
                            cur_repo_ticket_info[ticket_id]["repositories"] \
                                .extend(app_ticket_info_map[ticket_id]["repositories"])
                            app_ticket_info_map[ticket_id] = cur_repo_ticket_info[ticket_id]
                        else:
                            app_ticket_info_map[ticket_id]["repositories"].append(internal_repo)
                    else:
                        app_ticket_info_map[ticket_id] = cur_repo_ticket_info[ticket_id]

        return app_ticket_info_map

    def _get_jira_release_version_str(self, project_name: str, project_version: str) -> str:
        prefix: str = ""
        if project_name == "cv-management-web":
            prefix = "cvmw"
        elif project_name == "cv-management-web-frontend":
            prefix = "cvmwf"
        elif project_name == "cv-event-listener":
            prefix = "cvel"
        elif project_name == "model-generator":
            prefix = "modgen"
        elif project_name == "measurements-generator":
            prefix = "measgen"
        elif project_name == "shading-analysis-generator":
            prefix = "shadegen"
        elif project_name == "cv-management-admin-web":
            prefix = "cvmadmin"
        elif project_name == "cv-management-admin-web-frontend":
            prefix = "cvmadminwf"
        else:
            self.logger.error("The project given does not match any known projects. providedProject={}"
                              .format(project_name))
            exit(5)

        jira_version = re.sub(r"-build\d+", "", project_version)

        return prefix + "-" + jira_version

    def _is_finished_searching_commits(self, commit: dict, commit_date: datetime, previous_release_hash: str) -> bool:
        time_based_limit = datetime.now(pytz.utc) - relativedelta(months=self.git_search_timeframe_in_months)

        result = False
        if commit["hash"] == previous_release_hash:
            self.logger.info("commit found with hash={}".format(commit["hash"]))
            result = True
        elif not previous_release_hash and commit_date < time_based_limit:
            self.logger.info("commit found from date={}".format(commit_date))
            result = True
        return result

    def _get_tickets_referenced_in_commit(self, commit: dict) -> array:
        commit_tickets = []
        for jira_project_str in self.jira_possible_projects:
            regex_str = r"[-\(\s\/]?(" + jira_project_str + r"\-[0-9]+)[-\)\s\/]?"
            tickets_found = re.findall(regex_str, commit["message"])

            for ticket_found in tickets_found:
                commit_tickets.append(ticket_found)

        if len(commit_tickets) == 0:
            author_raw = commit["author"]["raw"]
            self.logger.warning("No ticket found in commit with message={} author={}"
                                .format(commit["message"], author_raw))
        return commit_tickets


    def _get_caused_by_ticket(self, released_ticket: any) -> any:
        ticket_links = released_ticket.fields.issuelinks
        for ticket_link in ticket_links:
            # check if the link is a "Causes" or "Caused by" type of link
            if ticket_link.type.name == "Problem/Incident":
                # check if the link is a "Caused by", we only want to capture this end of the relationship
                if hasattr(ticket_link, "inwardIssue"):
                    return ticket_link.inwardIssue


    def _get_repos_to_check(self, project_name: str):
        internal_libraries_to_check_backend = ["cv-domain", "cv-event-domain", "cv-management-domain", "cv-output",
                                               "id-access-domain", "infrastructure", "location-domain", "persistence"]
        internal_libraries_to_check_frontend = ["cv-node-package", "infrastructure-node-package",
                                                "id-access-node-package", "location-node-package",
                                                "persistence-node-package"]

        if "frontend" in project_name:
            dependency_repos = internal_libraries_to_check_frontend
        else:
            dependency_repos = internal_libraries_to_check_backend

        return dependency_repos

    def _get_auth_header(self, user: str, password: str) -> dict:
        basic_auth = "{}:{}".format(user, password)
        basic_bytes = basic_auth.encode("ascii")
        encoded_text = "Basic {}".format(base64.b64encode(basic_bytes).decode("utf-8"))
        return {"Authorization": encoded_text, "content-type": "application/json"}

    def _handle_response(self, response: requests.Response) -> None:
        if response.status_code >= 400:
            self.logger.error("Failure calling={} with response={}, content={}"
                              .format(response.url, response, response.content[0:100]))
            exit(1)
