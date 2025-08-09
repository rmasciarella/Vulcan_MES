"""
Holiday Calendar API Routes

Provides endpoints for accessing holiday calendar data for production scheduling.
"""

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlmodel import Session, select

from app.api.deps import get_db
from app.infrastructure.database.sqlmodel_entities import HolidayCalendar

router = APIRouter()


@router.get("/holidays", response_model=List[dict])
def get_holidays(
    *,
    db: Session = Depends(get_db),
    start_date: date | None = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date filter (YYYY-MM-DD)"),
    year: int | None = Query(None, description="Filter by year"),
) -> List[dict]:
    """
    Get holiday calendar data with optional date filtering.
    
    Used by scheduling algorithms to identify non-working days.
    """
    try:
        # Build the query
        statement = select(HolidayCalendar)
        
        # Apply filters
        if year:
            statement = statement.where(
                text("EXTRACT(year FROM holiday_date) = :year")
            ).params(year=year)
        else:
            if start_date:
                statement = statement.where(HolidayCalendar.holiday_date >= start_date)
            if end_date:
                statement = statement.where(HolidayCalendar.holiday_date <= end_date)
        
        # Order by date
        statement = statement.order_by(HolidayCalendar.holiday_date)
        
        holidays = db.exec(statement).all()
        
        # Convert to dict format for API response
        return [
            {
                "holiday_id": holiday.holiday_id,
                "holiday_date": holiday.holiday_date.isoformat(),
                "name": holiday.name,
                "created_at": holiday.created_at.isoformat(),
                "updated_at": holiday.updated_at.isoformat()
            }
            for holiday in holidays
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve holiday data: {str(e)}"
        )


@router.get("/holidays/{holiday_date}")
def get_holiday_by_date(
    *,
    db: Session = Depends(get_db),
    holiday_date: date,
) -> dict | None:
    """
    Check if a specific date is a holiday.
    
    Returns holiday information if the date is a holiday, null otherwise.
    """
    try:
        holiday = db.exec(
            select(HolidayCalendar)
            .where(HolidayCalendar.holiday_date == holiday_date)
        ).first()
        
        if not holiday:
            return None
            
        return {
            "holiday_id": holiday.holiday_id,
            "holiday_date": holiday.holiday_date.isoformat(),
            "name": holiday.name,
            "created_at": holiday.created_at.isoformat(),
            "updated_at": holiday.updated_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check holiday date: {str(e)}"
        )


@router.get("/is-working-day/{check_date}")
def is_working_day(
    *,
    db: Session = Depends(get_db),
    check_date: date,
) -> dict:
    """
    Check if a date is a working day (not a holiday and not a weekend).
    
    Returns working day status for scheduling calculations.
    """
    try:
        # Check if it's a holiday
        holiday = db.exec(
            select(HolidayCalendar)
            .where(HolidayCalendar.holiday_date == check_date)
        ).first()
        
        is_holiday = holiday is not None
        
        # Check if it's a weekend (Saturday = 5, Sunday = 6)
        is_weekend = check_date.weekday() >= 5
        
        is_working = not (is_holiday or is_weekend)
        
        return {
            "date": check_date.isoformat(),
            "is_working_day": is_working,
            "is_holiday": is_holiday,
            "is_weekend": is_weekend,
            "holiday_name": holiday.name if holiday else None,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check working day status: {str(e)}"
        )