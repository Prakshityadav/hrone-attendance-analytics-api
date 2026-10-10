"""
Employee Attendance & Analytics API - STARTER

Run:  uvicorn app.main:app --port 8000
Env:  MONGO_URI, MONGO_DB (a local .env is loaded for convenience)

This file was written quickly by a colleague who has left the company. The happy path
works, but nobody has reviewed it. Read PROBLEM_STATEMENT.docx for what is expected of you,
openapi.yaml for the contract and DATA_MODEL.md for what is stored in MongoDB.
"""
import os
import re
from datetime import datetime, timedelta, timezone, date
from typing import Optional


from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator, model_validator
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
db = client[os.getenv("MONGO_DB", "attendance_db")]

IST = timezone(timedelta(hours=5, minutes=30))

app = FastAPI(title="Employee Attendance & Analytics API", version="2.0.0")

# Edited 1

@app.on_event("startup")
def create_indexes():
    db.employees.create_index("emp_code", unique=True)
    db.attendance_logs.create_index(
        [("emp_code", 1), ("date", 1)],
        unique=True
    )
    db.attendance_logs.create_index(
        [("date", -1), ("emp_code", 1)]
    )
    db.attendance_logs.create_index(
        [("status", 1), ("date", -1)]
    )

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def compute_late_minutes(punch_in: datetime, shift_start: str) -> int:
    h, m = map(int, shift_start.split(":"))
    start = punch_in.replace(hour=h, minute=m, second=0, microsecond=0)
    minutes = int((punch_in - start).total_seconds() / 60)
    return minutes if minutes > 10 else 0


def compute_work_hours(punch_in: datetime, punch_out: datetime) -> float:
    return round((punch_out - punch_in).total_seconds() / 3600, 2)


def compute_overtime(punch_out: datetime, shift_end: str, date_str: str) -> int:
    h, m = map(int, shift_end.split(":"))
    end = datetime.fromisoformat(date_str).replace(hour=h, minute=m, tzinfo=IST)
    return max(0, int((punch_out - end).total_seconds() / 60))


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
# class EmployeeIn(BaseModel):
#     emp_code: str
#     name: str
#     email: str
#     department: str
#     shift_start: str = "09:30"
#     shift_end: str = "18:30"
#     joined_on: str

# Edited 5

class EmployeeIn(BaseModel):
    emp_code: str
    name: str
    email: str
    department: str
    shift_start: str = "09:30"
    shift_end: str = "18:30"
    joined_on: str

    @field_validator("emp_code")
    @classmethod
    def validate_emp_code(cls, value):
        if not re.fullmatch(r"EMP\d{4,6}", value):
            raise ValueError(
                "emp_code must match EMP followed by 4 to 6 digits"
            )
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        if len(value) < 1 or len(value) > 100:
            raise ValueError("name must contain 1 to 100 characters")
        return value

    @field_validator("department")
    @classmethod
    def validate_department(cls, value):
        if len(value) < 1 or len(value) > 50:
            raise ValueError(
                "department must contain 1 to 50 characters"
            )
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if len(value) > 120 or not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", value
        ):
            raise ValueError("Invalid email format")
        return value

    @field_validator("joined_on")
    @classmethod
    def validate_joined_on(cls, value):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("joined_on must use YYYY-MM-DD format")

        try:
            date.fromisoformat(value)
        except ValueError:
            raise ValueError("joined_on must be a valid calendar date")

        return value

    @field_validator("shift_start", "shift_end")
    @classmethod
    def validate_shift_time(cls, value):
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("Shift time must use HH:MM format")
        return value

    @model_validator(mode="after")
    def validate_shift(self):
        if self.shift_start == self.shift_end:
            raise ValueError("shift_start and shift_end must differ")
        return self

class PunchInIn(BaseModel):
    emp_code: str
    punched_at: Optional[int] = None
    status: str = "PRESENT"


# --------------------------------------------------------------------------- #
# Endpoints provided
# --------------------------------------------------------------------------- #
# @app.get("/health")
# def health():
#     return {"status": "ok"}

# Edited 2


@app.get("/health")
def health():
    try:
        db.command("ping")
        return {"status": "ok"}
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="MongoDB unavailable"
        )


# @app.post("/employees", status_code=201)
# def create_employee(body: EmployeeIn):
#     if db.employees.find_one({"emp_code": body.emp_code}):
#         raise HTTPException(409, "emp_code already exists")
#     doc = body.model_dump()
#     doc["created_at"] = datetime.now()
#     db.employees.insert_one(doc)
#     doc.pop("_id", None)
#     return doc

# Edited 3


@app.post("/employees", status_code=201)
def create_employee(body: EmployeeIn):
    if db.employees.find_one({"emp_code": body.emp_code}):
        raise HTTPException(
            status_code=409,
            detail="emp_code already exists"
        )

    doc = body.model_dump()
    created_at = datetime.now(timezone.utc)
    doc["created_at"] = created_at

    try:
        db.employees.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="emp_code already exists"
        )

    doc.pop("_id", None)

    # Return epoch milliseconds in the API response
    doc["created_at"] = int(created_at.timestamp() * 1000)

    return doc

# @app.get("/employees")
# def list_employees(department: Optional[str] = None, page: int = 1, page_size: int = 20):
#     q = {}
#     if department:
#         q["department"] = department
#     skip = (page-1) * page_size
#     total = db.employees.count_documents(q)
#     items = list(db.employees.find(q, {"_id": 0}).skip(skip).limit(page_size))
#     return {"items": items, "total": total, "page": page, "page_size": page_size}

# Edited 4



@app.get("/employees")
def list_employees(
    department: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be at least 1")

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=422,
            detail="page_size must be between 1 and 100"
        )

    query = {}
    if department:
        query["department"] = department

    total = db.employees.count_documents(query)

    items = list(
        db.employees.find(query, {"_id": 0})
        .sort("emp_code", 1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    # Convert MongoDB datetime values to epoch milliseconds for the API.
    for item in items:
        if isinstance(item.get("created_at"), datetime):
            item["created_at"] = int(
                item["created_at"].replace(tzinfo=timezone.utc).timestamp() * 1000
            )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@app.post("/attendance/punch-in", status_code=201)
def punch_in(body: PunchInIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})

    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Convert epoch milliseconds to UTC, truncated to whole seconds.
    punched_at_utc = datetime.fromtimestamp(
        body.punched_at // 1000, tz=timezone.utc
    )

    # Use IST to determine the attendance date.
    punched_at_ist = punched_at_utc.astimezone(IST)
    shift_start = emp["shift_start"]
    shift_end = emp["shift_end"]

    attendance_date = punched_at_ist.date()

    # For overnight shifts, early-morning punches belong to
    # the previous attendance date.
    if shift_end <= shift_start and punched_at_ist.strftime("%H:%M") < shift_end:
        attendance_date -= timedelta(days=1)

    date_str = attendance_date.isoformat()

    doc = {
        "emp_code": body.emp_code,
        "date": date_str,
        "status": body.status,
        "punch_in": punched_at_utc,
        "punch_out": None,
        "work_hours": None,
        "late_minutes": 0,
        "overtime_minutes": 0,
        "half_day": False,
        "history": [],
    }

    # Calculate lateness against the scheduled shift start.
    start_hour, start_minute = map(int, shift_start.split(":"))
    scheduled_start = datetime.combine(
        attendance_date,
        datetime.min.time(),
        tzinfo=IST
    ).replace(hour=start_hour, minute=start_minute)

    elapsed_minutes = int(
        (punched_at_ist - scheduled_start).total_seconds() // 60
    )

    if elapsed_minutes > 10:
        doc["late_minutes"] = elapsed_minutes

    try:
        result = db.attendance_logs.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="Attendance record already exists for this date"
        )

    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)

    # API timestamps are epoch milliseconds.
    doc["punch_in"] = int(punched_at_utc.timestamp() * 1000)

    return doc



class PunchOutIn(BaseModel):
    emp_code: str
    punched_at: int

    @field_validator("punched_at", mode="before")
    @classmethod
    def validate_punched_at(cls, value):
        if type(value) is not int:
            raise ValueError(
                "punched_at must be an integer in milliseconds"
            )

        if not 100000000000 <= value <= 4102444800000:
            raise ValueError("punched_at is outside the allowed range")

        return value


class AttendancePatchIn(BaseModel):
    status: Optional[str] = None
    punch_in: Optional[int] = None
    punch_out: Optional[int] = None
    reason: str
    regularized_by: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value not in {
            "PRESENT", "WFH", "ON_DUTY", "ABSENT", "LEAVE"
        }:
            raise ValueError("Invalid attendance status")
        return value

    @field_validator("punch_in", "punch_out", mode="before")
    @classmethod
    def validate_timestamp(cls, value):
        if value is None:
            return value

        if type(value) is not int:
            raise ValueError("Timestamp must be integer epoch milliseconds")

        if not 100000000000 <= value <= 4102444800000:
            raise ValueError("Timestamp is outside the allowed range")

        return value

    @field_validator("reason", "regularized_by")
    @classmethod
    def validate_required_text(cls, value):
        if not value.strip():
            raise ValueError("This field cannot be empty")
        return value.strip()

    @model_validator(mode="after")
    def validate_fields(self):
        if (
            self.status is None
            and self.punch_in is None
            and self.punch_out is None
        ):
            raise ValueError("Provide at least one field to update")
        return self


@app.get("/attendance")
def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    if page < 1:
        raise HTTPException(
            status_code=422,
            detail="page must be at least 1"
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=422,
            detail="page_size must be between 1 and 100"
        )

    # Validate date filters.
    for field_name, value in (
        ("date_from", date_from),
        ("date_to", date_to)
    ):
        if value is not None:
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError()
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail=f"{field_name} must be a valid YYYY-MM-DD date"
                )

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be on or before date_to"
        )

    query = {}

    if emp_code:
        query["emp_code"] = emp_code

    if status:
        query["status"] = status

    if date_from or date_to:
        query["date"] = {}
        if date_from:
            query["date"]["$gte"] = date_from
        if date_to:
            query["date"]["$lte"] = date_to

    total = db.attendance_logs.count_documents(query)

    docs = list(
        db.attendance_logs.find(query, {"_id": 0})
        .sort([("date", -1), ("emp_code", 1)])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    # Convert BSON datetimes to epoch milliseconds for the API.
    for item in docs:
        item["id"] = str(
            db.attendance_logs.find_one(
                {
                    "emp_code": item["emp_code"],
                    "date": item["date"]
                },
                {"_id": 1}
            )["_id"]
        )

        for field in ("punch_in", "punch_out"):
            value = item.get(field)
            if isinstance(value, datetime):
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                item[field] = int(value.timestamp() * 1000)

        for entry in item.get("history", []):
            if isinstance(entry.get("at"), datetime):
                value = entry["at"]
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                entry["at"] = int(value.timestamp() * 1000)

            for change in entry.get("changes", {}).values():
                if isinstance(change, dict):
                    for key in ("from", "to"):
                        value = change.get(key)
                        if isinstance(value, datetime):
                            if value.tzinfo is None:
                                value = value.replace(tzinfo=timezone.utc)
                            change[key] = int(value.timestamp() * 1000)

    return {
        "items": docs,
        "total": total,
        "page": page,
        "page_size": page_size
    }



@app.post("/attendance/punch-out")
def punch_out(body: PunchOutIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})

    if not emp:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    # Convert epoch milliseconds to UTC, truncated to whole seconds.
    punched_at_utc = datetime.fromtimestamp(
        body.punched_at // 1000,
        tz=timezone.utc
    )

    # Find the most recent eligible open attendance record.
    record = db.attendance_logs.find_one(
        {
            "emp_code": body.emp_code,
            "punch_in": {"$lte": punched_at_utc},
            "punch_out": None
        },
        sort=[("punch_in", -1)]
    )

    if not record:
        previous = db.attendance_logs.find_one(
            {
                "emp_code": body.emp_code,
                "punch_in": {"$lte": punched_at_utc}
            },
            sort=[("punch_in", -1)]
        )

        if previous and previous.get("punch_out") is not None:
            raise HTTPException(
                status_code=409,
                detail="Attendance already punched out"
            )

        raise HTTPException(
            status_code=404,
            detail="No eligible open punch-in found"
        )

    # MongoDB may return naive datetimes; treat them as UTC.
    punch_in_utc = record["punch_in"]
    if punch_in_utc.tzinfo is None:
        punch_in_utc = punch_in_utc.replace(tzinfo=timezone.utc)

    if punched_at_utc <= punch_in_utc:
        raise HTTPException(
            status_code=422,
            detail="Punch-out must be after punch-in"
        )

    elapsed_seconds = (
        punched_at_utc - punch_in_utc
    ).total_seconds()

    if elapsed_seconds > 24 * 60 * 60:
        raise HTTPException(
            status_code=422,
            detail="Punch-out cannot be more than 24 hours after punch-in"
        )

    # Calculate work hours using half-up rounding to 2 decimals.
    from decimal import Decimal, ROUND_HALF_UP

    work_hours = float(
        (Decimal(str(elapsed_seconds)) / Decimal("3600")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    )

    half_day = work_hours < 4.50

    # Calculate the scheduled shift-end instant in IST.
    attendance_date = date.fromisoformat(record["date"])
    end_hour, end_minute = map(int, emp["shift_end"].split(":"))

    scheduled_end = datetime(
        attendance_date.year,
        attendance_date.month,
        attendance_date.day,
        end_hour,
        end_minute,
        tzinfo=IST
    )

    # For overnight shifts, shift end falls on the following date.
    if emp["shift_end"] <= emp["shift_start"]:
        scheduled_end += timedelta(days=1)

    punch_out_ist = punched_at_utc.astimezone(IST)
    overtime_seconds = (
        punch_out_ist - scheduled_end
    ).total_seconds()

    # Overtime counts only when at least 30 minutes beyond shift end.
    overtime_minutes = (
        int(overtime_seconds // 60)
        if overtime_seconds >= 30 * 60
        else 0
    )

    # Atomically update the still-open record to prevent concurrent
    # punch-out requests from overwriting one another.
    result = db.attendance_logs.update_one(
        {
            "_id": record["_id"],
            "punch_out": None,
            "punch_in": {"$lte": punched_at_utc}
        },
        {
            "$set": {
                "punch_out": punched_at_utc,
                "work_hours": work_hours,
                "half_day": half_day,
                "overtime_minutes": overtime_minutes
            }
        }
    )

    if result.modified_count != 1:
        raise HTTPException(
            status_code=409,
            detail="Attendance was already punched out"
        )

    updated = db.attendance_logs.find_one(
        {"_id": record["_id"]},
        {"_id": 0}
    )

    updated["id"] = str(record["_id"])

    # Return API timestamps as epoch milliseconds.
    updated["punch_in"] = int(punch_in_utc.timestamp() * 1000)
    updated["punch_out"] = int(punched_at_utc.timestamp() * 1000)

    return updated


# --------------------------------------------------------------------------- #
# TODO - the rest of the contract (see openapi.yaml):
#   POST  /attendance/punch-out
#   PATCH /attendance/{emp_code}/{date}
#   GET   /analytics/employees/{emp_code}/monthly
#   GET   /analytics/departments/summary
#   GET   /analytics/leaderboard/late
#   GET   /analytics/departments/{department}/trend
#   GET   /admin/explain/{endpoint}
# --------------------------------------------------------------------------- #



@app.patch("/attendance/{emp_code}/{date_str}")
def regularize_attendance(
    emp_code: str,
    date_str: str,
    body: AttendancePatchIn
):
    from decimal import Decimal, ROUND_HALF_UP

    # Validate the attendance date.
    try:
        if date.fromisoformat(date_str).isoformat() != date_str:
            raise ValueError()
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="date must use YYYY-MM-DD format"
        )

    # Find the employee and attendance record.
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    record = db.attendance_logs.find_one({
        "emp_code": emp_code,
        "date": date_str
    })
    if not record:
        raise HTTPException(
            status_code=404,
            detail="Attendance record not found"
        )

    # Determine the final values after applying the requested changes.
    old_status = record.get("status")
    old_in = record.get("punch_in")
    old_out = record.get("punch_out")

    new_status = body.status if body.status is not None else old_status

    def normalize_datetime(value):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    old_in = normalize_datetime(old_in)
    old_out = normalize_datetime(old_out)

    new_in = (
        datetime.fromtimestamp(body.punch_in // 1000, timezone.utc)
        if body.punch_in is not None else old_in
    )
    new_out = (
        datetime.fromtimestamp(body.punch_out // 1000, timezone.utc)
        if body.punch_out is not None else old_out
    )

    presence_statuses = {"PRESENT", "WFH", "ON_DUTY"}

    # ABSENT and LEAVE cannot have punch times.
    if new_status in {"ABSENT", "LEAVE"}:
        if body.punch_in is not None or body.punch_out is not None:
            raise HTTPException(
                status_code=422,
                detail="ABSENT and LEAVE cannot include punch times"
            )
        new_in = None
        new_out = None

    # Presence statuses require a punch-in.
    elif new_status in presence_statuses:
        if new_in is None:
            raise HTTPException(
                status_code=422,
                detail="Presence status requires punch_in"
            )

    else:
        raise HTTPException(
            status_code=422,
            detail="Invalid attendance status"
        )

    # Punch-in must belong to the attendance date in IST.
    if new_in is not None:
        if new_in.astimezone(IST).date().isoformat() != date_str:
            raise HTTPException(
                status_code=422,
                detail="punch_in must fall on the attendance date in IST"
            )

    # Validate punch-out relative to punch-in.
    if new_out is not None:
        if new_in is None:
            raise HTTPException(
                status_code=422,
                detail="punch_out requires punch_in"
            )
        elapsed_seconds = (new_out - new_in).total_seconds()
        if elapsed_seconds <= 0:
            raise HTTPException(
                status_code=422,
                detail="punch_out must be after punch_in"
            )
        if elapsed_seconds > 24 * 60 * 60:
            raise HTTPException(
                status_code=422,
                detail="punch_out cannot be more than 24 hours after punch_in"
            )

    # Record only actual changes to the editable fields.
    changes = {}

    if new_status != old_status:
        changes["status"] = {"from": old_status, "to": new_status}

    if new_in != old_in:
        changes["punch_in"] = {"from": old_in, "to": new_in}

    if new_out != old_out:
        changes["punch_out"] = {"from": old_out, "to": new_out}

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="The requested changes do not modify the record"
        )

    # Recalculate all derived fields.
    work_hours = None
    half_day = False
    late_minutes = 0
    overtime_minutes = 0

    if new_status in presence_statuses and new_in is not None:
        punch_in_ist = new_in.astimezone(IST)
        start_hour, start_minute = map(
            int, emp["shift_start"].split(":")
        )

        scheduled_start = datetime(
            date.fromisoformat(date_str).year,
            date.fromisoformat(date_str).month,
            date.fromisoformat(date_str).day,
            start_hour,
            start_minute,
            tzinfo=IST
        )

        late_elapsed = int(
            (punch_in_ist - scheduled_start).total_seconds() // 60
        )
        if late_elapsed > 10:
            late_minutes = late_elapsed

        if new_out is not None:
            elapsed_seconds = (new_out - new_in).total_seconds()

            work_hours = float(
                (Decimal(str(elapsed_seconds)) / Decimal("3600")).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )
            )
            half_day = work_hours < 4.50

            end_hour, end_minute = map(
                int, emp["shift_end"].split(":")
            )
            scheduled_end = datetime(
                date.fromisoformat(date_str).year,
                date.fromisoformat(date_str).month,
                date.fromisoformat(date_str).day,
                end_hour,
                end_minute,
                tzinfo=IST
            )

            if emp["shift_end"] <= emp["shift_start"]:
                scheduled_end += timedelta(days=1)

            overtime_seconds = (
                new_out.astimezone(IST) - scheduled_end
            ).total_seconds()

            if overtime_seconds >= 30 * 60:
                overtime_minutes = int(overtime_seconds // 60)

    # Add the audit entry atomically with the update.
    history_entry = {
        "at": datetime.now(timezone.utc),
        "regularized_by": body.regularized_by,
        "reason": body.reason,
        "changes": changes
    }

    # Compare original values so concurrent edits cannot silently
    # overwrite each other or lose audit history.
    update_filter = {
        "_id": record["_id"],
        "status": record.get("status"),
        "punch_in": record.get("punch_in"),
        "punch_out": record.get("punch_out")
    }

    result = db.attendance_logs.update_one(
        update_filter,
        {
            "$set": {
                "status": new_status,
                "punch_in": new_in,
                "punch_out": new_out,
                "work_hours": work_hours,
                "half_day": half_day,
                "late_minutes": late_minutes,
                "overtime_minutes": overtime_minutes
            },
            "$push": {"history": history_entry}
        }
    )

    if result.modified_count != 1:
        raise HTTPException(
            status_code=409,
            detail="Attendance was changed concurrently; retry the request"
        )

    updated = db.attendance_logs.find_one({"_id": record["_id"]})
    updated["id"] = str(updated.pop("_id"))

    # Convert stored BSON datetimes to epoch milliseconds for the API.
    def to_epoch_ms(value):
        if value is None:
            return None
        value = normalize_datetime(value)
        return int(value.timestamp() * 1000)

    for field in ("punch_in", "punch_out"):
        updated[field] = to_epoch_ms(updated.get(field))

    for entry in updated.get("history", []):
        entry["at"] = to_epoch_ms(entry.get("at"))

        for change in entry.get("changes", {}).values():
            if isinstance(change, dict):
                for key in ("from", "to"):
                    if isinstance(change.get(key), datetime):
                        change[key] = to_epoch_ms(change[key])

    return updated



from decimal import Decimal, ROUND_HALF_UP
import re
from calendar import monthrange
from datetime import date


@app.get("/analytics/employees/{emp_code}/monthly")
def employee_monthly_analytics(emp_code: str, month: str):
    import re
    from calendar import monthrange
    from decimal import Decimal, ROUND_HALF_UP

    # 1. Validate month format
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(
            status_code=422,
            detail="month must be in YYYY-MM format"
        )

    year, month_number = map(int, month.split("-"))

    if not 1 <= month_number <= 12:
        raise HTTPException(
            status_code=422,
            detail="Invalid month"
        )

    month_start = date(year, month_number, 1)
    month_end = date(
        year,
        month_number,
        monthrange(year, month_number)[1]
    )

    # 2. Find employee
    employee = db.employees.find_one(
        {"emp_code": emp_code},
        {"_id": 0, "emp_code": 1, "joined_on": 1}
    )

    if employee is None:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    # 3. Convert joined_on to a Python date
    joined_on = employee["joined_on"]

    if isinstance(joined_on, datetime):
        joined_on = joined_on.date()
    elif isinstance(joined_on, str):
        try:
            joined_on = date.fromisoformat(joined_on)
        except ValueError:
            raise HTTPException(
                status_code=500,
                detail="Invalid employee joined_on date in database"
            )

    # 4. Calculate weekdays from joining date through month end
    first_day = max(month_start, joined_on)
    working_days = 0

    if first_day <= month_end:
        current_day = first_day

        while current_day <= month_end:
            if current_day.weekday() < 5:
                working_days += 1

            current_day += timedelta(days=1)

    # 5. Aggregate attendance records in MongoDB
    pipeline = [
        {
            "$match": {
                "emp_code": emp_code,
                "date": {
                    "$gte": month_start.isoformat(),
                    "$lte": month_end.isoformat()
                }
            }
        },
        {
            "$set": {
                "parsed_date": {
                    "$dateFromString": {
                        "dateString": "$date",
                        "format": "%Y-%m-%d",
                        "timezone": "Asia/Kolkata"
                    }
                }
            }
        },
        {
            "$set": {
                "is_weekday": {
                    "$and": [
                        {"$gte": [{"$dayOfWeek": "$parsed_date"}, 2]},
                        {"$lte": [{"$dayOfWeek": "$parsed_date"}, 6]}
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": None,

                "present_days": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {
                                        "$in": [
                                            "$status",
                                            ["PRESENT", "WFH", "ON_DUTY"]
                                        ]
                                    },
                                    "$is_weekday"
                                ]
                            },
                            {
                                "$cond": [
                                    {"$eq": [
                                        {"$ifNull": ["$half_day", False]},
                                        True
                                    ]},
                                    0.5,
                                    1
                                ]
                            },
                            0
                        ]
                    }
                },

                "leave_days": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$status", "LEAVE"]},
                            1,
                            0
                        ]
                    }
                },

                "late_count": {
                    "$sum": {
                        "$cond": [
                            {
                                "$gt": [
                                    {"$ifNull": ["$late_minutes", 0]},
                                    0
                                ]
                            },
                            1,
                            0
                        ]
                    }
                },

                "total_late_minutes": {
                    "$sum": {"$ifNull": ["$late_minutes", 0]}
                },

                "total_overtime_minutes": {
                    "$sum": {"$ifNull": ["$overtime_minutes", 0]}
                }
            }
        }
    ]

    results = list(db.attendance_logs.aggregate(pipeline))
    stats = results[0] if results else {}

    present_days = stats.get("present_days", 0)
    leave_days = stats.get("leave_days", 0)
    late_count = stats.get("late_count", 0)
    total_late_minutes = stats.get("total_late_minutes", 0)
    total_overtime_minutes = stats.get("total_overtime_minutes", 0)

    # 6. Calculate attendance percentage using half-up rounding
    attendance_pct = None

    if working_days > 0:
        percentage = (
            Decimal(str(present_days))
            * Decimal("100")
            / Decimal(str(working_days))
        )

        attendance_pct = float(
            percentage.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )
        )

    # 7. Return monthly analytics
    return {
        "emp_code": emp_code,
        "month": month,
        "working_days": working_days,
        "present_days": present_days,
        "leave_days": leave_days,
        "late_count": late_count,
        "total_late_minutes": total_late_minutes,
        "total_overtime_minutes": total_overtime_minutes,
        "attendance_pct": attendance_pct
    }



@app.get("/analytics/departments/summary")
def department_summary_analytics(
    month: str,
    department: Optional[str] = None
):
    import re
    from calendar import monthrange
    from decimal import Decimal, ROUND_HALF_UP

    # 1. Validate month
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(
            status_code=422,
            detail="month must be in YYYY-MM format"
        )

    year, month_number = map(int, month.split("-"))

    if not 1 <= month_number <= 12:
        raise HTTPException(
            status_code=422,
            detail="Invalid month"
        )

    month_start = date(year, month_number, 1)
    month_end = date(
        year,
        month_number,
        monthrange(year, month_number)[1]
    )

    # 2. Convert joining dates that may be strings or datetimes
    def as_date(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return date.fromisoformat(value)
        return value

    # 3. Get employees who joined on or before month end
    employee_query = {}

    if department:
        employee_query["department"] = department

    employees = list(
        db.employees.find(
            employee_query,
            {
                "_id": 0,
                "emp_code": 1,
                "department": 1,
                "joined_on": 1
            }
        )
    )

    headcounts = {}

    for employee in employees:
        joined_on = as_date(employee["joined_on"])

        if joined_on <= month_end:
            dept = employee["department"]
            headcounts[dept] = headcounts.get(dept, 0) + 1

    # Include departments with zero attendance logs
    department_names = sorted(headcounts.keys())

    if department:
        department_names = sorted(set(department_names + [department]))

    # 4. Aggregate monthly attendance in MongoDB
    pipeline = [
        {
            "$match": {
                "date": {
                    "$gte": month_start.isoformat(),
                    "$lte": month_end.isoformat()
                }
            }
        },
        {
            "$lookup": {
                "from": "employees",
                "localField": "emp_code",
                "foreignField": "emp_code",
                "as": "employee"
            }
        },
        {"$unwind": "$employee"},
        {
            "$match": {
                "employee.joined_on": {"$lte": month_end.isoformat()}
            }
        },
        {
            "$match": (
                {"employee.department": department}
                if department else {}
            )
        },
        {
            "$group": {
                "_id": "$employee.department",

                "present_days": {
                    "$sum": {
                        "$cond": [
                            {
                                "$in": [
                                    "$status",
                                    ["PRESENT", "WFH", "ON_DUTY"]
                                ]
                            },
                            {
                                "$cond": [
                                    {"$eq": [
                                        {"$ifNull": ["$half_day", False]},
                                        True
                                    ]},
                                    0.5,
                                    1
                                ]
                            },
                            0
                        ]
                    }
                },

                "work_hours_sum": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {
                                        "$in": [
                                            "$status",
                                            ["PRESENT", "WFH", "ON_DUTY"]
                                        ]
                                    },
                                    {"$ne": ["$work_hours", None]}
                                ]
                            },
                            "$work_hours",
                            0
                        ]
                    }
                },

                "work_hours_count": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {
                                        "$in": [
                                            "$status",
                                            ["PRESENT", "WFH", "ON_DUTY"]
                                        ]
                                    },
                                    {"$ne": ["$work_hours", None]}
                                ]
                            },
                            1,
                            0
                        ]
                    }
                },

                "late_count": {
                    "$sum": {
                        "$cond": [
                            {"$gt": [
                                {"$ifNull": ["$late_minutes", 0]}, 0
                            ]},
                            1,
                            0
                        ]
                    }
                },

                "total_late_minutes": {
                    "$sum": {"$ifNull": ["$late_minutes", 0]}
                },

                "leave_count": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$status", "LEAVE"]},
                            1,
                            0
                        ]
                    }
                },

                "on_duty_count": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$status", "ON_DUTY"]},
                            1,
                            0
                        ]
                    }
                }
            }
        }
    ]

    attendance_results = list(
        db.attendance_logs.aggregate(pipeline)
    )

    attendance_by_department = {
        item["_id"]: item for item in attendance_results
    }

    # 5. Return one item per department
    response = []

    for dept in department_names:
        stats = attendance_by_department.get(dept, {})

        present_days = stats.get("present_days", 0)
        work_hours_sum = stats.get("work_hours_sum", 0)
        work_hours_count = stats.get("work_hours_count", 0)

        avg_work_hours = None

        if work_hours_count > 0:
            avg_work_hours = float(
                (
                    Decimal(str(work_hours_sum))
                    / Decimal(str(work_hours_count))
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )
            )

        response.append({
            "department": dept,
            "headcount": headcounts.get(dept, 0),
            "present_days": present_days,
            "avg_work_hours": avg_work_hours,
            "late_count": stats.get("late_count", 0),
            "total_late_minutes": stats.get(
                "total_late_minutes", 0
            ),
            "leave_count": stats.get("leave_count", 0),
            "on_duty_count": stats.get("on_duty_count", 0)
        })

    return response



@app.get("/analytics/leaderboard/late")
def late_leaderboard(
    month: str,
    limit: int = 10,
    department: Optional[str] = None
):
    import re
    from calendar import monthrange

    # 1. Validate month
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(
            status_code=422,
            detail="month must be in YYYY-MM format"
        )

    year, month_number = map(int, month.split("-"))

    if not 1 <= month_number <= 12:
        raise HTTPException(
            status_code=422,
            detail="Invalid month"
        )

    # 2. Validate limit
    if not 1 <= limit <= 50:
        raise HTTPException(
            status_code=422,
            detail="limit must be between 1 and 50"
        )

    month_start = date(year, month_number, 1)
    month_end = date(
        year,
        month_number,
        monthrange(year, month_number)[1]
    )

    # 3. Build MongoDB aggregation pipeline
    pipeline = [
        {
            "$match": {
                "date": {
                    "$gte": month_start.isoformat(),
                    "$lte": month_end.isoformat()
                }
            }
        },
        {
            "$group": {
                "_id": "$emp_code",
                "total_late_minutes": {
                    "$sum": {"$ifNull": ["$late_minutes", 0]}
                }
            }
        },
        {
            "$match": {
                "total_late_minutes": {"$gt": 0}
            }
        },
        {
            "$lookup": {
                "from": "employees",
                "localField": "_id",
                "foreignField": "emp_code",
                "as": "employee"
            }
        },
        {"$unwind": "$employee"},
        {
            "$match": (
                {"employee.department": department}
                if department else {}
            )
        },
        {
            "$set": {
                "emp_code": "$_id",
                "department": "$employee.department"
            }
        },
        {
            "$setWindowFields": {
                "sortBy": {
                    "total_late_minutes": -1
                },
                "output": {
                    "rank": {
                        "$rank": {}
                    }
                }
            }
        },
        {
            "$match": {
                "rank": {"$lte": limit}
            }
        },
        {
            "$sort": {
                "total_late_minutes": -1,
                "emp_code": 1
            }
        },
        {
            "$project": {
                "_id": 0,
                "emp_code": 1,
                "department": 1,
                "total_late_minutes": 1,
                "rank": 1
            }
        }
    ]

    return list(db.attendance_logs.aggregate(pipeline))



@app.get("/analytics/departments/{department}/trend")
def department_attendance_trend(
    department: str,
    from_date: str = Query(alias="from"),
    to_date: str = Query(alias="to")
):
    import re
    from decimal import Decimal, ROUND_HALF_UP

    # Validate required date query parameters
    if from_date is None or to_date is None:
        raise HTTPException(
            status_code=422,
            detail="Both from and to query parameters are required"
        )

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", from_date):
        raise HTTPException(
            status_code=422,
            detail="from must use YYYY-MM-DD format"
        )

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", to_date):
        raise HTTPException(
            status_code=422,
            detail="to must use YYYY-MM-DD format"
        )

    try:
        start_date = date.fromisoformat(from_date)
        end_date = date.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Invalid calendar date"
        )

    if start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="from must be on or before to"
        )

    if (end_date - start_date).days + 1 > 92:
        raise HTTPException(
            status_code=422,
            detail="Date range cannot exceed 92 days"
        )

    # Check that the department exists
    if db.employees.count_documents({"department": department}) == 0:
        raise HTTPException(
            status_code=404,
            detail="Department not found"
        )

    # Load attendance records for the requested dates
    records = list(
        db.attendance_logs.find(
            {
                "date": {
                    "$gte": start_date.isoformat(),
                    "$lte": end_date.isoformat()
                }
            },
            {
                "_id": 0,
                "emp_code": 1,
                "date": 1,
                "status": 1,
                "half_day": 1,
                "late_minutes": 1
            }
        )
    )

    # Map employee codes to departments and joining dates
    employees = list(
        db.employees.find(
            {"department": department},
            {
                "_id": 0,
                "emp_code": 1,
                "joined_on": 1
            }
        )
    )

    employee_info = {}

    for employee in employees:
        joined_on = employee["joined_on"]

        if isinstance(joined_on, datetime):
            joined_on = joined_on.date()
        elif isinstance(joined_on, str):
            joined_on = date.fromisoformat(joined_on)

        employee_info[employee["emp_code"]] = joined_on

    # Group attendance records by date for this department
    daily = {}

    for record in records:
        emp_code = record["emp_code"]

        if emp_code not in employee_info:
            continue

        joined_on = employee_info[emp_code]
        record_date = date.fromisoformat(record["date"])

        if joined_on > record_date:
            continue

        key = record["date"]
        if key not in daily:
            daily[key] = {
                "present_count": 0.0,
                "late_count": 0
            }

        if record.get("status") in {"PRESENT", "WFH", "ON_DUTY"}:
            daily[key]["present_count"] += (
                0.5 if record.get("half_day", False) else 1.0
            )

        if record.get("late_minutes", 0) > 0:
            daily[key]["late_count"] += 1

    # Create a row for every date, including weekends and no-log dates
    result = []
    current_date = start_date

    while current_date <= end_date:
        key = current_date.isoformat()
        is_working_day = current_date.weekday() < 5

        headcount = sum(
            1 for joined_on in employee_info.values()
            if joined_on <= current_date
        )

        stats = daily.get(
            key,
            {"present_count": 0.0, "late_count": 0}
        )

        attendance_rate = None

        if is_working_day and headcount > 0:
            rate = (
                Decimal(str(stats["present_count"]))
                / Decimal(str(headcount))
            )

            attendance_rate = float(
                rate.quantize(
                    Decimal("0.0001"),
                    rounding=ROUND_HALF_UP
                )
            )

        result.append({
            "date": key,
            "is_working_day": is_working_day,
            "headcount": headcount,
            "present_count": stats["present_count"],
            "late_count": stats["late_count"],
            "attendance_rate": attendance_rate
        })

        current_date += timedelta(days=1)

    # Calculate moving average across current and previous six rows
    for i, row in enumerate(result):
        window = result[max(0, i - 6):i + 1]

        valid_rates = [
            item["attendance_rate"]
            for item in window
            if item["attendance_rate"] is not None
        ]

        row["moving_avg_7d"] = (
            round(sum(valid_rates) / len(valid_rates), 4)
            if valid_rates else None
        )

    return result


@app.get("/admin/explain/{endpoint}")
def explain_query(
    endpoint: str,
    month: str = None,
    department: str = None,
    emp_code: str = None,
    date_from: str = None,
    date_to: str = None,
    status: str = None,
    page: int = 1,
    page_size: int = 20,
    limit: int = 10,
):
    from fastapi import HTTPException
    import re
    from datetime import date, datetime, timedelta, timezone

    allowed_endpoints = {
        "attendance_list",
        "employee_monthly",
        "department_summary",
        "late_leaderboard",
        "department_trend",
    }

    if endpoint not in allowed_endpoints:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported endpoint. Choose one of: {sorted(allowed_endpoints)}",
        )

    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=422,
            detail="page must be >= 1 and page_size must be between 1 and 100",
        )

    if limit < 1 or limit > 50:
        raise HTTPException(
            status_code=422,
            detail="limit must be between 1 and 50",
        )

    def parse_month(value):
        if not value or not re.fullmatch(r"\d{4}-\d{2}", value):
            raise HTTPException(
                status_code=422,
                detail="month must use YYYY-MM format",
            )
        try:
            return date.fromisoformat(value + "-01")
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Invalid month",
            )

    def month_bounds(value):
        first = parse_month(value)
        if first.month == 12:
            next_month = date(first.year + 1, 1, 1)
        else:
            next_month = date(first.year, first.month + 1, 1)

        ist = timezone(timedelta(hours=5, minutes=30))
        start = datetime.combine(first, datetime.min.time(), tzinfo=ist)
        end = datetime.combine(next_month, datetime.min.time(), tzinfo=ist)

        return (
            start.astimezone(timezone.utc).replace(tzinfo=None),
            end.astimezone(timezone.utc).replace(tzinfo=None),
        )

    if endpoint == "attendance_list":
        query = {}

        if emp_code:
            query["emp_code"] = emp_code

        if status:
            query["status"] = status

        if date_from or date_to:
            date_filter = {}

            if date_from:
                try:
                    parsed_from = date.fromisoformat(date_from)
                except ValueError:
                    raise HTTPException(
                        status_code=422,
                        detail="date_from must use YYYY-MM-DD format",
                    )

                date_filter["$gte"] = parsed_from.isoformat()

            if date_to:
                try:
                    parsed_to = date.fromisoformat(date_to)
                except ValueError:
                    raise HTTPException(
                        status_code=422,
                        detail="date_to must use YYYY-MM-DD format",
                    )

                date_filter["$lte"] = parsed_to.isoformat()

            if date_from and date_to and parsed_from > parsed_to:
                raise HTTPException(
                    status_code=422,
                    detail="date_from must not be after date_to",
                )

            query["date"] = date_filter

        explanation = db.command(
            "explain",
            {
                "find": "attendance_logs",
                "filter": query,
                "sort": {"date": -1, "emp_code": 1},
                "skip": (page - 1) * page_size,
                "limit": page_size,
            },
            verbosity="executionStats",
        )

    elif endpoint == "employee_monthly":
        if not emp_code or not month:
            raise HTTPException(
                status_code=422,
                detail="emp_code and month are required",
            )

        start, end = month_bounds(month)

        pipeline = [
            {
                "$match": {
                    "emp_code": emp_code,
                    "date": {
                        "$gte": start.date().isoformat(),
                        "$lt": end.date().isoformat(),
                    },
                }
            },
            {"$sort": {"date": 1}},
        ]

        explanation = db.command(
            "explain",
            {
                "aggregate": "attendance_logs",
                "pipeline": pipeline,
                "cursor": {},
            },
            verbosity="executionStats",
        )

    elif endpoint == "department_summary":
        if not month:
            raise HTTPException(
                status_code=422,
                detail="month is required",
            )

        start, end = month_bounds(month)

        pipeline = [
            {
                "$match": {
                    "date": {
                        "$gte": start.date().isoformat(),
                        "$lt": end.date().isoformat(),
                    }
                }
            },
            {
                "$lookup": {
                    "from": "employees",
                    "localField": "emp_code",
                    "foreignField": "emp_code",
                    "as": "employee",
                }
            },
            {"$unwind": "$employee"},
        ]

        if department:
            pipeline.append(
                {"$match": {"employee.department": department}}
            )

        pipeline.append(
            {
                "$group": {
                    "_id": "$employee.department",
                    "record_count": {"$sum": 1},
                }
            }
        )

        explanation = db.command(
            "explain",
            {
                "aggregate": "attendance_logs",
                "pipeline": pipeline,
                "cursor": {},
            },
            verbosity="executionStats",
        )

    elif endpoint == "late_leaderboard":
        if not month:
            raise HTTPException(
                status_code=422,
                detail="month is required",
            )

        start, end = month_bounds(month)

        pipeline = [
            {
                "$match": {
                    "date": {
                        "$gte": start.date().isoformat(),
                        "$lt": end.date().isoformat(),
                    }
                }
            },
            {
                "$group": {
                    "_id": "$emp_code",
                    "total_late_minutes": {
                        "$sum": {"$ifNull": ["$late_minutes", 0]}
                    },
                }
            },
            {"$match": {"total_late_minutes": {"$gt": 0}}},
            {
                "$lookup": {
                    "from": "employees",
                    "localField": "_id",
                    "foreignField": "emp_code",
                    "as": "employee",
                }
            },
            {"$unwind": "$employee"},
        ]

        if department:
            pipeline.append(
                {"$match": {"employee.department": department}}
            )

        pipeline.extend(
            [
                {
                    "$setWindowFields": {
                        "sortBy": {"total_late_minutes": -1},
                        "output": {
                            "rank": {"$rank": {}}
                        },
                    }
                },
                {"$match": {"rank": {"$lte": limit}}},
                {
                    "$sort": {
                        "total_late_minutes": -1,
                        "_id": 1,
                    }
                },
            ]
        )

        explanation = db.command(
            "explain",
            {
                "aggregate": "attendance_logs",
                "pipeline": pipeline,
                "cursor": {},
            },
            verbosity="executionStats",
        )

    else:  # department_trend
        if not department or not date_from or not date_to:
            raise HTTPException(
                status_code=422,
                detail="department, date_from and date_to are required",
            )

        try:
            start_date = date.fromisoformat(date_from)
            end_date = date.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Dates must use YYYY-MM-DD format",
            )

        if start_date > end_date:
            raise HTTPException(
                status_code=422,
                detail="date_from must not be after date_to",
            )

        if (end_date - start_date).days > 91:
            raise HTTPException(
                status_code=422,
                detail="Date range must not exceed 92 calendar days",
            )

        pipeline = [
            {
                "$match": {
                    "date": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat(),
                    }
                }
            },
            {
                "$lookup": {
                    "from": "employees",
                    "localField": "emp_code",
                    "foreignField": "emp_code",
                    "as": "employee",
                }
            },
            {"$unwind": "$employee"},
            {"$match": {"employee.department": department}},
            {"$sort": {"date": 1, "emp_code": 1}},
        ]

        explanation = db.command(
            "explain",
            {
                "aggregate": "attendance_logs",
                "pipeline": pipeline,
                "cursor": {},
            },
            verbosity="executionStats",
        )

    return explanation