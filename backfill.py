#!/usr/bin/env python
# coding=utf-8

import os
import json
from collections import defaultdict

import tracker

OWNER = 'danvk'
REPO = 'dygraphs'

CACHE_DIR = 'issue-tracker-backfill'


def fetch_full_issue(issue):
    print 'Fetching issue %d...' % issue.number
    issue_json = issue.raw_data
    issue_json['events'] = [event.raw_data for event in issue.get_events()]
    for event in issue_json:
        del issue_json['events']['issue']
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
    for event in issue['events']:
        t = event['event']
        time = event['created_at']
        if t == 'labeled':
            label = event['label']['name']
            labels.add(label)
            if is_open:
                events.append((time, label, +1))
        elif t == 'unlabeled':
            label = event['label']['name']
            labels.remove(label)
            if is_open:
                events.append((time, label, -1))
        elif t == 'closed':
            for label in reversed([None] + list(labels)):
                events.append((time, label, -1))
        elif t == 'reopened':
            for label in [None] + list(labels):
                events.append((time, label, +1))
    return events


if __name__ == '__main__':
    if not os.path.exists(CACHE_DIR):
        os.mkdir(CACHE_DIR)
    g = tracker.get_github()

    repo = g.get_user(OWNER).get_repo(REPO)
    issues = fetch_all_issues(repo)

    # TODO:
    # - find the first date
    # - build an empty array of all labels and issue counts by date

    issue_events = []  # (timestamp, ∆ issues)
    label_events = defaultdict(list)  # label -> (timestamp, ∆ issues)

    # Possible events:
    # ([u'referenced', u'subscribed', u'unlabeled', u'reopened', u'assigned', u'renamed', u'labeled', u'unassigned', u'milestoned', u'head_ref_deleted', u'closed', u'mentioned', u'head_ref_restored', u'demilestoned', u'merged'])


    for issue in issues:
        labels = set(label['name'] for label in issue['labels'])
        # this is tricky since the current state is the end state.
        # we need to play the events in reverse
        for event in issue['events']:
            events.add(event['event'])

    print events

