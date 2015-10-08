#!/usr/bin/env python

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Sequence, DateTime
from sqlalchemy.orm import sessionmaker

from datetime import datetime
import os


DATABASE_URL = os.environ.get('DATABASE_URL', 'postgres:///issue-tracker')
engine = create_engine(DATABASE_URL, echo=True)
Session = sessionmaker(bind=engine)


Base = declarative_base()

class Repos(Base):
    __tablename__ = 'repos'
    id = Column(Integer, primary_key=True, nullable=False)
    owner = Column(String)
    repo = Column(String)
    token = Column(String)
    add_time = Column(DateTime, default=datetime.utcnow)


class Counts(Base):
    __tablename__ = 'counts'
    id = Column(Integer, primary_key=True, nullable=False)
    owner = Column(String)
    repo = Column(String)
    time = Column(DateTime, default=datetime.utcnow)
    stargazers = Column(Integer)
    open_issues = Column(Integer)
    open_pulls = Column(Integer)


class CountsByLabel(Base):
    __tablename__ = 'counts_by_label'
    id = Column(Integer, primary_key=True, nullable=False)
    owner = Column(String)
    repo = Column(String)
    label = Column(String)
    time = Column(DateTime, default=datetime.utcnow)
    open_issues = Column(Integer)


Base.metadata.create_all(engine)


def store_result(owner, repo, stats):
    '''stats is a tracker.RepoStats object'''
    now = datetime.utcnow()

    session = Session()
    session.add(Counts(owner=owner,
                       repo=repo,
                       time=now,
                       stargazers=stats.stargazers,
                       open_issues=stats.open_issues,
                       open_pulls=stats.open_pulls))

    for label, open_issues in stats.label_to_count.iteritems():
        session.add(CountsByLabel(owner=owner,
                                  repo=repo,
                                  time=now,
                                  label=label,
                                  open_issues=open_issues))

    session.commit()


def get_stats_series(owner, repo):
    # TODO: return tracker.RepoStats objects?
    session = Session()
    counts = (session.query(Counts.time,
                            Counts.stargazers,
                            Counts.open_issues,
                            Counts.open_pulls)
                     .filter(Counts.owner == owner)
                     .filter(Counts.repo == repo)
                     .order_by(Counts.time)
                     .all())
    return counts

