"""Tele calling & appointments API."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import CurrentUserDep, DbSession
from app.models.calls_model import Appointment, CallLog

router = APIRouter(prefix="/calls", tags=["calls"])


# ── Schemas ────────────────────────────────────────────────────────────────

class CallLogCreate(BaseModel):
    customer_name: str
    phone: str
    agent_name: str | None = None
    duration_secs: int = 0
    status: str = "completed"
    call_direction: str = "outbound"
    sector: str | None = None
    centre_id: str | None = None
    centre_name: str | None = None
    recording_source: str | None = None
    notes: str | None = None
    recording_url: str | None = None
    started_at: datetime | None = None


class CallLogResponse(BaseModel):
    id: UUID
    customer_name: str
    phone: str
    agent_name: str | None
    started_at: datetime
    duration_secs: int
    status: str
    call_direction: str
    sector: str | None
    centre_id: str | None
    centre_name: str | None
    recording_source: str | None
    notes: str | None
    recording_url: str | None

    class Config:
        from_attributes = True


class AppointmentCreate(BaseModel):
    title: str | None = None
    customer_name: str
    phone: str | None = None
    assigned_name: str | None = None
    appointment_at: datetime
    appt_type: str = "other"
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    title: str | None = None
    customer_name: str | None = None
    phone: str | None = None
    assigned_name: str | None = None
    appointment_at: datetime | None = None
    appt_type: str | None = None
    status: str | None = None
    notes: str | None = None


class AppointmentResponse(BaseModel):
    id: UUID
    title: str | None
    customer_name: str
    phone: str | None
    assigned_name: str | None
    appointment_at: datetime
    appt_type: str
    status: str
    notes: str | None

    class Config:
        from_attributes = True


def _org(current: CurrentUserDep) -> UUID:
    if current.org_id is None:
        raise HTTPException(400, "No organization context")
    return current.org_id


# ── Call Logs ──────────────────────────────────────────────────────────────

@router.get("/logs", response_model=list[CallLogResponse])
async def list_calls(
    db: DbSession, current: CurrentUserDep,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
) -> list[CallLogResponse]:
    org = _org(current)
    result = await db.execute(
        select(CallLog).where(CallLog.organization_id == org)
        .order_by(CallLog.started_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    return [CallLogResponse.model_validate(c) for c in result.scalars().all()]


@router.post("/logs", response_model=CallLogResponse, status_code=201)
async def create_call_log(data: CallLogCreate, db: DbSession, current: CurrentUserDep) -> CallLogResponse:
    org = _org(current)
    log = CallLog(
        organization_id=org,
        customer_name=data.customer_name,
        phone=data.phone,
        agent_id=current.user.id,
        agent_name=data.agent_name or current.user.full_name,
        started_at=data.started_at or datetime.now(timezone.utc),
        duration_secs=data.duration_secs,
        status=data.status,
        call_direction=data.call_direction,
        sector=data.sector,
        centre_id=data.centre_id,
        centre_name=data.centre_name,
        recording_source=data.recording_source,
        notes=data.notes,
        recording_url=data.recording_url,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return CallLogResponse.model_validate(log)


# ── Appointments ───────────────────────────────────────────────────────────

@router.get("/appointments", response_model=list[AppointmentResponse])
async def list_appointments(
    db: DbSession, current: CurrentUserDep,
    status: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
) -> list[AppointmentResponse]:
    org = _org(current)
    q = select(Appointment).where(
        Appointment.organization_id == org,
        Appointment.deleted_at.is_(None),
    )
    if status:
        q = q.where(Appointment.status == status)
    result = await db.execute(q.order_by(Appointment.appointment_at.asc()).offset((page - 1) * page_size).limit(page_size))
    return [AppointmentResponse.model_validate(a) for a in result.scalars().all()]


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
async def create_appointment(data: AppointmentCreate, db: DbSession, current: CurrentUserDep) -> AppointmentResponse:
    org = _org(current)
    appt = Appointment(organization_id=org, **data.model_dump())
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return AppointmentResponse.model_validate(appt)


@router.patch("/appointments/{appt_id}", response_model=AppointmentResponse)
async def update_appointment(appt_id: UUID, data: AppointmentUpdate, db: DbSession, current: CurrentUserDep) -> AppointmentResponse:
    org = _org(current)
    appt = (await db.execute(
        select(Appointment).where(Appointment.id == appt_id, Appointment.organization_id == org, Appointment.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not appt:
        raise HTTPException(404, "Appointment not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(appt, k, v)
    await db.commit()
    await db.refresh(appt)
    return AppointmentResponse.model_validate(appt)


@router.delete("/appointments/{appt_id}", status_code=204)
async def delete_appointment(appt_id: UUID, db: DbSession, current: CurrentUserDep) -> None:
    org = _org(current)
    appt = (await db.execute(
        select(Appointment).where(Appointment.id == appt_id, Appointment.organization_id == org, Appointment.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not appt:
        raise HTTPException(404, "Appointment not found")
    appt.deleted_at = datetime.now(timezone.utc)
    await db.commit()
