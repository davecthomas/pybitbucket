from src.pybitbucket.bitbucket import Bitbucket

config = {
    "secret-properties": "secretproperties.properties",
    "properties": "properties.properties"}

bb = Bitbucket(settings=config)

