"""
Operator load and availability read models with shift pattern analysis.

Provides optimized queries for operator workload balancing, availability forecasting,
and capacity planning with skill-based resource allocation insights.
"""

from datetime import datetime, timedelta, time, date
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session


class ShiftPattern(str, Enum):
    """Common shift patterns for analysis."""
    DAY_SHIFT = "day_shift"      # 6:00-14:00
    EVENING_SHIFT = "evening_shift"  # 14:00-22:00  
    NIGHT_SHIFT = "night_shift"    # 22:00-6:00
    FLEXIBLE = "flexible"
    CUSTOM = "custom"


class OperatorLoadBucket(BaseModel):
    """Time-bucketed operator load and availability data."""
    
    operator_id: UUID
    employee_id: str = ""
    full_name: str = ""
    department: str = "general"
    
    bucket_start: datetime
    bucket_end: datetime
    shift_pattern: ShiftPattern = ShiftPattern.FLEXIBLE
    
    # Load metrics
    total_assigned_minutes: int = Field(ge=0, default=0)
    total_available_minutes: int = Field(ge=0, default=0)
    total_working_minutes: int = Field(ge=0, default=0)
    
    # Task assignment metrics
    tasks_assigned: int = Field(ge=0, default=0)
    tasks_completed: int = Field(ge=0, default=0)
    tasks_active: int = Field(ge=0, default=0)
    
    # Skill utilization
    primary_skill_usage_minutes: int = Field(ge=0, default=0)
    secondary_skill_usage_minutes: int = Field(ge=0, default=0)
    cross_training_minutes: int = Field(ge=0, default=0)
    
    # Performance indicators
    average_task_efficiency: float = Field(ge=0.0, default=1.0)
    setup_time_percentage: float = Field(ge=0.0, le=1.0, default=0.0)
    
    @property
    def load_percentage(self) -> float:
        """Calculate load percentage (0.0 to 1.0)."""
        if self.total_available_minutes <= 0:
            return 0.0
        return min(1.0, self.total_assigned_minutes / self.total_available_minutes)
    
    @property
    def utilization_rate(self) -> float:
        """Calculate actual utilization rate.""" 
        if self.total_available_minutes <= 0:
            return 0.0
        return min(1.0, self.total_working_minutes / self.total_available_minutes)
    
    @property
    def completion_rate(self) -> float:
        """Calculate task completion rate."""
        if self.tasks_assigned <= 0:
            return 0.0
        return min(1.0, self.tasks_completed / self.tasks_assigned)
    
    @property
    def available_capacity_minutes(self) -> int:
        """Calculate remaining available capacity."""
        return max(0, self.total_available_minutes - self.total_assigned_minutes)
    
    @property
    def is_overloaded(self) -> bool:
        """Check if operator is overloaded (>95% capacity)."""
        return self.load_percentage > 0.95
    
    @property
    def is_underutilized(self) -> bool:
        """Check if operator is underutilized (<60% capacity)."""
        return self.load_percentage < 0.60


class OperatorAvailabilityForecast(BaseModel):
    """Operator availability forecast for capacity planning."""
    
    operator_id: UUID
    employee_id: str
    full_name: str
    
    forecast_date: date
    shift_pattern: ShiftPattern
    
    # Availability windows
    available_windows: List[Tuple[time, time]] = Field(default_factory=list)
    total_available_minutes: int = Field(ge=0)
    
    # Planned assignments
    planned_assignment_minutes: int = Field(ge=0, default=0)
    remaining_capacity_minutes: int = Field(ge=0, default=0)
    
    # Skill availability
    available_skills: Dict[str, int] = Field(default_factory=dict)  # skill -> proficiency level
    
    # Constraints and preferences
    overtime_eligible: bool = False
    max_overtime_minutes: int = Field(ge=0, default=0)
    preferred_task_types: List[str] = Field(default_factory=list)
    
    @property
    def capacity_utilization(self) -> float:
        """Calculate planned capacity utilization."""
        if self.total_available_minutes <= 0:
            return 0.0
        return min(1.0, self.planned_assignment_minutes / self.total_available_minutes)
    
    @property
    def has_capacity(self) -> bool:
        """Check if operator has remaining capacity."""
        return self.remaining_capacity_minutes > 30  # At least 30 minutes


class SkillDemandAnalysis(BaseModel):
    """Analysis of skill demand vs availability."""
    
    skill_code: str
    skill_name: str = ""
    department: str = "general"
    
    # Demand metrics  
    total_demand_hours: float = Field(ge=0.0)
    peak_demand_hours: float = Field(ge=0.0)
    unmet_demand_hours: float = Field(ge=0.0, default=0.0)
    
    # Supply metrics
    available_operators: int = Field(ge=0)
    total_supply_hours: float = Field(ge=0.0)
    average_skill_level: float = Field(ge=0.0, le=5.0)
    
    # Utilization
    skill_utilization_rate: float = Field(ge=0.0, le=1.0)
    
    @property
    def demand_supply_ratio(self) -> float:
        """Calculate demand to supply ratio."""
        if self.total_supply_hours <= 0:
            return float('inf') if self.total_demand_hours > 0 else 0.0
        return self.total_demand_hours / self.total_supply_hours
    
    @property
    def shortage_severity(self) -> str:
        """Determine skill shortage severity."""
        ratio = self.demand_supply_ratio
        if ratio > 1.5:
            return "critical"
        elif ratio > 1.2:
            return "high"
        elif ratio > 1.0:
            return "moderate"
        else:
            return "adequate"


class OperatorLoadReadModel:
    """
    Read model service for operator load and availability analytics.
    
    Provides high-performance queries for operator workload balancing,
    shift planning, and skill-based capacity management.
    """
    
    def __init__(self, db_session: Session):
        """Initialize with database session."""
        self.db = db_session
    
    async def get_operator_load_buckets(
        self,
        operator_ids: Optional[List[UUID]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        department: Optional[str] = None,
        bucket_hours: int = 8  # Default to 8-hour buckets (shift-based)
    ) -> List[OperatorLoadBucket]:
        """
        Get time-bucketed operator load data.
        
        Args:
            operator_ids: Specific operators to query (None for all)
            start_time: Query start time (defaults to today)
            end_time: Query end time (defaults to 7 days from start)
            department: Filter by department
            bucket_hours: Hours per bucket (8 for shift, 1 for hourly)
            
        Returns:
            List of load buckets ordered by operator and time
        """
        if not start_time:
            start_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if not end_time:
            end_time = start_time + timedelta(days=7)
        
        query = self._build_operator_load_query(
            operator_ids, start_time, end_time, department, bucket_hours
        )
        
        result = self.db.execute(text(query), {
            'start_time': start_time,
            'end_time': end_time,
            'operator_ids': [str(oid) for oid in (operator_ids or [])],
            'department': department,
            'bucket_hours': bucket_hours
        })
        
        buckets = []
        for row in result.fetchall():
            buckets.append(OperatorLoadBucket(
                operator_id=UUID(row.operator_id),
                employee_id=row.employee_id or "",
                full_name=row.full_name or "",
                department=row.department or "general",
                bucket_start=row.bucket_start,
                bucket_end=row.bucket_end,
                shift_pattern=ShiftPattern(row.shift_pattern) if row.shift_pattern else ShiftPattern.FLEXIBLE,
                total_assigned_minutes=row.assigned_minutes or 0,
                total_available_minutes=row.available_minutes or 0,
                total_working_minutes=row.working_minutes or 0,
                tasks_assigned=row.tasks_assigned or 0,
                tasks_completed=row.tasks_completed or 0,
                tasks_active=row.tasks_active or 0,
                primary_skill_usage_minutes=row.primary_skill_minutes or 0,
                secondary_skill_usage_minutes=row.secondary_skill_minutes or 0,
                cross_training_minutes=row.cross_training_minutes or 0,
                average_task_efficiency=row.avg_efficiency or 1.0,
                setup_time_percentage=row.setup_percentage or 0.0
            ))
        
        return buckets
    
    async def get_availability_forecast(
        self,
        forecast_days: int = 7,
        department: Optional[str] = None,
        skill_codes: Optional[List[str]] = None,
        include_overtime: bool = False
    ) -> List[OperatorAvailabilityForecast]:
        """
        Get operator availability forecast for capacity planning.
        
        Args:
            forecast_days: Number of days to forecast
            department: Filter by department
            skill_codes: Filter by required skills
            include_overtime: Include overtime capacity
            
        Returns:
            List of availability forecasts by operator and date
        """
        start_date = date.today()
        end_date = start_date + timedelta(days=forecast_days)
        
        query = """
        WITH operator_skills AS (
            SELECT 
                o.id as operator_id,
                o.employee_id,
                o.first_name || ' ' || o.last_name as full_name,
                o.department,
                o.default_working_hours_start,
                o.default_working_hours_end,
                COALESCE(json_agg(
                    json_build_object(
                        'skill_code', os.skill_code,
                        'proficiency_level', os.proficiency_level
                    )
                ) FILTER (WHERE os.skill_code IS NOT NULL), '[]'::json) as skills
            FROM operators o
            LEFT JOIN operator_skills os ON os.operator_id = o.id 
                AND os.is_active = true
                AND (os.expiry_date IS NULL OR os.expiry_date > CURRENT_DATE)
            WHERE o.is_active = true
                AND o.status IN ('AVAILABLE', 'BUSY')
                AND (:department IS NULL OR o.department = :department)
            GROUP BY o.id, o.employee_id, o.first_name, o.last_name, o.department,
                     o.default_working_hours_start, o.default_working_hours_end
        ),
        daily_forecasts AS (
            SELECT 
                os.operator_id,
                os.employee_id,
                os.full_name,
                d.forecast_date,
                os.default_working_hours_start,
                os.default_working_hours_end,
                os.skills,
                -- Calculate available minutes based on working hours and existing assignments
                EXTRACT(EPOCH FROM (os.default_working_hours_end - os.default_working_hours_start))/60 as base_available_minutes,
                COALESCE(SUM(EXTRACT(EPOCH FROM (oa.planned_end_time - oa.planned_start_time))/60), 0) as planned_minutes
            FROM operator_skills os
            CROSS JOIN generate_series(:start_date, :end_date, '1 day'::interval) d(forecast_date)
            LEFT JOIN operator_assignments oa ON oa.operator_id = os.operator_id
                AND oa.planned_start_time::date = d.forecast_date::date
                AND oa.status IN ('SCHEDULED', 'IN_PROGRESS')
            GROUP BY os.operator_id, os.employee_id, os.full_name, d.forecast_date,
                     os.default_working_hours_start, os.default_working_hours_end, os.skills
        )
        SELECT 
            operator_id,
            employee_id,
            full_name,
            forecast_date,
            default_working_hours_start,
            default_working_hours_end,
            skills,
            base_available_minutes,
            planned_minutes,
            GREATEST(0, base_available_minutes - planned_minutes) as remaining_capacity
        FROM daily_forecasts
        WHERE (:skill_codes IS NULL OR EXISTS (
            SELECT 1 FROM json_array_elements(skills) s
            WHERE s->>'skill_code' = ANY(:skill_codes::text[])
        ))
        ORDER BY operator_id, forecast_date
        """
        
        result = self.db.execute(text(query), {
            'start_date': start_date,
            'end_date': end_date,
            'department': department,
            'skill_codes': skill_codes or []
        })
        
        forecasts = []
        for row in result.fetchall():
            # Parse available skills
            skills_dict = {}
            if row.skills:
                import json
                skills_data = json.loads(row.skills) if isinstance(row.skills, str) else row.skills
                for skill in skills_data:
                    skills_dict[skill['skill_code']] = skill['proficiency_level']
            
            # Determine shift pattern based on working hours
            shift_pattern = self._determine_shift_pattern(
                row.default_working_hours_start, row.default_working_hours_end
            )
            
            # Calculate available windows (simplified - assumes single continuous window)
            available_windows = [(row.default_working_hours_start, row.default_working_hours_end)]
            
            forecasts.append(OperatorAvailabilityForecast(
                operator_id=UUID(row.operator_id),
                employee_id=row.employee_id,
                full_name=row.full_name,
                forecast_date=row.forecast_date.date() if hasattr(row.forecast_date, 'date') else row.forecast_date,
                shift_pattern=shift_pattern,
                available_windows=available_windows,
                total_available_minutes=int(row.base_available_minutes or 0),
                planned_assignment_minutes=int(row.planned_minutes or 0),
                remaining_capacity_minutes=int(row.remaining_capacity or 0),
                available_skills=skills_dict,
                overtime_eligible=include_overtime,
                max_overtime_minutes=120 if include_overtime else 0  # 2 hours max OT
            ))
        
        return forecasts
    
    async def get_skill_demand_analysis(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        department: Optional[str] = None
    ) -> List[SkillDemandAnalysis]:
        """
        Analyze skill demand vs supply for capacity planning.
        
        Args:
            start_time: Analysis period start
            end_time: Analysis period end  
            department: Filter by department
            
        Returns:
            List of skill demand analysis results
        """
        if not start_time:
            start_time = datetime.utcnow()
        if not end_time:
            end_time = start_time + timedelta(days=14)  # 2 week forecast
        
        query = """
        WITH skill_demand AS (
            SELECT 
                sr.skill_code,
                sr.skill_name,
                t.department,
                COUNT(DISTINCT t.id) as tasks_requiring_skill,
                SUM(EXTRACT(EPOCH FROM (t.planned_end_time - t.planned_start_time))/3600) as demand_hours,
                MAX(EXTRACT(EPOCH FROM (t.planned_end_time - t.planned_start_time))/3600) as peak_task_hours
            FROM tasks t
            JOIN task_skill_requirements tsr ON tsr.task_id = t.id
            JOIN skill_requirements sr ON sr.id = tsr.skill_requirement_id
            WHERE t.planned_start_time >= :start_time
                AND t.planned_end_time <= :end_time
                AND t.status IN ('PENDING', 'READY', 'SCHEDULED')
                AND (:department IS NULL OR t.department = :department)
            GROUP BY sr.skill_code, sr.skill_name, t.department
        ),
        skill_supply AS (
            SELECT 
                os.skill_code,
                o.department,
                COUNT(DISTINCT o.id) as available_operators,
                AVG(os.proficiency_level) as avg_skill_level,
                -- Estimate available hours per day * forecast days
                SUM(EXTRACT(EPOCH FROM (o.default_working_hours_end - o.default_working_hours_start))/3600) 
                    * (:end_time::date - :start_time::date) as supply_hours
            FROM operators o
            JOIN operator_skills os ON os.operator_id = o.id
            WHERE o.is_active = true
                AND o.status IN ('AVAILABLE', 'BUSY')
                AND os.is_active = true
                AND (os.expiry_date IS NULL OR os.expiry_date > :end_time::date)
                AND (:department IS NULL OR o.department = :department)
            GROUP BY os.skill_code, o.department
        )
        SELECT 
            COALESCE(d.skill_code, s.skill_code) as skill_code,
            COALESCE(d.skill_name, s.skill_code) as skill_name,
            COALESCE(d.department, s.department, 'general') as department,
            COALESCE(d.demand_hours, 0) as demand_hours,
            COALESCE(d.peak_task_hours, 0) as peak_hours,
            COALESCE(s.available_operators, 0) as available_operators,
            COALESCE(s.supply_hours, 0) as supply_hours,
            COALESCE(s.avg_skill_level, 0) as avg_skill_level,
            CASE 
                WHEN COALESCE(s.supply_hours, 0) > 0 
                THEN COALESCE(d.demand_hours, 0) / s.supply_hours
                ELSE 0
            END as utilization_rate
        FROM skill_demand d
        FULL OUTER JOIN skill_supply s ON s.skill_code = d.skill_code AND s.department = d.department
        WHERE COALESCE(d.demand_hours, s.supply_hours, 0) > 0
        ORDER BY demand_hours DESC, utilization_rate DESC
        """
        
        result = self.db.execute(text(query), {
            'start_time': start_time,
            'end_time': end_time,
            'department': department
        })
        
        analyses = []
        for row in result.fetchall():
            analyses.append(SkillDemandAnalysis(
                skill_code=row.skill_code,
                skill_name=row.skill_name,
                department=row.department,
                total_demand_hours=float(row.demand_hours or 0),
                peak_demand_hours=float(row.peak_hours or 0),
                available_operators=row.available_operators or 0,
                total_supply_hours=float(row.supply_hours or 0),
                average_skill_level=float(row.avg_skill_level or 0),
                skill_utilization_rate=min(1.0, float(row.utilization_rate or 0))
            ))
        
        return analyses
    
    async def get_overloaded_operators(
        self,
        threshold_load: float = 0.90,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Identify overloaded operators for workload rebalancing.
        
        Args:
            threshold_load: Minimum load percentage to consider overloaded
            start_time: Analysis period start
            end_time: Analysis period end
            
        Returns:
            List of overloaded operator analysis dictionaries
        """
        if not start_time:
            start_time = datetime.utcnow()
        if not end_time:
            end_time = start_time + timedelta(days=7)
        
        query = """
        WITH operator_loads AS (
            SELECT 
                o.id as operator_id,
                o.employee_id,
                o.first_name || ' ' || o.last_name as full_name,
                o.department,
                COUNT(oa.id) as total_assignments,
                SUM(EXTRACT(EPOCH FROM (oa.planned_end_time - oa.planned_start_time))/60) as assigned_minutes,
                -- Estimate available minutes based on working hours and period
                EXTRACT(EPOCH FROM (o.default_working_hours_end - o.default_working_hours_start))/60 
                    * (:end_time::date - :start_time::date) as available_minutes,
                COUNT(CASE WHEN oa.status = 'IN_PROGRESS' THEN 1 END) as active_assignments,
                AVG(CASE WHEN oa.actual_end_time IS NOT NULL AND oa.planned_end_time IS NOT NULL 
                         THEN EXTRACT(EPOCH FROM (oa.actual_end_time - oa.planned_start_time)) / 
                              EXTRACT(EPOCH FROM (oa.planned_end_time - oa.planned_start_time))
                         ELSE 1.0 END) as avg_efficiency
            FROM operators o
            LEFT JOIN operator_assignments oa ON oa.operator_id = o.id
                AND oa.planned_start_time >= :start_time
                AND oa.planned_end_time <= :end_time
            WHERE o.is_active = true
                AND o.status IN ('AVAILABLE', 'BUSY')
            GROUP BY o.id, o.employee_id, o.first_name, o.last_name, o.department,
                     o.default_working_hours_start, o.default_working_hours_end
        )
        SELECT 
            operator_id,
            employee_id,
            full_name,
            department,
            total_assignments,
            assigned_minutes,
            available_minutes,
            active_assignments,
            avg_efficiency,
            CASE 
                WHEN available_minutes > 0 
                THEN assigned_minutes / available_minutes
                ELSE 0 
            END as load_percentage
        FROM operator_loads
        WHERE available_minutes > 0
            AND (assigned_minutes / available_minutes) >= :threshold
        ORDER BY load_percentage DESC, active_assignments DESC
        """
        
        result = self.db.execute(text(query), {
            'start_time': start_time,
            'end_time': end_time,
            'threshold': threshold_load
        })
        
        overloaded = []
        for row in result.fetchall():
            overloaded.append({
                'operator_id': str(row.operator_id),
                'employee_id': row.employee_id,
                'full_name': row.full_name,
                'department': row.department,
                'load_percentage': float(row.load_percentage),
                'total_assignments': row.total_assignments,
                'active_assignments': row.active_assignments,
                'avg_efficiency': float(row.avg_efficiency or 1.0),
                'assigned_hours': float(row.assigned_minutes or 0) / 60.0,
                'available_hours': float(row.available_minutes or 0) / 60.0,
                'overload_severity': self._calculate_overload_severity(
                    float(row.load_percentage), row.active_assignments
                )
            })
        
        return overloaded
    
    def _build_operator_load_query(
        self,
        operator_ids: Optional[List[UUID]],
        start_time: datetime,
        end_time: datetime,
        department: Optional[str],
        bucket_hours: int
    ) -> str:
        """Build optimized operator load query."""
        
        operator_filter = ""
        if operator_ids:
            operator_filter = "AND o.id = ANY(:operator_ids::uuid[])"
        
        department_filter = ""
        if department:
            department_filter = "AND o.department = :department"
        
        return f"""
        WITH time_buckets AS (
            SELECT generate_series(
                :start_time, 
                :end_time, 
                INTERVAL '{bucket_hours} hours'
            ) as bucket_start
        ),
        operator_buckets AS (
            SELECT 
                o.id as operator_id,
                o.employee_id,
                o.first_name || ' ' || o.last_name as full_name,
                o.department,
                tb.bucket_start,
                tb.bucket_start + INTERVAL '{bucket_hours} hours' as bucket_end,
                -- Determine shift pattern based on bucket time
                CASE 
                    WHEN EXTRACT(HOUR FROM tb.bucket_start) BETWEEN 6 AND 13 THEN 'day_shift'
                    WHEN EXTRACT(HOUR FROM tb.bucket_start) BETWEEN 14 AND 21 THEN 'evening_shift' 
                    WHEN EXTRACT(HOUR FROM tb.bucket_start) >= 22 OR EXTRACT(HOUR FROM tb.bucket_start) <= 5 THEN 'night_shift'
                    ELSE 'flexible'
                END as shift_pattern,
                -- Calculate available minutes in this bucket based on working hours
                {bucket_hours * 60} as bucket_minutes
            FROM operators o
            CROSS JOIN time_buckets tb
            WHERE o.is_active = true
                AND o.status IN ('AVAILABLE', 'BUSY')
                {operator_filter}
                {department_filter}
        ),
        bucket_assignments AS (
            SELECT 
                ob.operator_id,
                ob.employee_id,
                ob.full_name,
                ob.department,
                ob.bucket_start,
                ob.bucket_end,
                ob.shift_pattern,
                ob.bucket_minutes as available_minutes,
                
                -- Assignment metrics within this bucket
                COALESCE(SUM(CASE 
                    WHEN oa.planned_start_time < ob.bucket_end AND oa.planned_end_time > ob.bucket_start
                    THEN LEAST(
                        EXTRACT(EPOCH FROM ob.bucket_end)/60,
                        EXTRACT(EPOCH FROM oa.planned_end_time)/60
                    ) - GREATEST(
                        EXTRACT(EPOCH FROM ob.bucket_start)/60,
                        EXTRACT(EPOCH FROM oa.planned_start_time)/60
                    )
                    ELSE 0
                END), 0) as assigned_minutes,
                
                -- Working minutes (actual time if available)
                COALESCE(SUM(CASE 
                    WHEN oa.actual_start_time IS NOT NULL AND oa.actual_end_time IS NOT NULL
                         AND oa.actual_start_time < ob.bucket_end AND oa.actual_end_time > ob.bucket_start
                    THEN LEAST(
                        EXTRACT(EPOCH FROM ob.bucket_end)/60,
                        EXTRACT(EPOCH FROM oa.actual_end_time)/60
                    ) - GREATEST(
                        EXTRACT(EPOCH FROM ob.bucket_start)/60,
                        EXTRACT(EPOCH FROM oa.actual_start_time)/60
                    )
                    ELSE 0
                END), 0) as working_minutes,
                
                -- Task counts
                COUNT(CASE WHEN oa.planned_start_time < ob.bucket_end AND oa.planned_end_time > ob.bucket_start THEN 1 END) as tasks_assigned,
                COUNT(CASE WHEN oa.status = 'COMPLETED' AND oa.planned_start_time < ob.bucket_end AND oa.planned_end_time > ob.bucket_start THEN 1 END) as tasks_completed,
                COUNT(CASE WHEN oa.status = 'IN_PROGRESS' AND oa.planned_start_time < ob.bucket_end AND oa.planned_end_time > ob.bucket_start THEN 1 END) as tasks_active,
                
                -- Skill usage (simplified)
                COALESCE(SUM(CASE WHEN tsr.skill_priority = 1 THEN EXTRACT(EPOCH FROM (oa.planned_end_time - oa.planned_start_time))/60 ELSE 0 END), 0) as primary_skill_minutes,
                COALESCE(SUM(CASE WHEN tsr.skill_priority = 2 THEN EXTRACT(EPOCH FROM (oa.planned_end_time - oa.planned_start_time))/60 ELSE 0 END), 0) as secondary_skill_minutes,
                0 as cross_training_minutes,  -- Would need additional tracking
                
                -- Performance metrics
                AVG(CASE 
                    WHEN oa.actual_end_time IS NOT NULL AND oa.planned_end_time IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (oa.planned_end_time - oa.planned_start_time)) / 
                         EXTRACT(EPOCH FROM (oa.actual_end_time - oa.actual_start_time))
                    ELSE 1.0 
                END) as avg_efficiency,
                
                AVG(CASE 
                    WHEN oa.setup_duration_minutes IS NOT NULL AND oa.total_duration_minutes IS NOT NULL AND oa.total_duration_minutes > 0
                    THEN oa.setup_duration_minutes::float / oa.total_duration_minutes
                    ELSE 0.0
                END) as setup_percentage
                
            FROM operator_buckets ob
            LEFT JOIN operator_assignments oa ON oa.operator_id = ob.operator_id
                AND oa.planned_start_time < ob.bucket_end 
                AND oa.planned_end_time > ob.bucket_start
            LEFT JOIN task_skill_requirements tsr ON tsr.task_id = oa.task_id
            GROUP BY ob.operator_id, ob.employee_id, ob.full_name, ob.department,
                     ob.bucket_start, ob.bucket_end, ob.shift_pattern, ob.bucket_minutes
        )
        SELECT 
            operator_id,
            employee_id,
            full_name,
            department,
            bucket_start,
            bucket_end,
            shift_pattern,
            assigned_minutes,
            available_minutes,
            working_minutes,
            tasks_assigned,
            tasks_completed,
            tasks_active,
            primary_skill_minutes,
            secondary_skill_minutes,
            cross_training_minutes,
            COALESCE(avg_efficiency, 1.0) as avg_efficiency,
            COALESCE(setup_percentage, 0.0) as setup_percentage
        FROM bucket_assignments
        ORDER BY operator_id, bucket_start
        """
    
    def _determine_shift_pattern(self, start_time: time, end_time: time) -> ShiftPattern:
        """Determine shift pattern based on working hours."""
        start_hour = start_time.hour if start_time else 8
        end_hour = end_time.hour if end_time else 17
        
        if start_hour >= 6 and end_hour <= 14:
            return ShiftPattern.DAY_SHIFT
        elif start_hour >= 14 and end_hour <= 22:
            return ShiftPattern.EVENING_SHIFT
        elif start_hour >= 22 or end_hour <= 6:
            return ShiftPattern.NIGHT_SHIFT
        else:
            return ShiftPattern.FLEXIBLE
    
    def _calculate_overload_severity(self, load_percentage: float, active_assignments: int) -> str:
        """Calculate operator overload severity."""
        if load_percentage >= 1.1 and active_assignments >= 5:
            return "critical"
        elif load_percentage >= 1.0 and active_assignments >= 3:
            return "high"  
        elif load_percentage >= 0.95:
            return "moderate"
        else:
            return "low"