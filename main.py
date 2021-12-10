from pybitbucket.bitbucket import Bitbucket

config = {
    "version": 1.0,
    "properties": "secretproperties.properties"}
print(f'pybitbucket ', {config["version"]})
bb = Bitbucket(settings=config)

