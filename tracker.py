#!/usr/bin/env python

from github import Github

import os
import time
from collections import namedtuple, defaultdict

OWNER = 'danvk'
REPO = 'dygraphs'


# Records statistics about the repo at a particular instant in time.
RepoStats = namedtuple('RepoStats',
        [
            'stargazers',
            'open_issues',
            'open_pulls',
            'label_to_count'
        ])


def get_github():
    token = os.environ.get('GITHUB_TOKEN')
    if not token and os.path.exists('.github-token'):
        token = open('.github-token').read().strip()
    if token:
        return Github(token)
    else:
        return Github()


def fetch_stats_from_github(owner, repo):
    start_secs = time.time()
    g = get_github()
    repo = g.get_user(owner).get_repo(repo)

    stargazers = repo.stargazers_count
    open_issues = repo.open_issues_count
    open_pulls = len(list(repo.get_pulls()))

    label_to_count = defaultdict(int)
    for issue in repo.get_issues():
        labels = [label.name for label in issue.labels] or ['']  # empty label = unlabeled
        for label in labels:
            label_to_count[label] += 1

    end_secs = time.time()
    print 'Fetched %d GitHub issues in %f secs' % (open_issues, end_secs - start_secs)

    return RepoStats(stargazers=stargazers,
                     open_issues=open_issues,
                     open_pulls=open_pulls,
                     label_to_count=label_to_count)


def user_for_token(token):
    g = Github(token)
    return g.get_user().login


def can_user_push_to_repo(token, owner, repo_name):
    g = Github(token)
    repo = g.get_user(owner).get_repo(repo_name)
    return repo.permissions.push


if __name__ == '__main__':
    print fetch_stats_from_github(OWNER, REPO)
