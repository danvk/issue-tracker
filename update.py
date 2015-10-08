#!/usr/bin/env python
'''This is the Heroku scheduler task.'''

import app

REPOS = [
    'danvk/dygraphs',
    'hammerlab/cycledash',
    'hammerlab/pileup.js'
]

if __name__ == '__main__':
    for owner_repo in REPOS:
        owner, repo = owner_repo.split('/')
        app.observe_and_add(owner, repo)
