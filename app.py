#!/usr/bin/env python

from flask import Flask, jsonify, render_template

import tracker

OWNER = 'danvk'
REPO = 'dygraphs'

app = Flask(__name__)
@app.route('/')
def hello():
    series = tracker.get_stats_series(OWNER, REPO)
    return render_template('index.html', series=series)


@app.route('/update', methods=['POST'])
def update():
    tracker.observe_and_add(OWNER, REPO)
    return 'OK'


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
