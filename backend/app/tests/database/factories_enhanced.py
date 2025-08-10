"""
Enhanced Test Data Factories

Advanced factory classes with realistic business scenarios, edge cases,
and domain-specific test data patterns for comprehensive testing.
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.task import OperatorAssignment, Task
from app.domain.scheduling.value_objects.enums import (
    AssignmentType,
    JobStatus,
    PriorityLevel,
    TaskStatus,
)


class BusinessScenario(Enum):
    """Pre-defined business scenarios for realistic testing."""
    AUTOMOTIVE_PRODUCTION = "automotive_production"
    AEROSPACE_MANUFACTURING = "aerospace_manufacturing"
    MEDICAL_DEVICE = "medical_device"
    ELECTRONICS_ASSEMBLY = "electronics_assembly"
    CUSTOM_MACHINING = "custom_machining"
    DEFENSE_CONTRACT = "defense_contract"
    PROTOTYPE_DEVELOPMENT = "prototype_development"
    MAINTENANCE_OVERHAUL = "maintenance_overhaul"


class IndustryDataPatterns:
    """Industry-specific data patterns and constraints."""
    
    AUTOMOTIVE = {
        "customers": [
            "Ford Motor Company", "General Motors", "Toyota Manufacturing",
            "BMW Group", "Mercedes-Benz", "Volkswagen AG", "Stellantis"
        ],
        "part_prefixes": ["ENG", "TRN", "SUS", "BRK", "ELX", "INT", "EXT"],
        "typical_quantities": [50, 100, 250, 500, 1000, 2500, 5000],
        "lead_times": {"normal": 14, "rush": 7, "emergency": 3},
        "quality_standards": ["TS16949", "ISO9001", "PPAP"],
        "operations": [
            "Rough Machining", "Finish Machining", "Heat Treatment",
            "Surface Coating", "Quality Inspection", "Packaging"
        ]
    }
    
    AEROSPACE = {
        "customers": [
            "Boeing", "Airbus", "Lockheed Martin", "Northrop Grumman",
            "Raytheon", "BAE Systems", "General Dynamics"
        ],
        "part_prefixes": ["ACS", "ENG", "LDG", "FLT", "NAV", "PWR", "STR"],
        "typical_quantities": [1, 2, 5, 10, 25, 50],
        "lead_times": {"normal": 28, "rush": 14, "emergency": 7},
        "quality_standards": ["AS9100", "NADCAP", "FAA-PMA"],
        "operations": [
            "Precision Machining", "EDM", "Welding", "NDT Inspection",
            "Surface Treatment", "Final Assembly", "FAI Documentation"
        ]
    }
    
    MEDICAL = {
        "customers": [
            "Johnson & Johnson", "Medtronic", "Abbott", "Boston Scientific",
            "Stryker", "Zimmer Biomet", "Smith & Nephew"
        ],
        "part_prefixes": ["IMP", "SUR", "DIG", "ORT", "CAR", "NEU", "DEN"],
        "typical_quantities": [10, 25, 50, 100, 500, 1000],
        "lead_times": {"normal": 21, "rush": 10, "emergency": 5},
        "quality_standards": ["ISO13485", "FDA-510k", "CE-MDR"],
        "operations": [
            "Micro Machining", "Laser Processing", "Bio-compatible Coating",
            "Sterile Assembly", "Validation Testing", "Clean Room Packaging"
        ]
    }
    
    ELECTRONICS = {
        "customers": [
            "Apple", "Samsung", "Intel", "NVIDIA", "AMD",
            "Qualcomm", "Broadcom", "Texas Instruments"
        ],
        "part_prefixes": ["PCB", "SEM", "CON", "ENC", "THM", "OPT", "SNS"],
        "typical_quantities": [1000, 5000, 10000, 25000, 50000, 100000],
        "lead_times": {"normal": 10, "rush": 5, "emergency": 2},
        "quality_standards": ["IPC-A-610", "J-STD-001", "RoHS"],
        "operations": [
            "SMT Assembly", "Wave Soldering", "Conformal Coating",
            "ICT Testing", "Functional Test", "Final QC"
        ]
    }


class ScenarioFactory:
    """Factory for creating industry-specific business scenarios."""
    
    @staticmethod
    def create_automotive_production_scenario() -> Dict[str, Any]:
        """Create automotive production scenario."""
        patterns = IndustryDataPatterns.AUTOMOTIVE
        
        jobs = []
        for i in range(8):  # Typical batch size for automotive
            customer = random.choice(patterns["customers"])
            part_prefix = random.choice(patterns["part_prefixes"])
            quantity = random.choice(patterns["typical_quantities"])
            
            # Automotive parts often have long part numbers
            part_number = f"{part_prefix}-{random.randint(1000, 9999)}-{random.choice(['A', 'B', 'C'])}{random.randint(1, 9)}"
            
            job = AdvancedJobFactory.create(
                job_number=f"AUTO-{datetime.utcnow().strftime('%y%m')}-{i+1:03d}",
                customer_name=customer,
                part_number=part_number,
                quantity=quantity,
                priority=random.choice([PriorityLevel.NORMAL, PriorityLevel.HIGH]),
                due_date=datetime.utcnow() + timedelta(days=patterns["lead_times"]["normal"]),
                industry_type="automotive",
                quality_standards=random.sample(patterns["quality_standards"], 2),
                operations=patterns["operations"][:4]  # First 4 operations
            )
            jobs.append(job)
        
        return {
            "scenario_type": "automotive_production",
            "jobs": jobs,
            "characteristics": {
                "high_volume": True,
                "quality_critical": True,
                "cost_sensitive": True,
                "delivery_critical": True
            }
        }
    
    @staticmethod
    def create_aerospace_precision_scenario() -> Dict[str, Any]:
        """Create aerospace precision manufacturing scenario."""
        patterns = IndustryDataPatterns.AEROSPACE
        
        jobs = []
        for i in range(3):  # Low volume, high precision
            customer = random.choice(patterns["customers"])
            part_prefix = random.choice(patterns["part_prefixes"])
            quantity = random.choice(patterns["typical_quantities"])
            
            # Aerospace parts have strict traceability
            part_number = f"{part_prefix}-{random.randint(10000, 99999)}-{random.randint(100, 999)}"
            
            job = AdvancedJobFactory.create(
                job_number=f"AERO-{datetime.utcnow().strftime('%y%m')}-{i+1:03d}",
                customer_name=customer,
                part_number=part_number,
                quantity=quantity,
                priority=PriorityLevel.HIGH,  # Always high priority
                due_date=datetime.utcnow() + timedelta(days=patterns["lead_times"]["normal"]),
                industry_type="aerospace",
                quality_standards=patterns["quality_standards"],
                operations=patterns["operations"],
                requires_documentation=True,
                requires_special_handling=True
            )
            jobs.append(job)
        
        return {
            "scenario_type": "aerospace_precision",
            "jobs": jobs,
            "characteristics": {
                "high_precision": True,
                "documentation_heavy": True,
                "long_lead_time": True,
                "regulatory_compliance": True
            }
        }
    
    @staticmethod
    def create_mixed_workload_scenario() -> Dict[str, Any]:
        """Create realistic mixed workload scenario."""
        # Mix different industry types
        scenarios = [
            ScenarioFactory.create_automotive_production_scenario(),
            ScenarioFactory.create_aerospace_precision_scenario(),
            ScenarioFactory.create_medical_device_scenario(),
            ScenarioFactory.create_electronics_assembly_scenario()
        ]
        
        all_jobs = []
        all_characteristics = {}
        
        for scenario in scenarios:
            all_jobs.extend(scenario["jobs"][:2])  # Take 2 jobs from each
            all_characteristics.update(scenario["characteristics"])
        
        # Add some rush orders
        rush_jobs = [
            AdvancedJobFactory.create_rush_order(industry="automotive"),
            AdvancedJobFactory.create_rush_order(industry="electronics")
        ]
        all_jobs.extend(rush_jobs)
        
        return {
            "scenario_type": "mixed_workload",
            "jobs": all_jobs,
            "characteristics": all_characteristics
        }
    
    @staticmethod
    def create_medical_device_scenario() -> Dict[str, Any]:
        """Create medical device manufacturing scenario."""
        patterns = IndustryDataPatterns.MEDICAL
        
        jobs = []
        for i in range(5):
            customer = random.choice(patterns["customers"])
            part_prefix = random.choice(patterns["part_prefixes"])
            quantity = random.choice(patterns["typical_quantities"])
            
            part_number = f"{part_prefix}-{random.randint(1000, 9999)}-REV{random.choice(['A', 'B', 'C'])}"
            
            job = AdvancedJobFactory.create(
                job_number=f"MED-{datetime.utcnow().strftime('%y%m')}-{i+1:03d}",
                customer_name=customer,
                part_number=part_number,
                quantity=quantity,
                priority=PriorityLevel.HIGH,
                due_date=datetime.utcnow() + timedelta(days=patterns["lead_times"]["normal"]),
                industry_type="medical",
                quality_standards=patterns["quality_standards"],
                operations=patterns["operations"],
                requires_clean_room=True,
                requires_validation=True
            )
            jobs.append(job)
        
        return {
            "scenario_type": "medical_device",
            "jobs": jobs,
            "characteristics": {
                "regulatory_strict": True,
                "clean_room_required": True,
                "validation_extensive": True,
                "traceability_full": True
            }
        }
    
    @staticmethod
    def create_electronics_assembly_scenario() -> Dict[str, Any]:
        """Create electronics assembly scenario."""
        patterns = IndustryDataPatterns.ELECTRONICS
        
        jobs = []
        for i in range(6):
            customer = random.choice(patterns["customers"])
            part_prefix = random.choice(patterns["part_prefixes"])
            quantity = random.choice(patterns["typical_quantities"])
            
            part_number = f"{part_prefix}{random.randint(100, 999)}-V{random.randint(1, 5)}.{random.randint(0, 9)}"
            
            job = AdvancedJobFactory.create(
                job_number=f"ELEC-{datetime.utcnow().strftime('%y%m')}-{i+1:03d}",
                customer_name=customer,
                part_number=part_number,
                quantity=quantity,
                priority=random.choice([PriorityLevel.NORMAL, PriorityLevel.HIGH]),
                due_date=datetime.utcnow() + timedelta(days=patterns["lead_times"]["normal"]),
                industry_type="electronics",
                quality_standards=patterns["quality_standards"],
                operations=patterns["operations"]
            )
            jobs.append(job)
        
        return {
            "scenario_type": "electronics_assembly",
            "jobs": jobs,
            "characteristics": {
                "high_volume": True,
                "fast_turnaround": True,
                "technology_driven": True,
                "cost_competitive": True
            }
        }


class AdvancedJobFactory:
    """Enhanced job factory with industry-specific patterns."""
    
    @staticmethod
    def create(
        job_number: str = None,
        customer_name: str = None,
        part_number: str = None,
        quantity: int = 1,
        priority: PriorityLevel = PriorityLevel.NORMAL,
        status: JobStatus = JobStatus.PLANNED,
        due_date: datetime = None,
        industry_type: str = "general",
        quality_standards: List[str] = None,
        operations: List[str] = None,
        **kwargs
    ) -> Job:
        """Create job with industry-specific attributes."""
        if job_number is None:
            job_number = f"ADV{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        
        if customer_name is None:
            # Select customer based on industry
            if industry_type == "automotive":
                customer_name = random.choice(IndustryDataPatterns.AUTOMOTIVE["customers"])
            elif industry_type == "aerospace":
                customer_name = random.choice(IndustryDataPatterns.AEROSPACE["customers"])
            elif industry_type == "medical":
                customer_name = random.choice(IndustryDataPatterns.MEDICAL["customers"])
            elif industry_type == "electronics":
                customer_name = random.choice(IndustryDataPatterns.ELECTRONICS["customers"])
            else:
                customer_name = f"Customer_{random.randint(1, 100)}"
        
        if part_number is None:
            prefix = "PART"
            if industry_type in ["automotive", "aerospace", "medical", "electronics"]:
                patterns = getattr(IndustryDataPatterns, industry_type.upper())
                prefix = random.choice(patterns["part_prefixes"])
            part_number = f"{prefix}-{random.randint(1000, 9999)}"
        
        if due_date is None:
            base_days = 14  # Default lead time
            if industry_type == "aerospace":
                base_days = 28
            elif industry_type == "electronics":
                base_days = 10
            elif industry_type == "medical":
                base_days = 21
            
            due_date = datetime.utcnow() + timedelta(days=base_days + random.randint(-3, 7))
        
        # Create base job
        job = Job.create(
            job_number=job_number,
            due_date=due_date,
            customer_name=customer_name,
            part_number=part_number,
            quantity=quantity,
            priority=priority,
            created_by=f"user_{random.randint(1, 20)}"
        )
        
        # Add industry-specific metadata
        job.metadata = {
            "industry_type": industry_type,
            "quality_standards": quality_standards or [],
            "operations": operations or [],
            **kwargs
        }
        
        return job
    
    @staticmethod
    def create_rush_order(industry: str = "general") -> Job:
        """Create rush order with tight deadline."""
        rush_due = datetime.utcnow() + timedelta(days=random.randint(1, 3))
        
        return AdvancedJobFactory.create(
            job_number=f"RUSH-{datetime.utcnow().strftime('%m%d%H%M')}",
            priority=PriorityLevel.URGENT,
            due_date=rush_due,
            industry_type=industry,
            quantity=random.randint(1, 50),  # Usually smaller quantities
            rush_order=True,
            expedite_fee=Decimal("500.00")
        )
    
    @staticmethod
    def create_prototype_job() -> Job:
        """Create prototype development job."""
        return AdvancedJobFactory.create(
            job_number=f"PROTO-{uuid4().hex[:8].upper()}",
            priority=PriorityLevel.HIGH,
            quantity=1,  # Prototypes are typically quantity 1
            industry_type="prototype",
            due_date=datetime.utcnow() + timedelta(days=21),
            prototype=True,
            requires_design_review=True,
            billable_hours_estimated=40.0
        )
    
    @staticmethod
    def create_maintenance_job() -> Job:
        """Create equipment maintenance job."""
        equipment_list = [
            "CNC-MILL-001", "LATHE-002", "GRINDER-003", 
            "EDM-004", "WELDING-005", "PRESS-006"
        ]
        
        return AdvancedJobFactory.create(
            job_number=f"MAINT-{datetime.utcnow().strftime('%y%m%d')}-{random.randint(100, 999)}",
            customer_name="Internal Maintenance",
            part_number=f"MAINT-{random.choice(equipment_list)}",
            quantity=1,
            priority=random.choice([PriorityLevel.NORMAL, PriorityLevel.HIGH, PriorityLevel.URGENT]),
            industry_type="maintenance",
            due_date=datetime.utcnow() + timedelta(days=random.randint(1, 7)),
            maintenance_type=random.choice(["preventive", "corrective", "emergency"]),
            equipment_id=random.choice(equipment_list),
            downtime_cost_per_hour=Decimal("150.00")
        )


class EdgeCaseFactory:
    """Factory for creating edge cases and boundary conditions."""
    
    @staticmethod
    def create_extreme_quantity_jobs() -> List[Job]:
        """Create jobs with extreme quantities (very small and very large)."""
        return [
            AdvancedJobFactory.create(
                job_number="EDGE-MICRO-001",
                quantity=1,  # Minimum quantity
                part_number="MICRO-PRECISION-001",
                industry_type="medical"
            ),
            AdvancedJobFactory.create(
                job_number="EDGE-BULK-001",
                quantity=100000,  # Very large quantity
                part_number="BULK-COMMODITY-001",
                industry_type="automotive"
            )
        ]
    
    @staticmethod
    def create_tight_deadline_jobs() -> List[Job]:
        """Create jobs with very tight deadlines."""
        now = datetime.utcnow()
        return [
            AdvancedJobFactory.create(
                job_number="EDGE-URGENT-001",
                due_date=now + timedelta(hours=4),  # 4 hours from now
                priority=PriorityLevel.URGENT,
                emergency_order=True
            ),
            AdvancedJobFactory.create(
                job_number="EDGE-SAME-DAY-001",
                due_date=now + timedelta(hours=8),  # Same day
                priority=PriorityLevel.URGENT,
                same_day_delivery=True
            )
        ]
    
    @staticmethod
    def create_overdue_jobs() -> List[Job]:
        """Create jobs that are already overdue."""
        now = datetime.utcnow()
        return [
            AdvancedJobFactory.create(
                job_number="EDGE-OVERDUE-001",
                due_date=now - timedelta(days=1),  # 1 day overdue
                status=JobStatus.IN_PROGRESS,
                overdue=True
            ),
            AdvancedJobFactory.create(
                job_number="EDGE-LATE-001",
                due_date=now - timedelta(days=7),  # 1 week overdue
                status=JobStatus.RELEASED,
                overdue=True,
                late_fee=Decimal("100.00")
            )
        ]
    
    @staticmethod
    def create_complex_dependency_scenario() -> Dict[str, Any]:
        """Create jobs with complex dependencies."""
        # Create a chain of dependent jobs
        jobs = []
        
        # Master job
        master_job = AdvancedJobFactory.create(
            job_number="DEP-MASTER-001",
            customer_name="Complex Systems Inc",
            part_number="MASTER-ASSEMBLY-001",
            quantity=10
        )
        jobs.append(master_job)
        
        # Dependent sub-assemblies
        for i in range(3):
            sub_job = AdvancedJobFactory.create(
                job_number=f"DEP-SUB-{i+1:03d}",
                customer_name="Internal",
                part_number=f"SUB-ASSEMBLY-{i+1:03d}",
                quantity=10,
                parent_job_id=master_job.id
            )
            jobs.append(sub_job)
            
            # Components for each sub-assembly
            for j in range(2):
                component_job = AdvancedJobFactory.create(
                    job_number=f"DEP-COMP-{i+1}-{j+1}",
                    customer_name="Internal",
                    part_number=f"COMPONENT-{i+1}-{j+1}",
                    quantity=20,  # Double quantity for assembly
                    parent_job_id=sub_job.id
                )
                jobs.append(component_job)
        
        return {
            "scenario_type": "complex_dependencies",
            "jobs": jobs,
            "dependency_depth": 3,
            "total_jobs": len(jobs)
        }
    
    @staticmethod
    def create_resource_conflict_scenario() -> Dict[str, Any]:
        """Create scenario that will cause resource conflicts."""
        # All jobs need the same specialized resource at the same time
        conflict_time = datetime.utcnow() + timedelta(hours=24)
        
        jobs = []
        for i in range(5):
            job = AdvancedJobFactory.create(
                job_number=f"CONFLICT-{i+1:03d}",
                due_date=conflict_time,
                priority=PriorityLevel.HIGH,
                required_machine="SPECIAL-CNC-001",
                required_operator="SPECIALIST-CERT-001",
                setup_time_hours=2.0
            )
            jobs.append(job)
        
        return {
            "scenario_type": "resource_conflicts",
            "jobs": jobs,
            "conflict_resource": "SPECIAL-CNC-001",
            "conflict_time": conflict_time.isoformat()
        }


class RealisticWorkloadGenerator:
    """Generate realistic workloads based on industry patterns."""
    
    @staticmethod
    def generate_monthly_workload(industry: str = "mixed") -> Dict[str, Any]:
        """Generate realistic monthly workload."""
        jobs = []
        scenarios = []
        
        if industry == "mixed":
            # Mixed industry workload
            auto_scenario = ScenarioFactory.create_automotive_production_scenario()
            aero_scenario = ScenarioFactory.create_aerospace_precision_scenario()
            med_scenario = ScenarioFactory.create_medical_device_scenario()
            elec_scenario = ScenarioFactory.create_electronics_assembly_scenario()
            
            scenarios = [auto_scenario, aero_scenario, med_scenario, elec_scenario]
            
            for scenario in scenarios:
                jobs.extend(scenario["jobs"])
        
        # Add edge cases (10% of workload)
        edge_cases = [
            *EdgeCaseFactory.create_extreme_quantity_jobs(),
            *EdgeCaseFactory.create_tight_deadline_jobs(),
            *EdgeCaseFactory.create_overdue_jobs(),
        ]
        
        # Add maintenance jobs (5% of workload)
        maintenance_jobs = [
            AdvancedJobFactory.create_maintenance_job()
            for _ in range(3)
        ]
        
        # Add prototype jobs (5% of workload)
        prototype_jobs = [
            AdvancedJobFactory.create_prototype_job()
            for _ in range(2)
        ]
        
        all_jobs = jobs + edge_cases + maintenance_jobs + prototype_jobs
        
        # Shuffle to simulate realistic arrival order
        random.shuffle(all_jobs)
        
        return {
            "workload_type": f"monthly_{industry}",
            "jobs": all_jobs,
            "total_jobs": len(all_jobs),
            "scenarios": [s["scenario_type"] for s in scenarios],
            "statistics": {
                "production_jobs": len(jobs),
                "edge_cases": len(edge_cases),
                "maintenance_jobs": len(maintenance_jobs),
                "prototype_jobs": len(prototype_jobs),
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def generate_stress_test_workload(job_count: int = 1000) -> Dict[str, Any]:
        """Generate large workload for stress testing."""
        jobs = []
        
        # Generate jobs in batches for efficiency
        batch_size = 100
        industries = ["automotive", "aerospace", "medical", "electronics"]
        
        for i in range(0, job_count, batch_size):
            batch_industry = random.choice(industries)
            
            for j in range(batch_size):
                if i + j >= job_count:
                    break
                
                job = AdvancedJobFactory.create(
                    job_number=f"STRESS-{i+j+1:06d}",
                    industry_type=batch_industry,
                    quantity=random.randint(1, 1000),
                    priority=random.choice(list(PriorityLevel))
                )
                jobs.append(job)
        
        return {
            "workload_type": "stress_test",
            "jobs": jobs,
            "total_jobs": len(jobs),
            "target_count": job_count,
            "generated_at": datetime.utcnow().isoformat()
        }


# Utility functions for enhanced testing
def create_industry_specific_scenario(industry: BusinessScenario) -> Dict[str, Any]:
    """Create scenario based on business scenario enum."""
    scenario_map = {
        BusinessScenario.AUTOMOTIVE_PRODUCTION: ScenarioFactory.create_automotive_production_scenario,
        BusinessScenario.AEROSPACE_MANUFACTURING: ScenarioFactory.create_aerospace_precision_scenario,
        BusinessScenario.MEDICAL_DEVICE: ScenarioFactory.create_medical_device_scenario,
        BusinessScenario.ELECTRONICS_ASSEMBLY: ScenarioFactory.create_electronics_assembly_scenario,
    }
    
    return scenario_map.get(industry, ScenarioFactory.create_mixed_workload_scenario)()


def validate_scenario_realism(scenario: Dict[str, Any]) -> Dict[str, bool]:
    """Validate that scenario data appears realistic."""
    jobs = scenario.get("jobs", [])
    
    checks = {
        "has_jobs": len(jobs) > 0,
        "reasonable_quantities": all(1 <= job.quantity <= 100000 for job in jobs),
        "future_due_dates": all(job.due_date > datetime.utcnow() - timedelta(days=90) for job in jobs),
        "valid_priorities": all(hasattr(job, 'priority') for job in jobs),
        "unique_job_numbers": len(set(job.job_number for job in jobs)) == len(jobs),
        "realistic_customers": all(len(job.customer_name) > 2 for job in jobs),
        "valid_part_numbers": all(len(job.part_number) > 3 for job in jobs),
    }
    
    return checks
