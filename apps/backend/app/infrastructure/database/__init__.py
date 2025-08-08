"""
Database Infrastructure

Contains database-specific implementations and schema definitions.
This module bridges the gap between the domain layer's repository interfaces
and the actual database technology (PostgreSQL/SQLModel).

Components:
- schema.sql: Complete SQL schema definitions for production scheduling
- migrations/: Custom database migrations for scheduling domain
- repositories/: Concrete implementations of domain repository interfaces
"""
