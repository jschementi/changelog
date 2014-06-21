# coding: utf-8

import os
import json
import re
import datetime
from collections import namedtuple
from contextlib import contextmanager

import github
import jenkins
from html_escape import html_escape
import email_send
from email_send import send_email

@contextmanager
def suppress(exception_type):
    try:
        yield
    except exception_type:
        pass

def load_config():
    config = {}
    github_api_url = None
    github_api_key = None
    jenkins_username = None
    jenkins_password = None
    jenkins_url = None
    sendgrid_username = None
    sendgrid_password = None
    email_subject_prefix = None

    try:
        with open(os.path.expanduser('~/.changelog.conf'), 'r') as config_file:
            config = json.loads(config_file.read())
    except IOError:
        prompt_for_config()
        load_config()
        return

    with suppress(KeyError):
        github_api_key = config['auth']['github']['api_key']
    with suppress(KeyError):
        github_api_url = config['auth']['github']['url']
    github.set_config(api_key=github_api_key, api_url=github_api_url)

    with suppress(KeyError):
        jenkins_username = config['auth']['jenkins']['username']
    with suppress(KeyError):
        jenkins_password = config['auth']['jenkins']['api_key']
    with suppress(KeyError):
        jenkins_url = config['auth']['jenkins']['url']
    jenkins.set_config(username=jenkins_username, password=jenkins_password, url=jenkins_url)

    with suppress(KeyError):
        sendgrid_username = config['auth']['sendgrid']['username']
    with suppress(KeyError):
        sendgrid_password = config['auth']['sendgrid']['password']
    with suppress(KeyError):
        email_subject_prefix = config['email']['subject_prefix']
    email_send.set_config(username=sendgrid_username, password=sendgrid_password, subject_prefix=email_subject_prefix)

def prompt_for_config():
    import getpass
    github_api_url = raw_input("GitHub API url (press enter for https://api.github.com): ") or 'https://api.github.com'
    github_api_key = getpass.getpass("GitHub API Key: ")
    jenkins_url = raw_input("Jenkins url (no trailing slash): ")
    jenkins_username = raw_input("Jenkins username: ")
    jenkins_password = getpass.getpass("Jenkins API Key: ")
    sendgrid_username = raw_input("Sendgrid username: ")
    sendgrid_password = getpass.getpass("Sendgrid password: ")
    email_subject_prefix = raw_input("Email subject prefix: ")
    with open(os.path.expanduser("~/.changelog.conf"), 'w') as config_file:
        config_data = {
            'auth': {
                'github': {
                    'url': github_api_url,
                    'api_key': github_api_key
                },
                'jenkins': {
                    'url': jenkins_url,
                    'username': jenkins_username,
                    'api_key': jenkins_password
                },
                'sendgrid': {
                    'username': sendgrid_username,
                    'password': sendgrid_password
                }
            },
            'email': {
                'subject_prefix': email_subject_prefix
            }
        }
        config_file.write(json.dumps(config_data, sort_keys=True, indent=4, separators=(',', ': ')))
        print "config written to %s" % os.path.expanduser("~/.changelog.conf")

class Commit(namedtuple('Commit', ['message', 'sha1', 'author', 'timestamp', 'changes'])):

    def get_associated_issues(self):
        return re.findall('#(\d+)', self.message)

    @classmethod
    def create_from_changeset_item(cls, changeset_item):
        return cls(message=changeset_item['comment'],
                   sha1=changeset_item['id'],
                   author=changeset_item['author']['fullName'],
                   timestamp=datetime.datetime.fromtimestamp(changeset_item['timestamp']),
                   changes=map(CommitChange.create_from_changeset_path, changeset_item['paths']))

class CommitChange(namedtuple('CommitChange', ['edit_type', 'filename'])):

    @classmethod
    def create_from_changeset_path(cls, changeset_path):
        return cls(edit_type=changeset_path['editType'], filename=changeset_path['file'])

def get_commit_index(commits):
    def index_commit_by_id(m, v):
        m[v.sha1] = v
        return m
    return reduce(index_commit_by_id, commits, {})

def get_commit_issue_index(commits):
    commit_to_issues = {}
    issues_to_commits = {}
    for commit in commits:
        issues = commit.get_associated_issues()
        commit_to_issues[commit.sha1] = issues
        for issue in issues:
            if not issues_to_commits.has_key(issue):
                issues_to_commits[issue] = []
            issues_to_commits[issue].append(commit.sha1)
    return {'issues': commit_to_issues, 'commits': issues_to_commits}

def get_issues_from_commits(commits, all_issues):
    commit_index = get_commit_index(commits)
    commit_issue_index = get_commit_issue_index(commits)
    all_issues_index = github.get_issue_index(all_issues)
    def each_issue_and_commits():
        for issue_id, commit_ids in commit_issue_index['commits'].iteritems():
            issue = all_issues_index.get(int(issue_id))
            if issue is None: continue
            issue_commits = [commit_index[commit_id] for commit_id in commit_ids]
            yield issue, issue_commits
    return each_issue_and_commits()

def get_commits_without_issues(commits):
    commit_index = get_commit_index(commits)
    commit_issue_index = get_commit_issue_index(commits)
    for commit_id, issues_id in commit_issue_index['issues'].iteritems():
        if len(issues_id) == 0:
            commit = commit_index.get(commit_id)
            if commit is None: continue
            yield commit

def get_changes_from_build(job_name, build_number):
    print job_name, build_number
    repo_url = jenkins.get_ci_job_repo_url(job_name)
    repo_owner, repo_name = github.get_repo_path(repo_url)
    ci_job = jenkins.get_ci_job(job_name)
    ci_build = jenkins.get_ci_build(job_name, build_number)
    changeset_items = ci_build['changeSet']['items']
    commits = map(Commit.create_from_changeset_item, changeset_items)
    all_issues = github.get_all_issues(repo_owner, repo_name)
    build_time = datetime.datetime.fromtimestamp(int(str(ci_build['timestamp'])[:10]))
    return {'job': ci_job,
            'build': ci_build,
            'job_name': ci_job['displayName'],
            'datetime': build_time,
            'repo_owner': repo_owner,
            'repo_name': repo_name,
            'issues': get_issues_from_commits(commits, all_issues),
            'commits': get_commits_without_issues(commits)}

def get_all_builds(job_names):
    for job_name in job_names:
        build_numbers = jenkins.get_build_numbers(job_name)
        for build_number in build_numbers:
            yield job_name, build_number

from operator import itemgetter

def get_changes_from_all_builds(job_names):
    return sorted([get_changes_from_build(name, number) for name, number in get_all_builds(job_names)],
                  key=itemgetter('datetime'), reverse=True)


from markdown import markdown

def render_commits(output, commits, repo_owner, repo_name, item_prefix='  - '):
    return len(map(lambda commit: render_commit(output, commit, repo_owner, repo_name, item_prefix), commits))

def render_commits_inline(output, commits, repo_owner, repo_name):
    def render_commit_inline(commit):
        short_commit_sha1 = commit.sha1[:8]
        commit_url = 'https://github.com/%s/%s/commit/%s' % (repo_owner, repo_name, commit.sha1)
        return "[%s](%s)" % (short_commit_sha1, commit_url)
    output.append('(commits: ' + ', '.join(map(render_commit_inline, commits)) + ')')
    return len(commits)

def render_commit(output, commit, repo_owner, repo_name, prefix='  - '):
    commit_title = html_escape(commit.message.split("\n")[0])
    short_commit_sha1 = commit.sha1[:8]
    commit_url = 'https://github.com/%s/%s/commit/%s' % (repo_owner, repo_name, commit.sha1)
    output.append("%s%s ([%s](%s))\n" % (prefix, commit_title, short_commit_sha1, commit_url))
    return 1

def render_issue(output, issue, repo_owner, repo_name, prefix='  - '):
    title = html_escape(issue['title'])
    number = issue['number']
    labels = [label['name'] for label in issue['labels']]
    # assignee = issue['assignee']['login']
    story_type = next((l for l in labels if l.startswith('(Type) ')), '').split("(Type) ")[-1]
    issue_url = 'https://github.com/%s/%s/issues/%d' % (repo_owner, repo_name, number)
    output.append("%s**[%s]** %s [#%d](%s)" % (prefix, story_type, title, number, issue_url))
    return 1

def render_build(display_name, build_datetime, prefix='### ', postfix='\n\n'):
    return "%s%s - %s%s" % (prefix, display_name, str(build_datetime), postfix)

def render_build_changes_as_markdown(build):
    repo_owner = build['repo_owner']
    repo_name = build['repo_name']
    build_issues = build['issues']
    build_commits = build['commits']
    output = []
    output.append(render_build(build['job_name'], build['datetime']))
    render_issues_len = 0
    for issue, commits in build_issues:
        render_issues_len += render_issue(output, issue, repo_owner, repo_name)
        output.append(' ')
        render_commits_inline(output, commits, repo_owner, repo_name)
        output.append("\n")
    commit_output = []
    render_commits_len = render_commits(commit_output, build_commits, repo_owner, repo_name)
    if render_issues_len > 0 and render_commits_len > 0:
        output.append("#### Other changes\n")
    output.extend(commit_output)
    if render_commits_len == 0 and render_issues_len == 0:
        return ''
    return ''.join(output)

def render_all_builds(job_names):
    changes_from_all_builds = get_changes_from_all_builds(job_names)
    return ''.join(map(render_build_changes_as_markdown, changes_from_all_builds))

def display_all_builds(job_names):
    print markdown(render_all_builds(job_names))

def notify_build(job_name, build_number, sender, email_addresses):
    build = get_changes_from_build(job_name, build_number)
    text = render_build_changes_as_markdown(build)
    html = markdown(text)
    if len(html) == 0:
        print "No HTML content, not sending email"
    else:
        send_email(build['job_name'], html, text, sender, email_addresses)
        print "Email sent from %s to %s" % (sender, ', '.join(email_addresses))

if __name__ == '__main__':

    import argparse
    import sys

    load_config()

    class Changelog(object):

        def __init__(self):
            parser = argparse.ArgumentParser(prog="changelog",
                                             description="GitHub issue + Jenkins changelog",
                                             usage='''python changelog.py <command> [<args>]

Commands:

  print_html    outputs a HTML changelog from all builds in a Jenkins job.
  notify        emails the list of provided addresses with a HTML changelog
                from a specific Jenkins build.


''')
            parser.add_argument('command', help="one of the commands listed above")
            args = parser.parse_args(sys.argv[1:2])
            if not hasattr(self, args.command):
                print "Unrecognized command \"%s\"" % args.command
                print
                parser.print_help()
                exit(1)
            getattr(self, args.command)()

        def print_html(self):
            parser = argparse.ArgumentParser(description='Prints changelog for entire job\'s history.')
            parser.add_argument('job_name', nargs='+')
            args = parser.parse_args(sys.argv[2:])
            display_all_builds(args.job_name)

        def notify(self):
            parser = argparse.ArgumentParser(
                description='Emails changelog for a specific job name and build number to a list of email addresses.')
            parser.add_argument('job_name')
            parser.add_argument('build_number')
            parser.add_argument("sender")
            parser.add_argument('email_address', nargs="+")
            args = parser.parse_args(sys.argv[2:])
            notify_build(args.job_name, args.build_number, args.sender, args.email_address)

    Changelog()

