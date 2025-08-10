"""Entity aliases that align ubiquitous language with existing models.

These provide friendly type names often used by operations teams while reusing
our core entities under the hood.
"""
from __future__ import annotations

from typing import Union

from .job import Job as WorkOrder
from .machine import Machine
from .operator import Operator
from .production_zone import ProductionZone as WorkCell
from .schedule import Schedule

# Resource is either a machine or an operator
Resource = Union[Machine, Operator]

__all__ = [
    "WorkOrder",
    "Resource",
    "WorkCell",
    "Schedule",
]
