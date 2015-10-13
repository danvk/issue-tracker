#!/usr/bin/env python
# coding=utf-8
"""Backfill counts for the GitHub Issue Tracker.

Usage:
  backfill.py <user> <repo> [--all | --issues | --pulls | --stars | --labels ]

Options:
  -h --help    Show this screen.
  --version    Show version.
  --all        Backfill all counts. [default: true]
  --issues     Backfill only open issues.
  --pulls      Backfill only open pull requests.
  --stars      Backfill only stargazer counts.
  --labels     Backfill only per-label open issue counts.
"""

import glob
import os
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta

import dateutil.parser
from docopt import docopt

import github
import tracker

CACHE_DIR = 'issue-tracker-backfill'

# GitHub doesn't track label renames as events in the issue.
# If you've renamed labels, you need to let the backfiller know.
# For example, if you renamed 'test' to 'tests', use this:
# LABEL_RENAMES = {
#     'test': 'tests'
# }

LABEL_RENAMES = {}

def fetch_full_issue(issue):
    """Fills out the events field for an Issue or Pull Request."""
    print 'Fetching issue %d...' % issue.number
    issue_json = issue.raw_data
    issue_json['events'] = [event.raw_data for event in issue.get_events()]
    for event in issue_json['events']:
        del event['issue']
    return issue_json


def fetch_issue_cached(repo, issue_number):
    cache_file = os.path.join(CACHE_DIR, '%d.json' % issue_number)
    if os.path.exists(cache_file):
        return json.load(open(cache_file))

    issue_json = fetch_issue(repo, issue_number)
    json.dump(issue_json, open(cache_file, 'w'), indent=2, sort_keys=True)
    return issue_json


def fetch_all_issues(repo):
    issues = []
    for issue in repo.get_issues(state='all'):
        cache_file = os.path.join(CACHE_DIR, '%d.json' % issue.number)
        if os.path.exists(cache_file):
            issue_data = json.load(open(cache_file))
        else:
            issue_data = fetch_full_issue(issue)
            json.dump(issue_data, open(cache_file, 'w'), indent=2, sort_keys=True)
        if 'pull_request' not in issue_data:
            issues.append(issue_data)
    return issues


def fetch_all_pulls(repo):
    '''Fetch all open/closed PRs for a repo.

    This returns the issue views of the PRs, which include events (unlike the PR views).
    '''
    prs = []
    for pr in repo.get_pulls(state='all'):
        cache_file = os.path.join(CACHE_DIR, '%d.json' % pr.number)
        if os.path.exists(cache_file):
            pr_data = json.load(open(cache_file))
        else:
            issue = repo.get_issue(pr.number)
            pr_data = fetch_full_issue(issue)
            json.dump(pr_data, open(cache_file, 'w'), indent=2, sort_keys=True)
        prs.append(pr_data)
    return prs


def fetch_all_issues_from_cache():
    return [json.load(open(path)) for path in glob.glob(CACHE_DIR + '/*.json')]


def needs_synthetic_close(issue):
    '''Some older issues are closed, but lack a "closed" event.'''
    is_open = True
    for event in issue['events']:
        t = event['event']
        if t == 'closed':
            is_open = False
        elif t == 'reopened':
            is_open = True
    return is_open and issue['state'] == 'closed'


def issue_events(issue, track_labels=True):
    """Returns a list of (time, label or None, delta) events.
    
    None = all issues
    delta +1 = add 1 to the count of open issues
    delta -1 = drop 1 from the count of open issues
    """
    labels = set()  # all issues start without labels.
    is_open = True

    events = []
    events.append((issue['created_at'], None, +1))

    raw_events = issue['events']
    if needs_synthetic_close(issue):
        raw_events = raw_events + [{
            'event': 'closed',
            'created_at': issue['closed_at']
            }]

    for event in raw_events:
        t = event['event']
        time = event['created_at']
        if t == 'labeled' and track_labels:
            label = event['label']['name']
            label = LABEL_RENAMES.get(label, label)
            labels.add(label)
            if is_open:
                events.append((time, label, +1))
        elif t == 'unlabeled' and track_labels:
            label = event['label']['name']
            label = LABEL_RENAMES.get(label, label)
            labels.remove(label)
            if is_open:
                events.append((time, label, -1))
        elif t == 'closed':
            is_open = False
            events.append((time, None, -1))
            if track_labels:
                for label in reversed(list(labels)):
                    events.append((time, label, -1))
        elif t == 'reopened':
            is_open = True
            events.append((time, None, +1))
            for label in list(labels):
                events.append((time, label, +1))

    if track_labels:
        github_labels = {label['name'] for label in issue['labels']}
        if labels != github_labels:
            print 'Label mismatch for issue %d' % issue['number']
            print '  Computed %s' % labels
            print '  GitHub says %s' % github_labels
            print 'You may need to fill out the LABEL_RENAMES variable\n'
    return events


def find_first_date(issue_events):
    return min(date for date, label, delta in issue_events)


def flatten(list_of_lists):
    return [item for sublist in list_of_lists for item in sublist]


def next_date(iso_str):
    '''Given an event during a day, return the date (YYYY-MM-DD) of the next day.'''
    dt = dateutil.parser.parse(iso_str)
    return (dt.date() + timedelta(days=1)).strftime('%Y-%m-%d')


def all_dates(start_str, last_str=None):
    '''Return a list of dates from start to today.'''
    d = dateutil.parser.parse(start_str)
    if not last_str:
        last = datetime.utcnow()
    else:
        last = dateutil.parser.parse(last_str)
    dates = []
    while d.date() <= last.date():
        dates.append(d.strftime('%Y-%m-%d'))
        d = d + timedelta(days=1)
    return dates


def summarize_rate_limit(g):
    sys.stderr.write("Oh no, you've run out of GitHub API quota!\n")
    sys.stderr.write("Please wait for it to reset; your backfill will resume where it left off.\n")
    rate = g.get_rate_limit().rate

    if rate.remaining == 0:
        sys.stderr.write('Your quota will reset in %s\n' % (rate.reset - datetime.utcnow()))

    sys.stderr.write('\n')


def backfill_core(issues, backfill_labels=False):
    '''Shared backfilling logic between issues and pull requests.'''
    all_events = flatten((issue_events(issue, track_labels=backfill_labels)
                         for issue in issues))
    first_date = find_first_date(all_events)
    dates = all_dates(first_date)

    label_to_deltas = defaultdict(lambda: {date: 0 for date in dates})
    for time_str, label, delta in all_events:
        yyyy_mm_dd = next_date(time_str)
        label_to_deltas[label][yyyy_mm_dd] += delta
    labels = label_to_deltas.keys()

    label_to_count = {label: 0 for label in labels}
    by_label = defaultdict(list)
    for date in dates:
        for label in labels:
            label_to_count[label] += label_to_deltas[label][date]
            by_label[label].append((date, label_to_count[label]))

    open_issues = by_label[None]
    del by_label[None]

    return open_issues, by_label


def backfill_issues(g, owner, repo_name, backfill_labels=False):
    repo = g.get_user(owner).get_repo(repo_name)
    issues = fetch_all_issues(repo)

    sys.stderr.write('Loaded %d issues\n' % len(issues))
    return backfill_core(issues, backfill_labels=backfill_labels)


def backfill_pulls(g, owner, repo_name):
    repo = g.get_user(owner).get_repo(repo_name)
    pulls = fetch_all_pulls(repo)
    sys.stderr.write('Loaded %d pull requests\n' % len(pulls))
    return backfill_core(pulls, backfill_labels=False)[0]


if __name__ == '__main__':
    arguments = docopt(__doc__, version='Backfiller 0.1')
    owner = arguments['<user>']
    repo_name = arguments['<repo>']

    CACHE_DIR += '-%s-%s' % (owner, repo_name)

    if not os.path.exists(CACHE_DIR):
        os.mkdir(CACHE_DIR)
    g = tracker.get_github()

    open_issues = []
    open_pulls = []
    by_label = {}
    stargazers = []

    do_all = arguments['--all']
    do_issues = arguments['--issues'] or do_all
    do_labels = arguments['--labels'] or do_all
    do_stars = arguments['--stars'] or do_all
    do_pulls = arguments['--pulls'] or do_all

    try:
        if do_issues or do_labels:
            open_issues, by_label = backfill_issues(g, owner, repo_name, backfill_labels=(do_all or do_labels))
        if do_stars:
            sys.stderr.write('\nStargazer backfilling is not implemented yet.\n\n')
            pass
        if do_pulls:
            open_pulls = backfill_pulls(g, owner, repo_name)

    except github.GithubException as e:
        if e.status == 403 and 'rate limit' in e.data['message']:
            summarize_rate_limit(g)
            raise e

    # Chunk into reasonably-sized requests
    objs = []
    if do_issues:
        objs.extend([
            {'delete': 'open_issues'},
            {'open_issues': open_issues}
        ])
    if do_labels:
        objs.append({'delete': 'by_label'})
        objs.extend([{'by_label': {label: by_label[label]}} for label in labels])
    if do_pulls:
        objs.extend([
            {'delete': 'open_pulls'},
            {'open_pulls': open_pulls}
        ])
    if do_stars:
        pass

    for path in glob.glob('%s/backfill????.json' % CACHE_DIR):
        os.remove(path)
    for i, obj in enumerate(objs):
        json.dump(obj, open('%s/backfill%04d.json' % (CACHE_DIR, i), 'w'))

    print '''
Success!

Now run:

    for file in %s/backfill*.json; do echo $file; curl --data @$file -H "Content-Type: application/json" http://github-issue-tracker.herokuapp.com/%s/%s/backfill; done

''' % (CACHE_DIR, owner, repo_name)

