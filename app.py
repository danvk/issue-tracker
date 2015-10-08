#!/usr/bin/env python

from flask import Flask, jsonify, render_template

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
    return render_template('index.html', owner=owner, repo=repo, stargazers=stargazers, open_issues=open_issues, open_pulls=open_pulls, by_label=by_label)


@app.route('/update', methods=['POST'])
def update():
    observe_and_add(OWNER, REPO)
    return 'OK'


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
