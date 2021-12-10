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

        # Response looks like this:
        # {"scopes": "pipeline runner pullrequest team project account issue snippet",
        # "access_token": "3N7udm1K-OASRIOz1XZnKowWiQjyvvkzz0ELJxooOHK26jP2RPEGSj-kWtK1t1EMtme0zGTpUQrsz-U1TKYFBzzgC8AU49PKUH-98C7jr_W2WOp7eOFJIMhL",
        # "expires_in": 7200,
        # "token_type": "bearer",
        # "state": "client_credentials",
        # "refresh_token": "bqh4vsh8xCtaELGwwD"}
        print(response.text)
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
        self.projects_list = []
        self.projects = None
        self.workspace = None
        config = configparser.RawConfigParser()
        config.read(settings["properties"])
        self.workspace_id = config["atlassian"]["workspace_id"]
        self.project_key = config["atlassian"]["project_key"]
        self.settings = config["atlassian_oauth"]
        self.oauth2 = BbOauth2(self.settings)
        self.access_token = self.oauth2.get_access_token()
        # Initialize the workspace and grab all projects therein
        self.get_workspace()
        self.get_projects()
        # self.get_repos()

    def get_pull_requests(self):
        url = "https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests".format(
            workspace="xpanseinc", repo_slug=123)

        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer <access_token>"
        }

        response = requests.request(
            "GET",
            url,
            headers=headers
        )

        print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

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
                        new_project = Project(project, self.access_token)
                        self.projects_list.append(new_project)
                        # repos_list = new_project.repos_url
                        # print(f"Project {new_project.name}")

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
                self.workspace = Workspace(response.json())

        print("get workspace {name}".format(name=self.workspace.name))


class Workspace:
    def __init__(self, workspace_dict):
        try:
            self.dict_urls = workspace_dict["links"]
            self.slug = workspace_dict["slug"]
            self.name = workspace_dict["name"]
            self.uuid = workspace_dict["uuid"]
        except (IndexError, KeyError, TypeError):
            self.dict_urls = None
            self.slug = None
            self.name = None
            self.uuid = None


class Project:
    def __init__(self, project_dict, access_token):
        print(f"Project {project_dict}")
        try:
            self.key = project_dict["key"]
            self.links = project_dict["links"]
            self.description = project_dict["description"]
            self.name = project_dict["name"]
            self.uuid = project_dict["uuid"]
            self.repos_url = project_dict["links"]["repositories"]["href"]
            print("Project {name} repo url {url}".format(name=self.name, url=self.repos_url))
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
            print("get repo {repos_url}".format(repos_url=self.repos_url))
            headers = {
                "Accept": "application/json",
                "Authorization": "Bearer {access_token}".format(access_token=access_token)
            }

            response = requests.request(
                "GET",
                self.repos_url,
                headers=headers
            )
            if response:
                if response.status_code == 200:
                    self.repo = Repository(response.json())

            # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))


class Repository:
    def __init__(self, repo_dict):
        print(f"Project {repo_dict}")
        # try:
        #     self.key = repo_dict["key"]
        #     self.links = repo_dict["links"]
        #     self.description = repo_dict["description"]
        #     self.name = repo_dict["name"]
        #     self.uuid = repo_dict["uuid"]
        #     self.avatar_url = repo_dict["links"]["avatar"]["href"]
        # except (IndexError, KeyError, TypeError):
        #     self.key = None
        #     self.links = None
        #     self.description = None
        #     self.name = None
        #     self.uuid = None
        #     self.avatar_url = None
