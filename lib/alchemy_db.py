#!/usr/bin/env python2

from __future__ import print_function, division, unicode_literals

import os
import json
from collections import OrderedDict

from cached_property import cached_property
from sqlalchemy import create_engine, MetaData, Table, Column, func as sql_func
from sqlalchemy.orm import mapper, sessionmaker
from sqlalchemy.exc import NoSuchTableError
import sqlalchemy.types as sqltypes

from common import InputValidationException
from log_handling import LogManager

defintions_metatable = "__table_defs__"


class AlchemyDatabase:
    _instances = {}

    def __init__(self, db_path=None, echo=False, logger=None):
        if logger is None:
            self.logger, log_path = LogManager.create_default_logger()
        else:
            self.logger = logger
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
        self.add_table(defintions_metatable, [("name", "TEXT"), ("columns", "TEXT")], "name")
        for tbl in self.engine.table_names():
            if tbl != defintions_metatable:
                self.add_table(tbl)
        self._instances[self.db_path] = self

    @property
    def tables(self):
        return self._tables

    @classmethod
    def get_db(cls, db_path, *args, **kwargs):
        if db_path not in cls._instances:
            cls._instances[db_path] = cls(db_path, *args, **kwargs)
        return cls._instances[db_path]

    def add_table(self, name, columns=None, pk=None):
        if name in self._tables:
            raise KeyError("Table '{}' already exists".format(name))
        return DBTable(self, name, columns, pk)

    def register_table(self, db_table):
        if not isinstance(db_table, DBTable):
            raise TypeError("Invalid db_table type - expected DBTable, found: {}".format(type(db_table).__name__))
        if db_table.name not in self._tables:
            self._tables[db_table.name] = db_table

    def __getitem__(self, key):
        return self._tables[key]

    def __contains__(self, item):
        return item in self._tables

    def __iter__(self):
        for table in self._tables:
            yield self._tables[table]

    def test(self):
        tbl1 = self.add_table("test_1", [("id", "INTEGER"), ("name", "TEXT")])
        self.add_table("test_2", [("email", "TEXT"), ("name", "TEXT")])
        tbl1.insert([0, "hello db"])
        self["test_2"]["bob@gmail.com"] = ["bob"]
        self["test_1"].insert([1, "line2"])
        pickle_table = self.add_table("pickled", [("id", "INTEGER"), ("values", "PickleType")])
        pickle_table.insert([0, {"z": 1, "x": ["a", "b", "c"]}])


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
                    self.session.commit()
                else:
                    raise KeyError(key)

            def __len__(row):
                return len(self.columns)

            def update(row, d=None, **kwargs):
                if d is not None:
                    for k, v in d.iteritems():
                        if k in self.columns:
                            setattr(row, k, v)
                for k, v in kwargs.iteritems():
                    if k in self.columns:
                        setattr(row, k, v)
                self.session.commit()

            def keys(row):
                return self.columns

            def iteritems(row):
                for c in self.columns:
                    yield c, getattr(row, c)

            def __iter__(row):
                for c in self.columns:
                    yield c

            def as_dict(row):
                return OrderedDict([(c, getattr(row, c)) for c in self.columns])

            def __repr__(row):
                return "<DBRow in {} for pk='{}'>".format(self.name, row[self.pk])

            def __str__(row):
                return json.dumps(row.as_dict())

        self.db = parent_db
        self.logger = self.db.logger
        self.name = name
        self.rowType = DBRow
        self.session = self.db.session

        col_types = None
        try:
            self.table = Table(self.name, self.db.meta, autoload=True)
        except NoSuchTableError as e:
            self.logger.verbose("Creating table '{}' in {}".format(self.name, self.db.db_path))
            if columns is None:
                raise e
            cols = OrderedDict()
            for col in columns:
                if isinstance(col, tuple):
                    cols[col[0]] = getattr(sqltypes, col[1]) if hasattr(sqltypes, col[1]) else None
                else:
                    cols[col] = None

            col_types = [[k, v.__name__ if v is not None else None] for k, v in cols.iteritems()]

            if pk is None:
                pk = cols.keys()[0]
            elif pk not in cols:
                raise KeyError("The provided PK is not one of the provided columns: {}".format(pk))
            table_cols = [Column(n, t) if pk != n else Column(n, t, primary_key=True) for n, t in cols.iteritems()]
            self.table = Table(self.name, self.db.meta, *table_cols)
            if self.name != defintions_metatable:
                self.db[defintions_metatable].insert([self.name, json.dumps(col_types)])
        else:
            if (self.name != defintions_metatable) and (self.name in self.db[defintions_metatable]):
                for col_name, col_type in json.loads(self.db[defintions_metatable][self.name]["columns"]):
                    actual_col = self.table.columns[col_name]
                    if (col_type is not None) and (type(actual_col.type).__name__ != col_type):
                        actual_col.type = getattr(sqltypes, col_type)()
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

        if self.name not in self.db.engine.table_names():
            self.db.meta.create_all()

        if (self.name == defintions_metatable) and (self.name not in self):
            self.insert([self.name, json.dumps(col_types)])
        self.db.register_table(self)

    def select(self, **kwargs):
        return self.rows().filter_by(**kwargs)

    def distinct_select(self, column):
        """
        :param column: Name of the column for which to select distinct values
        :return list: Unique values for the given column in this table
        """
        if column not in self.columns:
            raise KeyError(column)
        return [val[0] for val in self.session.query(getattr(self.rowType, column)).distinct()]

    def distinct_iter(self, column):
        if column not in self.columns:
            raise KeyError(column)
        for val in self.session.query(getattr(self.rowType, column)).distinct():
            yield val[0]

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
        self.session.commit()

    def bulk_delete(self, keys):
        for key in keys:
            self.session.query(self.rowType).filter_by(**{self.pk: key}).delete()
        self.session.commit()

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
            raise InputValidationException("Expected {}~{} elements; found {}".format(col_count - 1, col_count, len(value)))
            #raise InputValidationException("Invalid number of elements in the provided row: {}".format(len(value)))

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

    def __len__(self):
        return self.session.query(sql_func.count(getattr(self.rowType, self.pk))).scalar()

    def __iter__(self):
        for row in self.session.query(self.rowType):
            yield row

    def columns(self):
        return self.table.columns.keys()

    def rows(self):
        return [row for row in self.session.query(self.rowType)]

    @cached_property
    def simple(self):
        return SimpleDBTable(self)


class SimpleDBTable(object):
    def __init__(self, db_table):
        cols = dict(db_table.columns)
        if len(cols) > 2:
            raise ValueError("SimpleDBTable only accepts tables with 2 columns; {} has {}".format(db_table.name, len(cols)))
        cols.pop(db_table.pk)
        self.val_col = cols.keys()[0]
        self.table = db_table

    def __getitem__(self, key):
        return self.table[key][self.val_col]

    def __setitem__(self, key, value):
        self.table[key] = [value]

    def __contains__(self, item):
        return item in self.table

    def __iter__(self):
        for row in self.table:
            yield row[self.val_col]

    def iteritems(self):
        for row in self.table:
            yield row[self.table.pk], row[self.val_col]


if __name__ == "__main__":
    lm = LogManager.create_default_stream_logger(True)
