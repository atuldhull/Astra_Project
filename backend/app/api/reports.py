"""
PDF mission report endpoint. Streams a generated report as application/pdf.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.reports import generate_mission_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/mission/{mission_id}.pdf",
    responses={200: {"content": {"application/pdf": {}}}},
)
def mission_report(
    mission_id: int,
    db: Session = Depends(get_db),
) -> Response:
    try:
        pdf = generate_mission_report(db, mission_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="astra-mission-{mission_id}.pdf"',
        },
    )
