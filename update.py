#!/usr/bin/env python
'''This is the Heroku scheduler task.'''

import tracker

OWNER = 'danvk'
REPO = 'dygraphs'

tracker.observe_and_add(OWNER, REPO)
