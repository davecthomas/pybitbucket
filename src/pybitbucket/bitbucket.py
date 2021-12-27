import configparser
import json
import traceback

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
        # print(f"CommitList {commit.message}")

    def to_dataframe(self):
        self.df = pd.DataFrame(self.commit_list_dict)
        return self.df


class PullRequestList:
    def __init__(self):
        self.pr_list_dict = []  # This is a list of dictionaries of commits (for data framing)
        self.pr_list = []  # This is a list of Commit objects
        self.df = None

    def add(self, commit):
        self.pr_list.append(commit)
        self.pr_list_dict.append(commit.to_dict())

    def to_dataframe(self):
        self.df = pd.DataFrame(self.pr_list_dict)
        return self.df

    def get_uniques_list(self):
        if self.df is None:
            df = self.to_dataframe()
        else:
            df = self.df
        df['pr_id'].unique().tolist()


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
        self.prs_file = None
        self.commits_file = None

        # Initialize the workspace and grab all projects therein

        if "prs_file" in secret_config["general"]:
            self.prs_file = secret_config["general"]["prs_file"]
        if "commits_file" in secret_config["general"]:
            self.prs_file = secret_config["general"]["commits_file"]
        if "default_deploy_repo_list" in secret_config["atlassian"]:
            self.default_deploy_repo_list = secret_config["atlassian"]["default_deploy_repo_list"].split(",")
        else:
            self.default_deploy_repo_list = []
        if "default_project_key_list" in secret_config["atlassian"]:
            self.default_project_keys_list = secret_config["atlassian"]["default_project_key_list"].split(",")
        else:
            self.default_project_keys_list = []

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
                              "default_deploy_repo_list": self.default_deploy_repo_list,
                              "default_project_keys_list": self.default_project_keys_list,
                              "get_prs_updated_since_utc": self.get_prs_updated_since_utc,
                              "get_prs_updated_since_datetime": self.get_prs_updated_since_datetime,
                              "require_jira_issue_id_in_commit_message": self.require_jira_issue_id_in_commit_message
                              }
        print(f"pybitbucket settings: {self.settings_dict}")

        self.workspace = self.get_workspace()

        if len(self.default_project_keys_list) > 0:
            for project_key in self.default_project_keys_list:
                print(f"Default project: {project_key} (getting PRs for all repos)")
                project = self.workspace.get_project(project_key)
                # Get the list of repos for the default project
                repos_dict = project.get_repos()
                # print(f"default project repos {repos_dict}")
                for repo_name, repo in repos_dict.items():
                    repo.get_pull_requests(default_deploy_repo_list=self.default_deploy_repo_list,
                                           get_prs_updated_since_utc=self.get_prs_updated_since_utc,
                                           require_jira_issue_id_in_commit_message=self.require_jira_issue_id_in_commit_message)
        else:
            self.workspace.get_projects()

        # print(f"Dataframe {self.workspace.commit_list.to_dataframe().to_csv(self.commits_file)}")
        # print(f"Dataframe {self.workspace.pr_list.to_dataframe().to_csv(self.commits_file)}")
        self.df_commits = self.workspace.commit_list.to_dataframe()
        # df_commits.to_csv(self.commits_file)
        self.df_prs = self.workspace.pr_list.to_dataframe()
        # df_prs.to_csv(self.prs_file)
        df = pd.concat([self.df_prs, self.df_commits], ignore_index=True)
        df.to_csv("df.csv")

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
                    workspace = Workspace(response.json(), self.access_token, self.default_project_keys_list,
                                          self.default_deploy_repo_list)

            print(f"get workspace {workspace.name}")
            return workspace

    def get_settings(self):
        return self.settings_dict


class Workspace:
    def __init__(self, workspace_dict, access_token, default_project_keys_list=[], default_deploy_repo_list=[]):
        self.commit_list_df = None
        self.pr_list_df = None
        self.access_token = access_token
        self.default_project_keys_list = default_project_keys_list
        self.dict_urls = None
        self.slug = None
        self.name = None
        self.uuid = None
        self.projects_dict = {}
        self.commit_list = CommitList()
        self.pr_list = PullRequestList()
        self.default_deploy_repo_list = default_deploy_repo_list
        self.workspace_dict = workspace_dict

        try:
            self.dict_urls = workspace_dict["links"]
            self.slug = workspace_dict["slug"]
            self.name = workspace_dict["name"]
            self.uuid = workspace_dict["uuid"]

        except (IndexError, KeyError, TypeError) as e:
            print(f"Exception {e}")
            print(f"Repository: {self.workspace_dict}")

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
            print(f"Project: {self.project_dict}")

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
            print(f"Repository: {self.repo_dict}")

    def get_pull_requests(self, default_deploy_repo_list=[], get_prs_updated_since_utc=None,
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
                                     repo=self, pr_dict=pr_dict, default_deploy_repo_list=default_deploy_repo_list,
                                     require_jira_issue_id_in_commit_message=require_jira_issue_id_in_commit_message)
                    self.pull_requests_list.append(pr)

                    # print(f"pr {pr.to_dict()}")

                    # if pr.source_commit_url is not None:
                    #     print(f"commit: {pr.source_commit_url}")

                if "next" not in pr_response:
                    has_more_pages = False
                else:
                    url = pr_response["next"]
        # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))


class PullRequest:
    def __init__(self, workspace, project, repo, pr_dict, default_deploy_repo_list=[],
                 require_jira_issue_id_in_commit_message=False):
        # print(f"PullRequest{pr_dict}")
        self.query_param_pr_commits_sort_str = "-updated_on"  # sort PR commits by last updated first
        self.pr_dict = pr_dict
        self.workspace = workspace
        self.project = project
        self.repo = repo
        self.default_deploy_repo_list = default_deploy_repo_list
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
        self.jira_id = None
        self.pr_list = workspace.pr_list

        # print(f"Pull Request dict {pr_dict}")

        try:
            if "title" in pr_dict:
                self.title = pr_dict["title"]
                if require_jira_issue_id_in_commit_message:
                    jira_id = find_jira_id(self.title)
                    if jira_id is not None:
                        self.jira_id = jira_id
            if "id" in pr_dict:
                self.id = pr_dict["id"]
            if "created_on" in pr_dict:
                self.created_on_str = pr_dict["created_on"]
                self.created_on_dt = datetime.fromisoformat(self.created_on_str)
            if "updated_on" in pr_dict:
                self.updated_on = pr_dict["updated_on"]
                self.updated_on_dt = datetime.fromisoformat(self.updated_on)
            if "description" in pr_dict:
                self.description = pr_dict["description"]

            if "source" in pr_dict and "branch" in pr_dict["source"] and "name" in pr_dict["source"]["branch"]:
                self.source_branch = pr_dict["source"]["branch"]["name"]
                if self.jira_id is None and require_jira_issue_id_in_commit_message and "-" in self.source_branch:
                    jira_id_in_branch_list = self.source_branch.split("-")
                    if len(jira_id_in_branch_list) > 1:
                        jira_id_str_test = f"{jira_id_in_branch_list[0]}-{jira_id_in_branch_list[1]}"
                        self.jira_id = find_jira_id(jira_id_str_test)
                if "commit" in pr_dict["source"] and "links" in pr_dict["source"]["commit"]:
                    self.source_commit_hash = pr_dict["source"]["commit"]["hash"]
                    self.source_commit_url = pr_dict["source"]["commit"]["links"]["self"]["href"]
            if "destination" in pr_dict and "branch" in pr_dict["destination"] and "name" in pr_dict["destination"]["branch"]:
                self.destination_branch = pr_dict["destination"]["branch"]["name"]
                if "commit" in pr_dict["destination"] and "links" in pr_dict["destination"]["commit"]:
                    self.destination_commit_hash = pr_dict["destination"]["commit"]["hash"]
                    self.destination_commit_url = pr_dict["destination"]["commit"]["links"]["self"]["href"]
            if "author" in pr_dict and "display_name" in pr_dict["author"]:
                self.author = pr_dict["author"]["display_name"]

            if "links" in pr_dict:
                self.links = pr_dict["links"]
                if "self" in self.links and "href" in pr_dict["links"]["self"]:
                    self.url = pr_dict["links"]["self"]["href"]

                # Get the commits related to the pull request
                if "commits" in self.links and "href" in self.links["commits"]:
                    self.commits_url = self.links["commits"]["href"]
                    self.list_commits = []
                    headers = {
                        "Authorization": f"Bearer {self.workspace.access_token}"
                    }

                    url = self.commits_url
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
                            # print(f"PR commits: {pr_commits_response}")

                            try:
                                if "values" in pr_commits_response:
                                    pr_commits_list = pr_commits_response["values"]

                            except (IndexError, KeyError, TypeError):
                                print(f"get_pr_commits has no values in returned json {pr_commits_response}")

                            for pr_commit_dict in pr_commits_list:
                                # print(f"pr_commit_dict {pr_commit_dict}")
                                commit = Commit(self.workspace, project=self.project,
                                                pr=self, pr_commit_dict=pr_commit_dict,
                                                require_jira_issue_id_in_commit_message=require_jira_issue_id_in_commit_message)
                                self.pr_commits_list.append(commit)
                                # print(f"commit {commit.message}")

                                # if pr.source_commit_url is not None:
                                #     print(f"commit: {pr.source_commit_url}")

                            if "next" not in pr_commits_response:
                                has_more_pages = False
                            else:
                                url = pr_commits_response["next"]
            if "state" in pr_dict:
                self.state = pr_dict["state"]
            if "merge_commit" in pr_dict:
                self.merge_commit = pr_dict["merge_commit"]
                if "links" in pr_dict["merge_commit"] and "self" in pr_dict["merge_commit"]["links"] and \
                        "href" in pr_dict["merge_commit"]["links"]["self"]:
                    self.merge_commit_url = pr_dict["merge_commit"]["links"]["self"]["href"]

            if self.pr_list is not None:
                self.pr_list.add(self)

        except (IndexError, KeyError, TypeError) as e:
            print(f"Exception in PullRequest {e}")
            print(traceback.format_exc())
            print(f"PullRequest: {pr_dict}")
            print(f"Merge Commit {self.merge_commit}")

    def get_commits(self):
        return self.pr_commits_list

    def to_dict(self):
        return {
            "type": "PR",
            "pr_id": self.id,
            "message": self.title,  # renamed this from title so it matches with Commit.message in dataframe.concat
            "created_datetime": self.created_on_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_datetime": self.updated_on_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "project": self.project.name,
            "workspace": self.workspace.name,
            "author": self.author,
            "repo": self.repo.name,
            "state": self.state,
            "source_branch": self.source_branch,
            "destination_branch": self.destination_branch,
            "jira_id": self.jira_id
        }


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
            self.date_utc = pr_commit_dict["date"]
            self.datetime = datetime.strptime(
                self.date_utc, '%Y-%m-%dT%H:%M:%S%z')
            self.message = pr_commit_dict["message"]
            # print(f"Commit {self.message}")
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
        return {"type": "Commit",
                "hash": self.hash,
                "jira_id": self.jira_id,
                "created_datetime": self.datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "message": self.message,
                "project": self.project.name,
                "repo": self.pr.repo.name,
                "workspace": self.workspace.name,
                "author": self.author,
                "pr_id": self.pr.id,
                "source_branch": self.pr.source_branch,
                "destination_branch": self.pr.destination_branch,
                "is_deploy_repo": (self.pr.repo.name in self.workspace.default_deploy_repo_list)
                }
