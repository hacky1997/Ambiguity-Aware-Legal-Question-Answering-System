from __future__ import annotations

from legalrag.audit import AuditRecord
from legalrag.audit_store import AuditStore


class Cursor:
    def __init__(self):
        self.query = ""
        self.params = ()

    def execute(self, query, params):
        self.query = query
        self.params = params


class Connection:
    def __init__(self):
        self._cursor = Cursor()
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True


def test_audit_store_writes_minimized_record():
    connection = Connection()
    AuditStore(connection).write(
        AuditRecord("question", "ask", ("F1",), {}, {"input": True}, (), "v1", "idx1", 4)
    )
    assert "INSERT INTO audit_records" in connection._cursor.query
    assert connection.committed
    assert connection._cursor.params[0] == "question"
