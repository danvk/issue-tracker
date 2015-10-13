#!/usr/bin/env python
'''This is the Heroku scheduler task.'''

import app
import db


if __name__ == '__main__':
    for tracked_repo in db.tracked_repos():
        owner = tracked_repo.owner
        repo = tracked_repo.repo
        app.observe_and_add(owner, repo)
