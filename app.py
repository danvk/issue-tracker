#!/usr/bin/env python

from github import Github
import sqlite3

from datetime import datetime

def create_table(cursor):
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


def fetch_stats(g, owner, repo):
    repo = g.get_user("danvk").get_repo("dygraphs")

    stars = repo.stargazers_count
    open_issues = repo.open_issues_count
    open_pulls = len(list(repo.get_pulls()))
    return stars, open_issues, open_pulls


if __name__ == '__main__':
    conn = sqlite3.connect('issue-tracker.db')
    cur = conn.cursor()
    g = Github()
    create_table(cur)
    stars, open_issues, open_pulls = fetch_stats(g, 'danvk', 'dygraphs')
    store_result(cur, 'danvk', 'dygraphs', stars, open_issues, open_pulls)
    conn.commit()

