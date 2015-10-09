#!/usr/bin/env python

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Sequence, DateTime
from sqlalchemy.orm import sessionmaker

from collections import defaultdict
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


def ordered_labels(label_counts):
    '''Given time, label, count tuples, return a sorted list of unique labels.'''
    return list(sorted(set(label for _, label, _ in label_counts)))


def get_stats_series(owner, repo):
    session = Session()
    counts = (session.query(Counts.time,
                            Counts.stargazers,
                            Counts.open_issues,
                            Counts.open_pulls)
                     .filter(Counts.owner == owner)
                     .filter(Counts.repo == repo)
                     .order_by(Counts.time)
                     .all())

    label_counts = (session.query(CountsByLabel.time,
                                  CountsByLabel.label,
                                  CountsByLabel.open_issues)
                           .filter(CountsByLabel.owner == owner)
                           .filter(CountsByLabel.repo == repo)
                           .order_by(CountsByLabel.time)
                           .all())

    # Pull out three separate time series for issues, stargazers and PRs
    open_issues = []
    stargazers = []
    open_pulls = []
    for time, stars, issues, pulls in counts:
        stargazers.append((time, stars))
        open_issues.append((time, issues))
        open_pulls.append((time, pulls))

    # Group by label
    date_to_label_to_count = defaultdict(dict)
    for time, label, count in label_counts:
        date_to_label_to_count[time][label] = count

    print date_to_label_to_count

    labels = ordered_labels(label_counts)

    by_label = []
    for date in sorted(date_to_label_to_count.keys()):
        label_to_count = date_to_label_to_count[date]
        row = [date] + [label_to_count.get(label, 0) for label in labels]
        by_label.append(row)

    try:
        blank_idx = labels.index('')
        labels[blank_idx] = '(unlabeled)'
    except ValueError:
        pass
    by_label = [['Date'] + labels] + by_label

    return stargazers, open_issues, open_pulls, by_label

