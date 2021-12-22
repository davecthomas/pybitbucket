import configparser
import json
from src.pybitbucket.jira import find_jira_id
from datetime import datetime
from urllib.parse import urlencode, quote_plus
import numpy as np
import pandas as pd

import requests


class BbOauth2Test:
    def __init__(self, settings):
        print("Not implemented")


class BbOauth2:
    def __init__(self, settings):
        self.access_token = None
        self.refresh_token = None
        self.dict_urls = None
        self.auth_uri = "https://bitbucket.org/site/oauth2/authorize"
        self.token_uri = "https://bitbucket.org/site/oauth2/access_token"
        self.server_base_uri = "https://api.bitbucket.org/"
        self.settings = settings
        self.key = settings["key"]
        self.secret = settings["secret"]

    def get_access_token(self):
        data = {
            'grant_type': 'client_credentials'
        }
        response = requests.post('https://bitbucket.org/site/oauth2/access_token', data=data,
                                 auth=(self.key, self.secret))
        if response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.access_token = data["access_token"]
                    self.refresh_token = data["refresh_token"]
                except (IndexError, KeyError, TypeError) as e:
                    print(f"Exception {e}")
                    self.access_token = None
                    self.refresh_token = None

            elif response.status_code == 401:
                self.access_token = self.refresh_access_token()
        else:
            self.access_token = None

        # print(response.text)
        return self.access_token

    def refresh_access_token(self):
        print("refresh_token")
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        response = requests.post('https://bitbucket.org/site/oauth2/access_token', data=data,
                                 auth=(self.key, self.secret))
        if response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.access_token = data["access_token"]
                    self.refresh_token = data["refresh_token"]
                except (IndexError, KeyError, TypeError) as e:
                    print(f"Exception {e}")
                    self.access_token = None
                    self.refresh_token = None
        else:
            self.access_token = None

        print(response.text)
        return self.access_token


class CommitList:
    def __init__(self):
        self.commit_list_dict = []  # This is a list of dictionaries of commits (for data framing)
        self.commit_list = []  # This is a list of Commit objects
        self.df = None

    def add(self, commit):
        self.commit_list.append(commit)
        self.commit_list_dict.append(commit.to_dict())

    def to_dataframe(self):
        self.df = pd.DataFrame(self.commit_list_dict)
        return self.df


class Bitbucket:
    def __init__(self, settings):
        self.settings_dict = {}
        self.projects_dict = {}
        self.projects = None
        self.workspace = None
        secret_config = configparser.RawConfigParser()
        secret_config.read(settings["secret-properties"])
        self.workspace_id = secret_config["atlassian"]["workspace_id"]
        self.settings = secret_config["atlassian_oauth"]
        config = configparser.RawConfigParser()
        config.read(settings["properties"])
        self.version = config["general"]["version"]
        print(f"Bitbucket version {self.version}")
        self.workspace_id = secret_config["atlassian"]["workspace_id"]
        self.oauth2 = BbOauth2(self.settings)
        self.access_token = self.oauth2.get_access_token()
        # Initialize the workspace and grab all projects therein

        if "default_deploy_repo" in secret_config["atlassian"]:
            self.default_deploy_repo = secret_config["atlassian"]["default_deploy_repo"]
        else:
            self.default_deploy_repo = None
        if "default_project_key" in secret_config["atlassian"]:
            self.default_project_key = secret_config["atlassian"]["default_project_key"]
        else:
            self.default_project_key = None

        if "get_prs_updated_since_utc" in secret_config["atlassian"]:
            self.get_prs_updated_since_utc = secret_config["atlassian"]["get_prs_updated_since_utc"]
            self.get_prs_updated_since_datetime = datetime.strptime(
                self.get_prs_updated_since_utc, '%Y-%m-%dT%H:%M:%S%z')
        else:
            self.get_prs_updated_since_datetime = None

        if "require_jira_issue_id_in_commit_message" in secret_config["atlassian"]:
            self.require_jira_issue_id_in_commit_message = bool(
                secret_config["atlassian"]["require_jira_issue_id_in_commit_message"])
        else:
            self.require_jira_issue_id_in_commit_message = False

        self.settings_dict = {"version": self.version,
                              "workspace_id": self.workspace_id,
                              "default_deploy_repo": self.default_deploy_repo,
                              "default_project_key": self.default_project_key,
                              "get_prs_updated_since_utc": self.get_prs_updated_since_utc,
                              "get_prs_updated_since_datetime": self.get_prs_updated_since_datetime,
                              "require_jira_issue_id_in_commit_message": self.require_jira_issue_id_in_commit_message
                              }
        print(f"pybitbucket settings: {self.settings_dict}")

        self.workspace = self.get_workspace()

        if self.default_project_key is not None:
            print(f"Default project: {self.default_project_key} (getting PRs for all repos)")
            project = self.workspace.get_project(self.default_project_key)
            # Get the list of repos for the default project
            repos_dict = project.get_repos()
            # print(f"default project repos {repos_dict}")
            for repo_name, repo in repos_dict.items():
                if self.default_deploy_repo is not None and repo_name == self.default_deploy_repo:
                    default_deploy_repo = True
                else:
                    default_deploy_repo = False
                repo.get_pull_requests(default_deploy_repo=default_deploy_repo,
                                       get_prs_updated_since_utc=self.get_prs_updated_since_utc,
                                       require_jira_issue_id_in_commit_message=self.require_jira_issue_id_in_commit_message)
        else:
            self.workspace.get_projects()

        print(f"Dataframe {self.workspace.commit_list.to_dataframe().to_csv()}")

    def get_workspace(self):
        workspace = None

        if self.workspace is not None:
            return self.workspace
        else:
            url = "https://api.bitbucket.org/2.0/workspaces/{{{workspace}}}".format(workspace=self.workspace_id)

            headers = {
                "Accept": "application/json",
                "Authorization": "Bearer {access_token}".format(access_token=self.access_token)
            }

            response = requests.request(
                "GET",
                url,
                headers=headers
            )
            if response:
                if response.status_code == 200:
                    workspace = Workspace(response.json(), self.access_token, self.default_project_key)

            print(f"get workspace {workspace.name}")
            return workspace


class Workspace:
    def __init__(self, workspace_dict, access_token, default_project_key=None):
        self.commit_list_df = None
        self.access_token = access_token
        self.default_project_key = default_project_key
        self.dict_urls = None
        self.slug = None
        self.name = None
        self.uuid = None
        self.projects_dict = {}
        self.commit_list = CommitList()

        try:
            self.dict_urls = workspace_dict["links"]
            self.slug = workspace_dict["slug"]
            self.name = workspace_dict["name"]
            self.uuid = workspace_dict["uuid"]

        except (IndexError, KeyError, TypeError) as e:
            print(e)

    def get_project(self, key):
        project = None
        if key in self.projects_dict:
            project = self.projects_dict[key]
        else:
            url = f"https://api.bitbucket.org/2.0/workspaces/{self.slug}/projects/{key}"
            # print(f"get_project {key} url={url}")

            headers = {
                "Accept": "application/json",
                "Authorization": "Bearer {access_token}".format(access_token=self.access_token)
            }

            response = requests.request(
                "GET",
                url,
                headers=headers
            )
            if response:
                if response.status_code == 200:
                    project_dict = response.json()
                    project = Project(self, project_dict)

            # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
        return project

    def get_projects(self):
        url = self.dict_urls["projects"]["href"]
        print("get_projects: {url}".format(url=url))

        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer {access_token}".format(access_token=self.access_token)
        }

        response = requests.request(
            "GET",
            url,
            headers=headers
        )
        if response:
            if response.status_code == 200:
                self.projects_dict = response.json()
                try:
                    projects_list = self.projects_dict["values"]

                except (IndexError, KeyError, TypeError) as e:
                    print(f"Exception {e}")
                    projects_list = []

                for project in projects_list:
                    new_project = Project(self, project)
                    self.projects_dict[new_project.key] = new_project

        # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
        else:
            print("No workspace")


class Project:
    def __init__(self, workspace, project_dict):
        # print(f"Project {project_dict}")
        self.workspace = workspace
        self.repos = None
        self.repos_dict = {}
        self.key = None
        self.links = None
        self.description = None
        self.name = None
        self.uuid = None
        self.avatar_url = None
        self.repos_url = None

        try:
            self.key = project_dict["key"]
            self.links = project_dict["links"]
            self.description = project_dict["description"]
            self.name = project_dict["name"]
            self.uuid = project_dict["uuid"]
            self.repos_url = project_dict["links"]["repositories"]["href"]
            # print("Project {name} repo url {url}".format(name=self.name, url=self.repos_url))
            self.avatar_url = project_dict["links"]["avatar"]["href"]
        except (IndexError, KeyError, TypeError) as e:
            print(f"Exception {e}")

        if self.repos_url is not None:
            repos_url = self.repos_url
            has_more_pages = True
            while has_more_pages:
                # print("get repos {repos_url}".format(repos_url=repos_url))
                headers = {
                    "Accept": "application/json",
                    "Authorization": "Bearer {access_token}".format(access_token=self.workspace.access_token)
                }

                response = requests.request(
                    "GET",
                    repos_url,
                    headers=headers
                )
                if response:
                    if response.status_code == 200:
                        self.repos = response.json()

                        try:
                            repos_list = self.repos["values"]

                        except (IndexError, KeyError, TypeError):
                            repos_list = []

                        for repo in repos_list:
                            new_repo = Repository(self.workspace, project=self, repo_dict=repo)
                            self.repos_dict[new_repo.name] = new_repo

                        if "next" not in self.repos:
                            has_more_pages = False
                        else:
                            repos_url = self.repos["next"]

            # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

    def get_repos(self):
        return self.repos_dict


class Repository:
    def __init__(self, workspace, project, repo_dict):
        pull_request_state = "MERGED"
        self.query_param_pr_sort_str = "-updated_on"  # sort PRs by last updated first
        self.workspace = workspace
        self.pull_requests_list = []
        self.project = project
        self.repo_dict = repo_dict
        self.links = None
        self.description = None
        self.name = None
        self.full_name = None
        self.uuid = None
        self.avatar_url = None
        self.url = None
        self.slug = None
        # print(f"Repository {repo_dict}")
        try:
            self.links = repo_dict["links"]
            self.description = repo_dict["description"]
            self.name = repo_dict["name"]
            self.full_name = repo_dict["full_name"]
            self.uuid = repo_dict["uuid"]
            self.avatar_url = repo_dict["links"]["avatar"]["href"]
            self.url = repo_dict["links"]["self"]["href"]
            self.slug = repo_dict["slug"]

            # print(f"Repository {self.name}")
        except (IndexError, KeyError, TypeError) as e:
            print(f"Exception {e}")

    def get_pull_requests(self, default_deploy_repo=False, get_prs_updated_since_utc=None,
                          require_jira_issue_id_in_commit_message=False, state="MERGED"):
        url_query_parameter = f"?state={state}&sort={self.query_param_pr_sort_str}"
        if get_prs_updated_since_utc is not None:
            payload = {"q": f"updated_on>{get_prs_updated_since_utc}"}
            get_prs_updated_since_utc_urlencoded = urlencode(payload, quote_via=quote_plus)
            url_query_parameter = f"{url_query_parameter}&{get_prs_updated_since_utc_urlencoded}"
        url = f"https://api.bitbucket.org/2.0/repositories/{self.workspace.slug}/{self.slug}/pullrequests" + url_query_parameter
        # print(f"pull_requests {self.name} url={url}")

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.workspace.access_token}"
        }

        has_more_pages = True
        pagenum = 0
        while has_more_pages:
            pagenum = pagenum + 1
            # print(f"get_pull_requests page {pagenum} url={url}")
            response = requests.request(
                "GET",
                url,
                headers=headers
            )
            if response and response.status_code == 200:
                pr_response = response.json()
                pr_list = []

                try:
                    pr_list = pr_response["values"]

                except (IndexError, KeyError, TypeError):
                    print(f"get_pull_requests has no values in returned json {pr_response}")

                for pr_dict in pr_list:
                    pr = PullRequest(self.workspace, project=self.project,
                                     repo=self, pr_dict=pr_dict, default_deploy_repo=default_deploy_repo,
                                     require_jira_issue_id_in_commit_message=require_jira_issue_id_in_commit_message)
                    self.pull_requests_list.append(pr)
                    # print(f"pr {pr.title}")

                    # if pr.source_commit_url is not None:
                    #     print(f"commit: {pr.source_commit_url}")

                if "next" not in pr_response:
                    has_more_pages = False
                else:
                    url = pr_response["next"]
        # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))


class PullRequest:
    def __init__(self, workspace, project, repo, pr_dict, default_deploy_repo=False,
                 require_jira_issue_id_in_commit_message=False):
        self.query_param_pr_commits_sort_str = "-updated_on"  # sort PR commits by last updated first
        self.pr_dict = pr_dict
        self.workspace = workspace
        self.project = project
        self.repo = repo
        self.default_deploy_repo = default_deploy_repo
        self.title = None
        self.id = None
        self.created_on_str = None
        self.created_on_dt = None
        self.description = None
        self.source_branch = None
        self.source_commit_hash = None
        self.source_commit_url = None
        self.destination_branch = None
        self.destination_commit_hash = None
        self.destination_commit_url = None
        self.author = None
        self.url = None
        self.links = None
        self.state = None
        self.merge_commit = None
        self.merge_commit_url = None
        self.pr_commits_list = []

        try:
            if "title" in pr_dict:
                self.title = pr_dict["title"]
            self.id = pr_dict["id"]
            self.created_on_str = pr_dict["created_on"]
            if "updated_on" in pr_dict:
                self.updated_on = pr_dict["updated_on"]
            if "description" in pr_dict:
                self.description = pr_dict["description"]
            self.created_on_dt = datetime.fromisoformat(self.created_on_str)
            if "source" in pr_dict:
                self.source_branch = pr_dict["source"]["branch"]["name"]
                self.source_commit_hash = pr_dict["source"]["commit"]["hash"]
                self.source_commit_url = pr_dict["source"]["commit"]["links"]["self"]["href"]
            if "destination" in pr_dict:
                self.destination_branch = pr_dict["destination"]["branch"]["name"]
                self.destination_commit_hash = pr_dict["destination"]["commit"]["hash"]
                self.destination_commit_url = pr_dict["destination"]["commit"]["links"]["self"]["href"]
            self.author = pr_dict["author"]["display_name"]
            self.url = pr_dict["links"]["self"]["href"]
            self.links = pr_dict["links"]
            # if default_deploy_repo:
            #     print(f"default_deploy_repo: {self.title} : {self.description}")

            # Get the commits related to the pull request
            if "commits" in self.links:
                self.commits_url = self.links["commits"]["href"]
                self.list_commits = []
                headers = {
                    "Authorization": f"Bearer {self.workspace.access_token}"
                }

                url = self.commits_url
                url_query_parameter = f"?sort={self.query_param_pr_commits_sort_str}"
                has_more_pages = True
                pagenum = 0
                while has_more_pages:
                    pagenum = pagenum + 1
                    # print(f"get PR commits page {pagenum} url={url}")

                    pr_commits_response = requests.request(
                        "GET",
                        url,
                        headers=headers
                    )
                    if pr_commits_response and pr_commits_response.status_code == 200:
                        pr_commits_response = pr_commits_response.json()
                        pr_commits_list = []
                        # print("PR commits:")
                        # print(json.dumps(json.loads(pr_commits_response.text), sort_keys=True, indent=4, separators=(",", ": ")))

                        try:
                            pr_commits_list = pr_commits_response["values"]

                        except (IndexError, KeyError, TypeError):
                            print(f"get_pr_commits has no values in returned json {pr_commits_response}")

                        for pr_commit_dict in pr_commits_list:
                            commit = Commit(self.workspace, project=self.project,
                                            pr=self, pr_commit_dict=pr_commit_dict,
                                            require_jira_issue_id_in_commit_message=require_jira_issue_id_in_commit_message)
                            self.pr_commits_list.append(commit)
                            # print(f"pr {pr.title}")

                            # if pr.source_commit_url is not None:
                            #     print(f"commit: {pr.source_commit_url}")

                        if "next" not in pr_commits_response:
                            has_more_pages = False
                        else:
                            url = pr_commits_response["next"]

            self.state = pr_dict["state"]
            if "merge_commit" in pr_dict:
                self.merge_commit = pr_dict["merge_commit"]
                self.merge_commit_url = pr_dict["merge_commit"]["links"]["self"]["href"]

        except (IndexError, KeyError, TypeError) as e:
            print(f"Exception {e}")


class Commit:
    def __init__(self, workspace, project, pr, pr_commit_dict, require_jira_issue_id_in_commit_message=False):
        self.workspace = workspace
        self.project = project
        self.pr = pr
        self.pr_commit_dict = pr_commit_dict
        self.date = None
        self.message = None
        self.hash = None
        self.has_jira_id = False
        self.jira_id = None
        self.author = None
        self.commit_list = workspace.commit_list

        try:
            self.date = pr_commit_dict["date"]
            self.message = pr_commit_dict["message"]
            self.hash = pr_commit_dict["hash"]
            self.author = pr_commit_dict["author"]["user"]["display_name"]
            # print(f"PR Commit {self.date} {self.message}")
            if require_jira_issue_id_in_commit_message:
                jira_id = find_jira_id(self.message)
                # print(f"find_jira_string {has_jira_id}")
                if jira_id is not None:
                    self.has_jira_id = True
                    self.jira_id = jira_id
            if self.commit_list is not None:
                self.commit_list.add(self)

        except (IndexError, KeyError, TypeError) as e:
            print(f"Exception {e}")
            print(f"Commit: {self.pr_commit_dict}")

    def to_dict(self):
        return {"hash": self.hash,
                "jira_id": self.jira_id,
                "date": self.date,
                "message": self.message,
                "project": self.project.name,
                "workspace": self.workspace.name,
                "author": self.author
                }
