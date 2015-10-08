#!/usr/bin/env python

from github import Github

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Sequence, DateTime
from sqlalchemy.orm import sessionmaker

from datetime import datetime

OWNER = 'danvk'
REPO = 'dygraphs'

engine = create_engine('sqlite:///issue-tracker.db', echo=True)
Session = sessionmaker(bind=engine)
session = Session()


Base = declarative_base()
class Counts(Base):
    __tablename__ = 'Counts'
    id = Column(Integer, Sequence('user_id_seq'), primary_key=True, nullable=False)
    owner = Column(String)
    repo = Column(String)
    time =  Column(DateTime, default=datetime.utcnow)
    stargazers = Column(Integer)
    open_issues = Column(Integer)
    open_pulls = Column(Integer)


Base.metadata.create_all(engine)


def store_result(session, owner, repo, stargazers, open_issues, open_pulls):
    row = Counts(owner=owner,
                 repo=repo,
                 stargazers=stargazers,
                 open_issues=open_issues,
                 open_pulls=open_pulls)
    session.add(row)
    session.commit()


def fetch_counts(session, owner, repo):
    counts = session.query(Counts.time, Counts.stargazers, Counts.open_issues, Counts.open_pulls).filter(Counts.owner == owner).filter(Counts.repo == repo).order_by(Counts.time).all()
    return counts


def fetch_stats_from_github(g, owner, repo):
    repo = g.get_user(owner).get_repo(repo)

    stars = repo.stargazers_count
    open_issues = repo.open_issues_count
    open_pulls = len(list(repo.get_pulls()))
    return stars, open_issues, open_pulls


def observe_and_add(owner, repo):
    g = Github()
    stars, open_issues, open_pulls = fetch_stats_from_github(g, owner, repo)
    store_result(session, owner, repo, stars, open_issues, open_pulls)


def get_stats_series(owner, repo):
    series = fetch_counts(session, owner, repo)
    return series


if __name__ == '__main__':
    observe_and_add(OWNER, REPO)
