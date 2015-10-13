#!/usr/bin/env python
# coding=utf-8

import dateutil.parser
import glob
import os
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta

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
        issues.append(issue_data)
    return issues


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


def issue_events(issue):
    """Returns a list of (time, label or None, delta) events.
    
    None = all issues
    delta +1 = add 1 to the count of open issues
    delta -1 = drop 1 from the count of open issues
    """
    labels = set()  # all issues start without labels.
    is_open = True

    events = []
    events.append((issue['created_at'], None, +1))

    # XXX do open pull requests count toward the total # of open issues?
    if 'pull_request' in issue:
        return []

    raw_events = issue['events']
    if needs_synthetic_close(issue):
        raw_events = raw_events + [{
            'event': 'closed',
            'created_at': issue['closed_at']
            }]

    for event in raw_events:
        t = event['event']
        time = event['created_at']
        if t == 'labeled':
            label = event['label']['name']
            label = LABEL_RENAMES.get(label, label)
            labels.add(label)
            if is_open:
                events.append((time, label, +1))
        elif t == 'unlabeled':
            label = event['label']['name']
            label = LABEL_RENAMES.get(label, label)
            labels.remove(label)
            if is_open:
                events.append((time, label, -1))
        elif t == 'closed':
            is_open = False
            for label in reversed([None] + list(labels)):
                events.append((time, label, -1))
        elif t == 'reopened':
            is_open = True
            for label in [None] + list(labels):
                events.append((time, label, +1))

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


if __name__ == '__main__':
    owner, repo_name = sys.argv[1:]
    CACHE_DIR += '-%s-%s' % (owner, repo_name)

    if not os.path.exists(CACHE_DIR):
        os.mkdir(CACHE_DIR)
    g = tracker.get_github()

    try:
        repo = g.get_user(owner).get_repo(repo_name)
        issues = fetch_all_issues(repo)
    except github.GithubException as e:
        if e.status == 403 and 'rate limit' in e.data['message']:
            summarize_rate_limit(g)
            raise e

    # issues = fetch_all_issues_from_cache()
    sys.stderr.write('Loaded %d issues\n' % len(issues))

    all_events = flatten((issue_events(issue) for issue in issues))
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

    # Chunk into reasonably-sized requests
    objs = [
        {'delete': 'open_issues'},
        {'open_issues': open_issues},
        {'delete': 'by_label'}
    ] + [{'by_label': {label: by_label[label]}} for label in labels]

    for i, obj in enumerate(objs):
        json.dump(obj, open('%s/backfill%04d.json' % (CACHE_DIR, i), 'w'))

    print '''
Success!

Now run:

    for file in %s/backfill*.json; do echo $file; curl --data @$file -H "Content-Type: application/json" http://github-issue-tracker.herokuapp.com/%s/%s/backfill; done

''' % (CACHE_DIR, owner, repo_name)

