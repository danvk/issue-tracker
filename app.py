#!/usr/bin/env python

from collections import defaultdict

from flask import Flask, jsonify, render_template, request

import db
import tracker

OWNER = 'danvk'
REPO = 'dygraphs'


def format_date_column(series):
    '''Converts the first column of series to an ISO-8601 string'''
    out = []
    for row in series:
        out.append([row[0].strftime('%Y-%m-%d %H:%M:%SZ')] + list(row[1:]))
    return out


def get_current_label_counts(by_label):
    '''Returns an ordered list of (label, count) tuples.'''
    pairs = zip(by_label[0][1:], by_label[-1][1:])
    pairs.sort(key=lambda pair: -pair[1])
    return pairs


def observe_and_add(owner, repo):
    stats = tracker.fetch_stats_from_github(owner, repo)
    db.store_result(owner, repo, stats)


app = Flask(__name__)
@app.route('/')
def hello():
    return stats(OWNER, REPO)


@app.route('/<owner>/<repo>')
def stats(owner, repo):
    stargazers, open_issues, open_pulls, by_label = db.get_stats_series(owner, repo)
    stargazers = format_date_column(stargazers)
    open_issues = format_date_column(open_issues)
    open_pulls = format_date_column(open_pulls)
    by_label = [by_label[0]] + format_date_column(by_label[1:])

    current_label_counts = get_current_label_counts(by_label)

    return render_template('index.html',
            owner=owner,
            repo=repo,
            stargazers=stargazers,
            open_issues=open_issues,
            open_pulls=open_pulls,
            by_label=by_label,
            current_label_counts=current_label_counts)


@app.route('/<owner>/<repo>/json')
def stats_json(owner, repo):
    stargazers, open_issues, open_pulls, by_label = db.get_stats_series(owner, repo)
    stargazers = format_date_column(stargazers)
    open_issues = format_date_column(open_issues)
    open_pulls = format_date_column(open_pulls)
    by_label = [by_label[0]] + format_date_column(by_label[1:])

    by_label_dict = defaultdict(list)
    for row in by_label[1:]:  # drop header row
        for idx, col in enumerate(row):
            if idx == 0: continue  # drop date column
            label = by_label[0][idx]
            if label == '(unlabeled)':
                label = ''
            by_label_dict[label].append((row[0], col))

    return jsonify({
        'owner': owner,
        'repo': repo,
        'stargazers': stargazers,
        'open_issues': open_issues,
        'open_pulls': open_pulls,
        'by_label': by_label_dict
    })


@app.route('/<owner>/<repo>/backfill', methods=['POST'])
def backfill(owner, repo):
    db.store_backfill(owner, repo, request.get_json())
    return 'OK'


@app.route('/<owner>/<repo>/add', methods=['POST'])
def add_repo(owner, repo):
    db.add_repo(owner, repo, '')
    return 'OK'


@app.route('/update', methods=['POST'])
def update():
    observe_and_add(OWNER, REPO)
    return 'OK'


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
