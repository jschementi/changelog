import os
import requests

github_auth = (None, 'x-oauth-basic')
github_api_url = "https://api.github.com"

def set_config(api_key, api_url):
    global github_auth
    global github_api_url
    if api_key is not None:
        github_auth = (api_key, github_auth[1])
    if api_url is not None:
        github_api_url = api_url

all_issues_url = '%s/repos/%s/%s/issues?per_page=100&state=all'
all_commits_url = '%s/repos/%s/%s/commits?per_page=100'
all_pull_requests_url = '%s/repos/%s/%s/pulls?per_page=100&state=all'

all_issues_cache = {}

def get_paged_data(url, auth=None):
    data = []
    current_url = url
    headers = {
        'accept': 'application/vnd.github.v3+json',
        'user-agent': 'https://github.com/jschementi/changelog'
    }
    while True:
        r = requests.get(current_url, auth=auth, headers=headers)
        r.raise_for_status()
        data.extend(r.json())
        if not ('next' in r.links):
            break
        current_url = r.links['next']['url']
    return data

def get_all_issues(owner, repo):
    global all_issues_cache
    cache_key = "%s/%s" % (owner, repo)
    if not cache_key in all_issues_cache:
        all_issues = get_paged_data(all_issues_url % (github_api_url, owner, repo), auth=github_auth)
        all_issues_cache[cache_key] = all_issues
    return all_issues_cache[cache_key]

def get_issue_index(issues):
    def index_issue_by_number(m, v):
        m[v['number']] = v
        return m
    return reduce(index_issue_by_number, issues, {})

def get_repo_path(repo_url):
    return os.path.splitext(repo_url)[0].split('github.com')[1][1:].split('/')

