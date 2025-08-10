"""
Admin data management endpoints.

Routes (admin-only):
- POST /admin/data/{table_name}/import: CSV import with validation, batch=50
- PUT /admin/data/{table_name}/{id}: Edit single row
- DELETE /admin/data/{table_name}/{id}: Delete single row
- DELETE /admin/data/{table_name}/clear: Clear entire table with confirmation token
- GET /admin/data/{table_name}/export: Export current data as CSV template
"""
from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.api.deps import SessionDep
from app.core.admin_auth import destructive_rate_limit, require_admin
from app.services.admin_data_service import AdminDataService

# You may extend this registry to include more tables and their natural keys
from app.infrastructure.database.models import Job, Task, Machine

router = APIRouter(prefix="/admin/data", tags=["admin-data"])

# Register supported tables and natural keys
AdminDataService.register_table("jobs", Job, ("job_number",))
AdminDataService.register_table("tasks", Task, ("job_id", "sequence_in_job"))
AdminDataService.register_table("machines", Machine, ("name",))


class EditPayload(BaseModel):
    data: dict[str, Any]


@router.post("/{table_name}/import")
async def import_csv(
    table_name: str,
    file: UploadFile = File(...),
    session: SessionDep = None,
    current_admin = Depends(require_admin),
    _limit = Depends(destructive_rate_limit(limit=100, window_seconds=3600)),
):
    if file.content_type not in ("text/csv", "application/vnd.ms-excel", "application/csv", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Invalid file type; expected CSV")

    content = await file.read()
    service = AdminDataService(session)
    result = service.import_csv(table_name, content, batch_size=50)
    return {
        "total": result.total,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "errors": result.errors,
    }


@router.put("/{table_name}/{id}")
async def edit_row(
    table_name: str,
    id: str,
    payload: EditPayload,
    session: SessionDep = None,
    current_admin = Depends(require_admin),
):
    service = AdminDataService(session)
    obj = service.edit_row(table_name, id, payload.data)
    return {"message": "updated", "id": id}


@router.delete("/{table_name}/{id}")
async def delete_row(
    table_name: str,
    id: str,
    session: SessionDep = None,
    current_admin = Depends(require_admin),
    _limit = Depends(destructive_rate_limit(limit=200, window_seconds=3600)),
):
    service = AdminDataService(session)
    service.delete_row(table_name, id)
    return {"message": "deleted", "id": id}


@router.delete("/{table_name}/clear")
async def clear_table(
    table_name: str,
    confirm: str = Query(..., description="Confirmation token; must be 'CONFIRM'"),
    session: SessionDep = None,
    current_admin = Depends(require_admin),
    _limit = Depends(destructive_rate_limit(limit=20, window_seconds=3600)),
):
    if confirm != "CONFIRM":
        raise HTTPException(status_code=400, detail="Invalid confirmation token")
    service = AdminDataService(session)
    count = service.clear_table(table_name)
    return {"message": "cleared", "deleted": count}


@router.get("/{table_name}/export")
async def export_template(
    table_name: str,
    session: SessionDep = None,
    current_admin = Depends(require_admin),
):
    service = AdminDataService(session)
    filename, content = service.export_template(table_name)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

