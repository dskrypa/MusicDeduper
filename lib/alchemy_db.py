#!/usr/bin/env python2

from __future__ import print_function, division

import os
import json
from collections import OrderedDict
import sqlalchemy
from sqlalchemy import create_engine, MetaData, Table, Column
from sqlalchemy.orm import mapper, sessionmaker
from sqlalchemy.exc import NoSuchTableError
import sqlalchemy.types

from common import InputValidationException
from log_handling import LogManager


class AlchemyDatabase:
    def __init__(self, db_path=None, echo=False):
        self.db_path = os.path.expanduser(db_path if db_path is not None else ":memory:")
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)
        self.engine = create_engine("sqlite:///{}".format(self.db_path), echo=echo)
        self.meta = MetaData(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.session.autocommit = True
        self._tables = {}
        for tbl in self.engine.table_names():
            self.add_table(tbl)

    def add_table(self, name, columns=None, pk=None):
        self._tables[name] = DBTable(self, name, columns, pk)
        if name not in self.engine.table_names():
            self.meta.create_all()
        return self._tables[name]

    def __getitem__(self, key):
        return self._tables[key]

    def __iter__(self):
        for table in self._tables:
            yield self._tables[table]

    def test(self):
        tbl1 = self.add_table("test_1", [("id", "INTEGER"), ("name", "TEXT")])
        self.add_table("test_2", [("email", "TEXT"), ("name", "TEXT")])
        tbl1.insert([0, "hello db"])
        self["test_2"]["bob@gmail.com"] = ["bob"]
        self["test_1"].insert([1, "line2"])


class DBTable(object):
    def __init__(self, parent_db, name, columns=None, pk=None):
        class DBRow(object):
            def __getitem__(row, key):
                if key in self.columns:
                    return getattr(row, key)
                raise KeyError(key)

            def __setitem__(row, key, value):
                if key in self.columns:
                    setattr(row, key, value)
                else:
                    raise KeyError(key)

            def update(row, d=None, **kwargs):
                if d is not None:
                    for k, v in d.iteritems():
                        row[k] = v
                for k, v in kwargs.iteritems():
                    row[k] = v

            def keys(row):
                return row.as_dict().keys()

            def iteritems(row):
                for k, v in row.as_dict().iteritems():
                    yield k, v

            def __iter__(row):
                for k in row.as_dict():
                    yield k

            def as_dict(row):
                return OrderedDict([(c, getattr(row, c)) for c in self.columns])

            def __repr__(row):
                return json.dumps(row.as_dict())

        self.db = parent_db
        self.name = name
        self.rowType = DBRow
        self.session = self.db.session
        try:
            self.table = Table(self.name, self.db.meta, autoload=True)
        except NoSuchTableError as e:
            if columns is None:
                raise e
            cols = OrderedDict()
            for col in columns:
                if isinstance(col, tuple):
                    cols[col[0]] = getattr(sqlalchemy.types, col[1]) if hasattr(sqlalchemy.types, col[1]) else None
                else:
                    cols[col] = None
            if pk is None:
                pk = cols.keys()[0]
            elif pk not in cols:
                raise KeyError("The provided PK is not one of the provided columns: {}".format(pk))
            table_cols = [Column(n, t) if pk != n else Column(n, t, primary_key=True) for n, t in cols.iteritems()]
            self.table = Table(self.name, self.db.meta, *table_cols)
        mapper(self.rowType, self.table)

        self.columns = OrderedDict(self.table.columns.items())
        self.pk, self.pk_pos, c = None, 0, 0
        for col_name, col_def in self.columns.iteritems():
            if col_def.primary_key:
                self.pk_pos = c
                self.pk = col_name
                break
            c += 1
        assert self.pk is not None

    def select(self, **kwargs):
        return self.rows().filter_by(**kwargs)

    def __getitem__(self, key):
        try:
            return self.session.query(self.rowType).filter_by(**{self.pk: key})[0]
        except IndexError:
            raise KeyError(key)

    def __contains__(self, key):
        return bool(self.session.query(self.rowType).filter_by(**{self.pk: key}).all())

    def __delitem__(self, key):
        if not key in self:
            raise KeyError(key)
        self.session.query(self.rowType).filter_by(**{self.pk: key}).delete()

    def insert(self, row):
        if not isinstance(row, (tuple, list, dict)):
            raise TypeError("Expected tuple, list, or dict; found {}".format(type(row)))
        elif len(row) != len(self.columns):
            raise InputValidationException("Found {} columns; expected {}".format(len(row), len(self.columns)))

        if isinstance(row, (list, tuple)):
            col_keys = self.columns.keys()
            row = {col_keys[c]: row[c] for c in range(len(col_keys))}
        self.table.insert(row).execute()

    def __setitem__(self, key, value):
        if not isinstance(value, (list, dict, tuple)):
            raise TypeError("Expected tuple, list, or dict; found {}".format(type(value)))
        col_count = len(self.columns)
        if len(value) not in (col_count, col_count - 1):
            raise InputValidationException("Invalid number of elements in the provided row: {}".format(len(value)))

        if isinstance(value, dict):
            row = dict(value)
            if (self.pk in row) and (row[self.pk] != key):
                raise KeyError("The PK '{}' does not match the value in the provided row: {}".format(key, row[self.pk]))
            elif self.pk not in row:
                row[self.pk] = key
        else:
            row_list = list(value)
            if len(value) != col_count:
                row_list.insert(self.pk_pos, key)
            row = dict(zip(self.columns.keys(), row_list))

        try:
            self[key].update(row)
        except KeyError:
            self.insert(row)

    def __iter__(self):
        for row in self.session.query(self.rowType):
            yield row

    def columns(self):
        return self.table.columns.keys()

    def rows(self):
        return [row for row in self.session.query(self.rowType)]


if __name__ == "__main__":
    lm = LogManager.create_default_stream_logger(True)
