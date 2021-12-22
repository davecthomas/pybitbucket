import re


def find_jira_id(search_string):
    pattern = re.compile(r"([0-Z]+\-\d+)")
    match = pattern.search(search_string)
    if match is not None:
        return match.group(1)
    else:
        return None
