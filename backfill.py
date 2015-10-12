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

OWNER = 'danvk'
REPO = 'dygraphs'

CACHE_DIR = 'issue-tracker-backfill'


class Stargazer(github.GithubObject.NonCompletableGithubObject):
    @property
    def starred_at(self):
        """
        :type: datetime.datetime
        """
        return self._starred_at.value

    @property
    def user(self):
        """
        :type: :class:`github.NamedUser`
        """
        return self._user.value

    def _initAttributes(self):
        self._starred_at = github.GithubObject.NotSet
        self._user = github.GithubObject.NotSet
        self._url = github.GithubObject.NotSet

    def _useAttributes(self, attributes):
        if 'starred_at' in attributes:
            self._starred_at = self._makeDatetimeAttribute(attributes['starred_at'])
        if 'user' in attributes:
            self._user = self._makeClassAttribute(github.NamedUser.NamedUser, attributes['user'])


def get_stargazers(repo):
    return github.PaginatedList.PaginatedList(
        Stargazer,
        repo._requester,
        repo.url + "/stargazers",
        None,
        # XXX: pygithub doesn't support this:
        headers={
            'Accept': 'application/vnd.github.v3.star+json'
        }
    )


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
            labels.add(label)
            if is_open:
                events.append((time, label, +1))
        elif t == 'unlabeled':
            label = event['label']['name']
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


if __name__ == '__main__':
    if not os.path.exists(CACHE_DIR):
        os.mkdir(CACHE_DIR)
    g = tracker.get_github()

    repo = g.get_user(OWNER).get_repo(REPO)

    sys.stderr.write('Fetching %d stargazers...\n' % repo.stargazers_count)
    date_to_gazer_delta = defaultdict(int)
    for gazer in get_stargazers(repo):
        dt = gazer.starred_at
        d = (dt.date() + timedelta(days=1)).strftime('%Y-%m-%d')
        date_to_gazer_delta[d] += 1

    # issues = fetch_all_issues(repo)
    issues = fetch_all_issues_from_cache()
    sys.stderr.write('Loaded %d issues\n' % len(issues))

    all_events = flatten((issue_events(issue) for issue in issues))
    first_date = find_first_date(all_events)
    dates = all_dates(first_date)

    label_to_deltas = defaultdict(lambda: {date: 0 for date in dates})
    for time_str, label, delta in all_events:
        yyyy_mm_dd = next_date(time_str)
        label_to_deltas[label][yyyy_mm_dd] += delta
    labels = label_to_deltas.keys()

    # label_to_count = {label: 0 for label in labels}
    # print '\t'.join(['Date'] + [x if x else 'Unlabeled' for x in labels]).encode('utf8')
    # for date in dates:
    #     for label in labels:
    #         label_to_count[label] += label_to_deltas[label][date]
    #     print '\t'.join([date] + [str(label_to_count[label]) for label in labels])

    stargazers = 0
    for date in all_dates(min(date_to_gazer_delta.keys())):
        stargazers += date_to_gazer_delta[date]
        print '%s\t%d' % (date, stargazers)


    # Possible events:
    # ([u'referenced', u'subscribed', u'unlabeled', u'reopened', u'assigned', u'renamed', u'labeled', u'unassigned', u'milestoned', u'head_ref_deleted', u'closed', u'mentioned', u'head_ref_restored', u'demilestoned', u'merged'])
    #
    # for issue in issues:
    #     labels = set(label['name'] for label in issue['labels'])
    #     # this is tricky since the current state is the end state.
    #     # we need to play the events in reverse
    #     for event in issue['events']:
    #         events.add(event['event'])
    #
    # print events

