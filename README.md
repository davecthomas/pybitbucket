# pybitbucket
A python interface to Atlassian Bitbucket API. Uses the OAuth grant type of client credentials.

# Use
1. Rename the samplesecretproperties.properties file to secreproperties.properties
2. Open your Bitbucket workspace and go to settings
3. Add an OAuth consumer with read access to everything you need. Check the "This is a private consumer" checkbox.
4. Copy the key and secret into the [atlassian_oauth] section
5. Copy the workplace UUID into the [atlassian] section
6. Run the project

## Pull Requests
1. If there is a default project key set, a list of pull requests will be retrieved for all repos for this project.
2. If there is a default deploy project repo set, a list of pull requests will be retrieved for deployments.


## Tracking deployments
If there is a default_deploy_repo value set in the [atlassian] section of the secretproperties file, it will look for 
commits to this repo to backtrack to original commits. 

