from src.pybitbucket.bitbucket import Bitbucket

config = {
    "secret-properties": "secretproperties.properties",
    "properties": "properties.properties"}

bb = Bitbucket(settings=config)

# workspace = bb.workspace
prs_df = bb.df_prs
commits_df = bb.df_commits
prs_list = prs_df["pr_id"].unique().tolist().sort()
print(f"PRs: {prs_list}")
