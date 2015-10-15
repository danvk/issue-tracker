#!/usr/bin/env python

from collections import defaultdict
import json
import os

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask.ext.github import GitHub
import requests

import db
import tracker

OWNER = 'danvk'
REPO = 'dygraphs'

app = Flask(__name__)

DEBUG = os.environ.get('DEBUG')
app.secret_key = os.environ.get('SECRET_KEY')
app.config['GITHUB_CLIENT_ID'] = os.environ.get('CLIENT_ID')
app.config['GITHUB_CLIENT_SECRET'] = os.environ.get('CLIENT_SECRET')

github = GitHub(app)


def format_date_column(series):
    '''Converts the first column of series to an ISO-8601 string'''
    out = []
    for row in series:
        out.append([row[0].strftime('%Y-%m-%dT%H:%M:%SZ')] + list(row[1:]))
    return out


def get_current_label_counts(by_label):
    '''Returns an ordered list of (label, count) tuples.'''
    pairs = zip(by_label[0][1:], by_label[-1][1:])
    pairs.sort(key=lambda pair: -pair[1])
    return pairs


def observe_and_add(owner, repo):
    stats = tracker.fetch_stats_from_github(owner, repo)
    db.store_result(owner, repo, stats)




@app.route('/')
def index():
    return stats(OWNER, REPO)


@app.route('/<owner>/<repo>')
def stats(owner, repo):
    login = g.user.login if g.user else None

    if not db.is_repo_tracked(owner, repo):
        return render_template('new_repo.html', login=login, owner=owner, repo=repo)

    stargazers, open_issues, open_pulls, by_label = db.get_stats_series(owner, repo, include_labels=False)
    stargazers = format_date_column(stargazers)
    open_issues = format_date_column(open_issues)
    open_pulls = format_date_column(open_pulls)

    return render_template('index.html',
            login=login,
            owner=owner,
            repo=repo,
            stargazers=stargazers,
            open_issues=open_issues,
            open_pulls=open_pulls)


@app.route('/<owner>/<repo>/json')
def stats_json(owner, repo):
    stargazers, open_issues, open_pulls, by_label = (
        db.get_stats_series(owner, repo, include_labels=request.args.get('include_labels')))
    stargazers = format_date_column(stargazers)
    open_issues = format_date_column(open_issues)
    open_pulls = format_date_column(open_pulls)
    by_label = [by_label[0]] + format_date_column(by_label[1:])

    return jsonify({
        'owner': owner,
        'repo': repo,
        'stargazers': stargazers,
        'open_issues': open_issues,
        'open_pulls': open_pulls,
        'by_label': by_label
    })


@app.route('/<owner>/<repo>/backfill', methods=['POST'])
def backfill(owner, repo):
    db.store_backfill(owner, repo, request.get_json())
    return 'OK'


@app.route('/<owner>/<repo>/add', methods=['POST'])
def add_repo(owner, repo):
    if not g.user:
        flash('You must be signed in to force an update!', 'error')
        return stats(owner, repo)
    if not tracker.can_user_push_to_repo(g.user.token, owner, repo):
        flash('You must have push rights to a repo to update its charts.', 'error')
        return stats(owner, repo)
    db.add_repo(owner, repo, g.user.token)
    flash('This repo is now being tracked', 'success')
    return redirect(url_for('stats', owner=owner, repo=repo))


@app.route('/<owner>/<repo>/update', methods=['POST'])
def update(owner, repo):
    if not g.user:
        flash('You must be signed in to force an update!', 'error')
        return stats(owner, repo)
    if not tracker.can_user_push_to_repo(g.user.token, owner, repo):
        flash('You must have push rights to a repo to update its charts.', 'error')
        return stats(owner, repo)
    observe_and_add(owner, repo)
    flash('A new data point has been added to all charts.', 'success')
    return redirect(url_for('stats', owner=owner, repo=repo))


# OAuth stuff


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = db.get_user(session['user_id'])


@github.access_token_getter
def token_getter():
    user = g.user
    if user is not None:
        return user.token


@app.route('/login')
def login():
    if session.get('user_id', None) is None:
        return github.authorize()
    else:
        return 'Already signed in'


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


@app.route('/callback')
@github.authorized_handler
def authorized(oauth_token):
    next_url = request.args.get('next') or url_for('index')
    if oauth_token is None:
        flash("Authorization failed.")
        return redirect(next_url)

    login = tracker.user_for_token(oauth_token)
    user_id = db.add_user(login, oauth_token)
    session['user_id'] = user_id
    return redirect(next_url)



if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=DEBUG)
