#!/usr/bin/env python

from datetime import datetime
from github import Github
g = Github()
repo = g.get_user("danvk").get_repo("dygraphs")

stars = repo.stargazers_count
open_issues = repo.open_issues_count
open_pulls = len(list(repo.get_pulls()))

now_iso8601 = datetime.utcnow().isoformat() + 'Z'

print '\t'.join(str(x) for x in [now_iso8601, stars, open_issues, open_pulls])
