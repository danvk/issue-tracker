#!/usr/bin/env python

from github import Github
import sqlite3

from datetime import datetime

OWNER = 'danvk'
REPO = 'dygraphs'

def maybe_create_table(cursor):
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Counts(
        id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        owner STRING,
        repo STRING,
        time DATETIME DEFAULT CURRENT_TIMESTAMP,
        stargazers INTEGER,
        open_issues INTEGER,
        open_pulls INTEGER
        )
    ''')


def store_result(cursor, owner, repo, stars, open_issues, open_pulls):
    cursor.execute('''
    INSERT INTO Counts(owner, repo, stargazers, open_issues, open_pulls)
    VALUES(?, ?, ?, ?, ?)
    ''', (owner, repo, stars, open_issues, open_pulls))


def fetch_counts(cursor, owner, repo):
    cursor.execute('''
      SELECT time, stargazers, open_issues, open_pulls
      FROM Counts
      WHERE owner=? AND repo=?
      ORDER BY time
    ''', (owner, repo))
    return cursor.fetchall()


def fetch_stats_from_github(g, owner, repo):
    repo = g.get_user(owner).get_repo(repo)

    stars = repo.stargazers_count
    open_issues = repo.open_issues_count
    open_pulls = len(list(repo.get_pulls()))
    return stars, open_issues, open_pulls


def connect_to_db():
    conn = sqlite3.connect('issue-tracker.db')
    cur = conn.cursor()
    return conn, cur


def observe_and_add(owner, repo):
    conn, cur = connect_to_db()
    g = Github()
    maybe_create_table(cur)
    stars, open_issues, open_pulls = fetch_stats_from_github(g, owner, repo)
    store_result(cur, owner, repo, stars, open_issues, open_pulls)
    conn.commit()


def get_stats_series(owner, repo):
    conn, cur = connect_to_db()
    series = fetch_counts(cur, owner, repo)
    return series


if __name__ == '__main__':
    observe_and_add(OWNER, REPO)
