# Changelog

A changelog generator for Jenkins jobs and GitHub issues.

For each Jenkins job, it looks in all the commit messages for links to GitHub
issues (Issue #1234, for example), and uses that issue's title as a changelog
entry. Each changelog entry is then appended with a list of associated commits.

All commits that do not reference issues are listed in an "Other changes"
section.

## Usage

Output a HTML changelog from any number of Jenkins builds:

    python changelog.py print_html job-abc job-def

Output a HTML changelog for a specific Jenkins build:

    python changelog.py notify job-abc 123 foo@bar.com

