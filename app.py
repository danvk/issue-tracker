#!/usr/bin/env python

from flask import Flask, jsonify, render_template

import tracker

OWNER = 'danvk'
REPO = 'dygraphs'


def format_date_column(series):
    '''Converts the first column of series to an ISO-8601 string'''
    out = []
    for row in series:
        out.append([row[0].strftime('%Y-%m-%d %H:%M:%SZ')] + list(row[1:]))
    return out


app = Flask(__name__)
@app.route('/')
def hello():
    series = tracker.get_stats_series(OWNER, REPO)
    series = format_date_column(series)
    return render_template('index.html', series=series)


@app.route('/update', methods=['POST'])
def update():
    tracker.observe_and_add(OWNER, REPO)
    return 'OK'


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
