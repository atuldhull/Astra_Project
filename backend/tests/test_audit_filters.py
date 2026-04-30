"""audit filter parsing.

_parse_event_types is the gateway between query strings and the
AuditEventType enum. A regression here = silent filter drops on /audit.
"""

import pytest
from fastapi import HTTPException

from app.api.audit import _parse_event_types
from app.db.models import AuditEventType


def test_parse_none_returns_none():
    assert _parse_event_types(None) is None
    assert _parse_event_types("") is None


def test_parse_single():
    out = _parse_event_types("ingest_completed")
    assert out == [AuditEventType.INGEST_COMPLETED]


def test_parse_multi_csv():
    out = _parse_event_types("ingest_completed,alert_engaged")
    assert out == [AuditEventType.INGEST_COMPLETED, AuditEventType.ALERT_ENGAGED]


def test_parse_strips_whitespace_and_empty_tokens():
    out = _parse_event_types("ingest_completed , , alert_engaged")
    assert out == [AuditEventType.INGEST_COMPLETED, AuditEventType.ALERT_ENGAGED]


def test_parse_rejects_unknown():
    with pytest.raises(HTTPException) as exc:
        _parse_event_types("nope_not_an_event")
    assert exc.value.status_code == 400


def test_parse_includes_d35_public_events():
    out = _parse_event_types("public_report_submitted,public_report_pinned")
    assert out == [
        AuditEventType.PUBLIC_REPORT_SUBMITTED,
        AuditEventType.PUBLIC_REPORT_PINNED,
    ]
