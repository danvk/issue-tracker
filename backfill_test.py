#!/usr/bin/env python

import backfill
from nose.tools import eq_

import json

closed_issue = json.loads('''
{
  "closed_at": "2015-09-29T16:59:18Z", 
  "comments": 5, 
  "created_at": "2015-09-29T15:14:05Z", 
  "events": [
    {
      "created_at": "2015-09-29T16:59:18Z", 
      "event": "closed", 
      "id": 422119583 
    }
  ], 
  "id": 108891635, 
  "labels": [], 
  "locked": false, 
  "milestone": null, 
  "number": 668, 
  "state": "closed", 
  "title": "points not being connected", 
  "updated_at": "2015-09-29T16:59:18Z", 
  "url": "https://api.github.com/repos/danvk/dygraphs/issues/668"
}
''')

tortured_history_issue = json.loads('''
{
  "assignee": null, 
  "closed_at": "2014-10-20T23:53:09Z", 
  "comments": 2, 
  "created_at": "2014-10-20T22:44:07Z", 
  "events": [
    {
      "created_at": "2014-10-20T22:44:07Z", 
      "event": "labeled", 
      "id": 181211834, 
      "label": { "name": "imported" }
    }, 
    {
      "created_at": "2014-10-20T22:44:07Z", 
      "event": "labeled", 
      "id": 181211835, 
      "label": { "name": "enhancement" }
    }, 
    {
      "created_at": "2014-10-20T22:44:07Z", 
      "event": "labeled", 
      "id": 181211836, 
      "label": { "name": "1 star" }
    }, 
    {
      "created_at": "2014-10-20T22:44:07Z", 
      "event": "labeled", 
      "id": 181211837, 
      "label": { "name": "Component-Docs" }
    }, 
    {
      "created_at": "2014-10-20T23:09:19Z", 
      "event": "unlabeled", 
      "id": 181221151, 
      "label": { "name": "1 star" }
    }, 
    {
      "created_at": "2014-10-20T23:53:09Z", 
      "event": "closed", 
      "id": 181236697
    }
  ], 
  "id": 46334750, 
  "labels": [
    { "name": "Component-Docs" }, 
    { "name": "enhancement" }, 
    { "name": "imported" }
  ], 
  "locked": false, 
  "milestone": null, 
  "number": 427, 
  "state": "closed", 
  "title": "Annotations Documentation: Annotations not Visible", 
  "updated_at": "2014-10-20T23:53:09Z"
}
''')


def test_get_initial_labels():
    eq_(backfill.issue_events(closed_issue),
            [('2015-09-29T15:14:05Z', None, +1),
             ('2015-09-29T16:59:18Z', None, -1)])

    eq_(backfill.issue_events(tortured_history_issue),
            [('2014-10-20T22:44:07Z', None, +1),
             ('2014-10-20T22:44:07Z', 'imported', +1),
             ('2014-10-20T22:44:07Z', 'enhancement', +1),
             ('2014-10-20T22:44:07Z', '1 star', +1),
             ('2014-10-20T22:44:07Z', 'Component-Docs', +1),
             ('2014-10-20T23:09:19Z', '1 star', -1),
             ('2014-10-20T23:53:09Z', 'Component-Docs', -1),
             ('2014-10-20T23:53:09Z', 'enhancement', -1),
             ('2014-10-20T23:53:09Z', 'imported', -1),
             ('2014-10-20T23:53:09Z', None, -1)
            ])


def test_find_first_date():
    eq_(backfill.find_first_date(backfill.issue_events(closed_issue)),
        '2015-09-29T15:14:05Z')

    eq_(backfill.find_first_date(backfill.issue_events(tortured_history_issue)),
        '2014-10-20T22:44:07Z')


def test_next_date():
    next_date = backfill.next_date
    eq_(next_date('2015-09-29T15:14:05Z'), '2015-09-30')
    eq_(next_date('2014-10-20T22:44:07Z'), '2014-10-21')


def test_all_dates():
    all_dates = backfill.all_dates
    eq_(all_dates('2015-09-29', '2015-10-03 12:34:56'),
        ['2015-09-29', '2015-09-30', '2015-10-01', '2015-10-02', '2015-10-03'])
