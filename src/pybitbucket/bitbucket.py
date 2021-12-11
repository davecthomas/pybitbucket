import configparser
import requests
import json


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
                except (IndexError, KeyError, TypeError):
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
                except (IndexError, KeyError, TypeError):
                    self.access_token = None
                    self.refresh_token = None
        else:
            self.access_token = None

        print(response.text)
        return self.access_token


class Bitbucket():
    def __init__(self, settings):
        self.projects_dict = {}
        self.projects = None
        self.workspace = None
        secret_config = configparser.RawConfigParser()
        secret_config.read(settings["secret-properties"])
        self.workspace_id = secret_config["atlassian"]["workspace_id"]
        if "default_project_key" in secret_config["atlassian"]:
            self.default_project_key = secret_config["atlassian"]["default_project_key"]
        else:
            self.default_project_key = None
        self.settings = secret_config["atlassian_oauth"]
        config = configparser.RawConfigParser()
        config.read(settings["properties"])
        self.version = config["general"]["version"]
        print(f"Bitbucket version {self.version}")
        self.workspace_id = secret_config["atlassian"]["workspace_id"]
        self.oauth2 = BbOauth2(self.settings)
        self.access_token = self.oauth2.get_access_token()
        # Initialize the workspace and grab all projects therein
        self.get_workspace()
        self.get_projects()

    def get_repos(self):
        if self.workspace is not None:
            url = self.workspace.dict_urls["repositories"]["href"]
            print("get_repos: {url}".format(url=url))

            headers = {
                "Accept": "application/json",
                "Authorization": "Bearer {access_token}".format(access_token=self.access_token)
            }

            response = requests.request(
                "GET",
                url,
                headers=headers
            )

            print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

    def get_projects(self):
        if self.workspace is not None:

            url = self.workspace.dict_urls["projects"]["href"]
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
                    self.projects = response.json()
                    try:
                        projects_list = self.projects["values"]

                    except (IndexError, KeyError, TypeError):
                        projects_list = []

                    for project in projects_list:
                        new_project = Project(self.workspace, project)
                        self.projects_dict[new_project.key] = new_project

                    if self.default_project_key is not None:
                        print(f"Default project {self.default_project_key}")
                        if self.default_project_key in self.projects_dict:
                            print(f"Default project found {self.projects_dict[self.default_project_key].name}")
                            # Get the list of repos for the default project
                            repos_dict = self.projects_dict[self.default_project_key].get_repos()
                            print(f"default project repos {repos_dict}")

            # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
        else:
            print("No workspace")

    def get_workspace(self):
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
                self.workspace = Workspace(response.json(), self.access_token)

        print(f"get workspace {self.workspace.name}")


class Workspace:
    def __init__(self, workspace_dict, access_token):
        try:
            self.dict_urls = workspace_dict["links"]
            self.slug = workspace_dict["slug"]
            self.name = workspace_dict["name"]
            self.uuid = workspace_dict["uuid"]
            self.access_token = access_token
        except (IndexError, KeyError, TypeError):
            self.dict_urls = None
            self.slug = None
            self.name = None
            self.uuid = None


class Project:
    def __init__(self, workspace, project_dict):
        # print(f"Project {project_dict}")
        self.workspace = workspace
        self.repos = None
        self.repos_dict = {}

        try:
            self.key = project_dict["key"]
            self.links = project_dict["links"]
            self.description = project_dict["description"]
            self.name = project_dict["name"]
            self.uuid = project_dict["uuid"]
            self.repos_url = project_dict["links"]["repositories"]["href"]
            # print("Project {name} repo url {url}".format(name=self.name, url=self.repos_url))
            self.avatar_url = project_dict["links"]["avatar"]["href"]
        except (IndexError, KeyError, TypeError):
            self.key = None
            self.links = None
            self.description = None
            self.name = None
            self.uuid = None
            self.avatar_url = None
            self.repos_url = None

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
                            new_repo = Repository(self.workspace, repo)
                            self.repos_dict[new_repo.name] = new_repo

                        if "next" not in self.repos:
                            has_more_pages = False
                        else:
                            repos_url = self.repos["next"]

            # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

    def get_repos(self):
        return self.repos_dict


class Repository:
    def __init__(self, workspace, repo_dict):
        pull_request_state = "MERGED"
        self.workspace = workspace
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
        except (IndexError, KeyError, TypeError):
            self.links = None
            self.description = None
            self.name = None
            self.full_name = None
            self.uuid = None
            self.avatar_url = None
            self.url = None
            self.slug = None

    def get_pull_requests(self, state="MERGED"):
        url = f"https://api.bitbucket.org/2.0/repositories/{self.workspace.slug}/{{{self.uuid}}}/pullrequests"
        print(f"pull_requests {self.name} url={url}")

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.workspace.access_token}"
        }

        response = requests.request(
            "GET",
            url,
            headers=headers
        )

        print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))


class PullRequest:
    def __init__(self, workspace, project, repo):
        self.workspace = workspace
        self.project = project
        self.repo = repo
