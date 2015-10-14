#!/usr/bin/env python

from sqlalchemy import create_engine, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Sequence, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, backref
import dateutil.parser

from collections import defaultdict
from datetime import datetime
import os
import time


DATABASE_URL = os.environ.get('DATABASE_URL', 'postgres:///issue-tracker')
#engine = create_engine(DATABASE_URL, echo=True)
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

STARS_LABEL = '__STARS'
ALL_ISSUES_LABEL = '__ALL'
PULL_REQUESTS_LABEL = '__PRS'


Base = declarative_base()

class Repos(Base):
    __tablename__ = 'repos'
    id = Column(Integer, primary_key=True, nullable=False)
    owner = Column(String(100))
    repo = Column(String(100))
    token = Column(String(100))
    add_time = Column(DateTime, default=datetime.utcnow)


class CountsByLabel(Base):
    __tablename__ = 'counts_by_label'
    id = Column(Integer, primary_key=True, nullable=False)
    repo_id = Column(Integer, ForeignKey('repos.id'))
    repo = relationship("Repos")
    label = Column(String(50))  # can also be STARS_LABEL, ALL_ISSUES_LABEL or PULL_REQUESTS_LABEL
    time = Column(DateTime, default=datetime.utcnow)
    count = Column(Integer)


Base.metadata.create_all(engine)


def store_result(owner, repo, stats):
    '''stats is a tracker.RepoStats object'''
    now = datetime.utcnow()

    session = Session()
    repo = get_repo(session, owner, repo)

    session.add(CountsByLabel(repo_id=repo.id, time=now, label=ALL_ISSUES_LABEL, count=stats.open_issues))
    session.add(CountsByLabel(repo_id=repo.id, time=now, label=PULL_REQUESTS_LABEL, count=stats.open_pulls))
    session.add(CountsByLabel(repo_id=repo.id, time=now, label=STARS_LABEL, count=stats.stargazers))

    for label, count in stats.label_to_count.iteritems():
        session.add(CountsByLabel(repo_id=repo.id,
                                  time=now,
                                  label=label,
                                  count=count))

    session.commit()


def ordered_labels(label_counts):
    '''Given time, label, count tuples, return a sorted list of unique labels.'''
    return list(sorted(set(label for _, label, _ in label_counts)))


def get_repo(session, owner, repo):
    return (session.query(Repos).filter(Repos.owner == owner).filter(Repos.repo == repo)).one()


def is_repo_tracked(owner, repo):
    session = Session()
    count = (session.query(Repos).filter(Repos.owner == owner).filter(Repos.repo == repo)).count()
    return count > 0


def tracked_repos():
    session = Session()
    return session.query(Repos)


def get_stats_series(owner, repo):
    session = Session()
    repo = get_repo(session, owner, repo)

    counts = (session.query(CountsByLabel)
        .filter(CountsByLabel.repo_id == repo.id)
        .filter(or_(CountsByLabel.label == ALL_ISSUES_LABEL,
                    CountsByLabel.label == PULL_REQUESTS_LABEL,
                    CountsByLabel.label == STARS_LABEL))
        .order_by(CountsByLabel.label, CountsByLabel.time))

    open_issues = []
    stargazers = []
    open_pulls = []
    label_counts = []

    for row in counts:
        label = row.label
        pair = (row.time, row.count)
        if label == ALL_ISSUES_LABEL:
            open_issues.append(pair)
        elif label == PULL_REQUESTS_LABEL:
            open_pulls.append(pair)
        elif label == STARS_LABEL:
            stargazers.append(pair)
        else:
            label_counts.append((row.time, label, row.count))

    # Group by label
    date_to_label_to_count = defaultdict(dict)
    for time, label, count in label_counts:
        date_to_label_to_count[time][label] = count

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


def store_backfill(owner, repo, backfill_data):
    '''Store backfilled issue and star data in the database.
    
    The backfill data is a dict with a subset of these keys:
    
    - stars
    - open_issues
    - issues_by_label
    - delete

    Values are lists of ['YYYY-MM-DD', count] tuples. The changes in a single
    request are atomic, but can be chunked into multiple requests to keep the
    backfill from taking too long.
    '''
    session = Session()

    repo = get_repo(session, owner, repo)

    def delete_for_label(label):
        session.query(CountsByLabel).filter(CountsByLabel.repo_id == repo.id).filter(CountsByLabel.label == label).delete()

    def fill_for_label(label, data):
        start_secs = time.time()
        session.execute(CountsByLabel.__table__.insert(), [
            {
                'repo_id': repo.id,
                'label': label,
                'time': dateutil.parser.parse(row[0]),
                'count': int(row[1])
            } for row in data])
        stop_secs = time.time()
        print 'Inserted %d rows in %f secs' % (len(data), stop_secs - start_secs)

    if 'delete' in backfill_data:
        t = backfill_data['delete']
        if t == 'open_issues':
            delete_for_label(ALL_ISSUES_LABEL)
        elif t == 'stargazers':
            delete_for_label(STARS_LABEL)
        elif t == 'open_pulls':
            delete_for_label(PULL_REQUESTS_LABEL)
        elif t == 'by_label':
            (session.query(CountsByLabel)
                    .filter(CountsByLabel.repo_id == repo.id)
                    .filter(CountsByLabel.label != ALL_ISSUES_LABEL,
                            CountsByLabel.label != STARS_LABEL,
                            CountsByLabel.label != PULL_REQUESTS_LABEL)
                    .delete())

    if 'open_issues' in backfill_data:
        fill_for_label(ALL_ISSUES_LABEL, backfill_data['open_issues'])

    if 'stargazers' in backfill_data:
        fill_for_label(STARS_LABEL, backfill_data['stargazers'])

    if 'open_pulls' in backfill_data:
        fill_for_label(PULL_REQUESTS_LABEL, backfill_data['open_pulls'])

    if 'by_label' in backfill_data:
        for label, data in backfill_data['by_label'].iteritems():
            fill_for_label(label, data)

    session.commit()


def add_repo(owner, repo, token):
    '''Add a new repo to the list of tracked repos.'''
    session = Session()
    session.add(Repos(owner=owner, repo=repo, token=token))
    session.commit()
