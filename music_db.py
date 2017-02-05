#!/usr/bin/env python2

from __future__ import print_function, division

import os
import sqlite3
import logging
from operator import itemgetter
from collections import OrderedDict

from common import InputValidationException, itemfinder

OperationalError = sqlite3.OperationalError


class Sqlite3Database:
    """
    None -> NULL, int -> INTEGER, long -> INTEGER, float -> REAL, str -> TEXT, unicode -> TEXT, buffer -> BLOB
    """
    def __init__(self, db_path=None):
        self.db_path = os.path.expanduser(db_path if db_path is not None else "/var/tmp/deduper_music.db")
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)
        self.db = sqlite3.connect(self.db_path)
        self.c = self.db.cursor()

    def execute(self, *args, **kwargs):
        with self.db:
            return self.db.execute(*args, **kwargs)

    def create_table(self, name, columns):
        """
        :param name: Table name
        :param list columns: Column names
        """
        self.execute("CREATE TABLE {} ({});".format(name, ", ".join(columns)))

    def drop_table(self, name, vacuum=True):
        """
        Drop the given table from this DB, optionally performing VACUUM to reconstruct the DB, recovering the space that
        was used by the table that was dropped
        :param name: Name of the table to be dropped
        :param bool vacuum: Perform VACUUM after dropping the table
        """
        self.execute("DROP TABLE {};".format(name))
        if vacuum:
            self.execute("VACUUM;")

    def __contains__(self, item):
        return self.table_exists(item)

    def __getitem__(self, item):
        if item not in self:
            raise KeyError("Table '{}' does not exist in this DB".format(item))
        return DBTable(self, item)

    def __iter__(self):
        for table in self.get_table_names():
            yield DBTable(self, table)

    def insert(self, table, row):
        """
        :param table: Table name
        :param list row: Values
        """
        self.execute("INSERT INTO {} VALUES ({});".format(table, ("?," * len(row))[:-1]), tuple(row))

    def update(self, table, where, **set_args):
        set_strs = ["{} = {}".format(k, "'{}'".format(v) if isinstance(v, (str, unicode)) else v) for k, v in set_args.iteritems()]
        self.execute("UPDATE {} SET {} WHERE {};".format(table, ", ".join(set_strs), where))

    def delete_row(self, table, where):
        self.execute("DELETE FROM {} WHERE {};".format(table, where))

    def query(self, query):
        """
        :param query: Query string
        :return list: Result rows
        """
        results = self.execute(query)
        if results.description is None:
            raise OperationalError("No Results.")
        headers = [fields[0] for fields in results.description]
        return [dict(zip(headers, row)) for row in results]

    def iterquery(self, query):
        results = self.execute(query)
        if results.description is None:
            raise OperationalError("No Results.")
        headers = [fields[0] for fields in results.description]
        for row in results:
            yield dict(zip(headers, row))

    def select(self, columns, table, where=None):
        """
        SELECT $columns FROM $table (WHERE $where);
        :param columns: Column name(s)
        :param table: Table name
        :param where: Conditional expression string
        :return list: Result rows
        """
        cols = ", ".join(columns) if isinstance(columns, (list, tuple)) else columns
        cond = " WHERE {}".format(where) if where is not None else ""
        return self.query("SELECT {} FROM {}{};".format(cols, table, cond))

    def get_table_names(self):
        """
        :return list: Names of tables in this DB
        """
        return [row["name"] for row in self.select("name", "sqlite_master", "type='table'")]

    def table_exists(self, table):
        return bool(self.select("name", "sqlite_master", "type='table' AND name='{}'".format(table)))

    def table_info(self, table):
        return self.query("pragma table_info({})".format(table))

    def column_names(self, table):
        return [col["name"] for col in self.table_info(table)]

    def test(self):
        self.create_table("test_1", ["id INTEGER", "name TEXT"])
        self.create_table("test_2", ["email TEXT", "name TEXT"])
        self.insert("test_1", [0, "hello db"])
        self.insert("test_2", ["bob@gmail.com", "bob"])
        self.insert("test_1", [1, "line2"])


class DBRow(dict):
    def __init__(self, db_table, *args, **kwargs):
        """
        :param DBTable db_table: DBTable in which this row resides
        :param args: dict positional args
        :param kwargs: dict kwargs
        """
        super(DBRow, self).__init__(*args, **kwargs)
        self.table = db_table
        self.pk = self.table.pk

    def __setitem__(self, key, value):
        if (key in self) and (self[key] == value):
            return
        elif key == self.pk:
            raise KeyError("Unable to change PrimaryKey ('{}')".format(self.pk))
        elif key not in self:
            raise KeyError("Unable to add additional key: {}".format(key))
        self.table.update_row(self[self.table.pk], key, value)
        super(DBRow, self).__setitem__(key, value)

    def update(self, E=None, **F):
        if E is not None:
            for k, v in E.iteritems():
                self[k] = v
        for k, v in F.iteritems():
            self[k] = v

    def popitem(self):
        raise NotImplementedError("popitem is not permitted on DBRow objects")

    def pop(self, k, d=None):
        raise NotImplementedError("pop is not permitted on DBRow objects")

    def clear(self):
        raise NotImplementedError("clear is not permitted on DBRow objects")

    def __delitem__(self, key):
        raise NotImplementedError("del is not permitted on DBRow objects")


class DBTable:
    def __init__(self, parent_db, table, columns=None, pk=None):
        """
        :param AbstractDB parent_db: DB in which this table resides
        :param table: Name of the table
        :param list columns: Column names
        :param pk: Primary key (defaults to the table's PK or the first column if not defined for the table)
        """
        self.db = parent_db
        self.name = table
        table_exists = self.db.table_exists(self.name)

        if (columns is None) and (not table_exists):
            raise InputValidationException("Columns are required for tables that do not already exist")

        if table_exists:
            table_info = self.db.table_info(self.name)
            current_names = [entry["name"] for entry in table_info]
            current_types = [entry["type"] for entry in table_info]
            pk_entry = itemfinder(table_info, itemgetter("pk"))
            current_pk = pk_entry["name"] if pk_entry is not None else None
        else:
            current_names, current_types, current_pk = None, None, None

        if columns is not None:
            if not isinstance(columns, (list, tuple)):
                raise TypeError("Columns must be provided as a list or tuple, not {}".format(type(columns)))
            elif (current_names is not None) and (len(current_names) != len(columns)):
                raise InputValidationException("The number of columns provided does not match the existing ones")

            self.col_names, self.col_types = [], []
            for col in columns:
                if isinstance(col, tuple):
                    self.col_names.append(col[0])
                    self.col_types.append(col[1])
                else:
                    self.col_names.append(col)
                    self.col_types.append("")

            if (current_names is not None) and (self.col_names != current_names):
                raise InputValidationException("The provided column names do not match the existing ones")
            elif current_types is not None:
                for i in range(len(current_types)):
                    ct = current_types[i]
                    nt = self.col_types[i]
                    if (ct != nt) and ((ct != "") or (nt != "")):
                        raise InputValidationException("The provided type for column '{}' ({}) did not match the existing one ({})".format(self.col_names[i], ct, nt))
        else:
            self.col_names = current_names
            self.col_types = current_types

        self.columns = OrderedDict(zip(self.col_names, self.col_types))

        if pk is not None:
            if pk not in self.col_names:
                raise InputValidationException("The provided PK '{}' is not a column in this table".format(pk))
            self.pk = pk
        else:
            self.pk = current_pk if current_pk is not None else self.col_names[0]

        self.pk_pos = 0
        for c in range(len(self.col_names)):
            if self.pk == self.col_names[c]:
                self.pk_pos = c
                break
        assert self.col_names[self.pk_pos] == self.pk

        if not table_exists:
            col_strs = ["{} {}".format(cname, ctype) if ctype else cname for cname, ctype in self.columns.iteritems()]
            self.db.create_table(self.name, col_strs)

    def select(self, columns, where=None):
        return self.db.select(columns, self.name, where)

    def insert(self, row):
        if isinstance(row, dict):
            row = [row[k] for k in self.col_names]
        self.db.insert(self.name, row)

    def _fmt_pk_val(self, val):
        if (self.columns[self.pk] == "TEXT") or isinstance(val, (str, unicode)):
            return "'{}'".format(val)
        return val

    def __contains__(self, item):
        return bool(self.db.select("*", self.name, "{}={}".format(self.pk, self._fmt_pk_val(item))))

    def rows(self):
        return [DBRow(self, row) for row in self.db.select("*", self.name)]

    def iterrows(self):
        for row in self.db.select("*", self.name):
            yield DBRow(self, row)

    def __iter__(self):
        for row in self.db.select("*", self.name):
            yield DBRow(self, row)

    def __getitem__(self, item):
        results = self.db.select("*", self.name, "{}={}".format(self.pk, self._fmt_pk_val(item)))
        if not results:
            raise KeyError(item)
        return DBRow(self, results[0])

    def __delitem__(self, key):
        if key in self:
            self.db.delete_row(self.name, "{}={}".format(self.pk, self._fmt_pk_val(key)))
        else:
            raise KeyError(key)

    def __setitem__(self, key, value):
        """
        Replace a current row, or insert a new one.  If a list or tuple is provided and its length is 1 shorter than the
        number of columns in this table, then the PK is inserted at position self.pk_pos before the row is modified.
        :param key: PK of a row in this table
        :param value: list, tuple, or dict to be added to this table
        """
        if not isinstance(value, (list, dict, tuple)):
            raise TypeError("Rows must be provided as a list, tuple, or dict, not {}".format(type(value)))

        col_count = len(self.col_names)
        if len(value) not in (col_count, col_count - 1):
            raise InputValidationException("Invalid number of elements in the provided row: {}".format(len(value)))

        if key in self:
            if isinstance(value, dict):
                row = value
            else:
                row_list = list(value)
                if len(value) != col_count:
                    row_list.insert(self.pk_pos, key)
                row = dict(zip(self.col_names, row_list))
            self[key].update(row)
        else:
            if isinstance(value, dict):
                val_pk = value.get(self.pk, None)
                if val_pk is None:
                    row = dict(**value)
                    row[self.pk] = key
                elif val_pk != key:
                    raise KeyError("The PK '{}' does not match the value in the provided row: {}".format(key, val_pk))
                else:
                    row = value
            else:
                row = list(value)
                if len(value) != col_count:
                    row.insert(self.pk_pos, key)
            self.insert(row)

    def update_row(self, row_pk, key, value):
        self.db.update(self.name, "{} = {}".format(self.pk, self._fmt_pk_val(row_pk)), **{key: value})



class MusicDB:
    def __init__(self, db_path=None):
        self.db_path = os.path.expanduser(db_path if db_path is not None else "/var/tmp/deduper_music.db")

        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

        self.db = sqlite3.connect(self.db_path)
        self.c = self.db.cursor()