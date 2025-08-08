# Database Testing Suite - Story 1.2

## Overview

This comprehensive test suite validates database connectivity and CRUD operations for the Vulcan Engine backend. The tests ensure a solid foundation for the `/solve` API endpoint by thoroughly testing the database layer functionality.

## Test Structure

### Core Test Files

#### 1. **Connection & Health Tests** (`test_connectivity.py`)
- **Database Connectivity**: Engine creation, connection validation
- **Health Checks**: Database status monitoring, connection pool health
- **Error Recovery**: Connection failures, timeouts, pool exhaustion
- **Performance Monitoring**: Connection pool statistics, query performance

#### 2. **Model Validation Tests** (`test_models.py`)
- **Job Entity Tests**: Creation, validation, business rules, status transitions
- **Task Entity Tests**: Sequencing, scheduling, completion workflows
- **Operator Assignment Tests**: Resource allocation, timing operations
- **Relationship Tests**: Job-Task coordination, referential integrity

#### 3. **Repository CRUD Tests** (`test_repositories.py`)
- **Job Repository**: Save, retrieve, update, delete operations
- **Task Repository**: CRUD operations, filtering, status queries
- **Query Performance**: Collection queries, filtered operations
- **Repository Integration**: Cross-repository scenarios

#### 4. **Integration Tests** (`test_integration.py`)
- **Manufacturing Workflows**: Complete job-to-completion scenarios
- **Priority Management**: Job prioritization and scheduling
- **Task Dependencies**: Sequential task execution
- **Operator Assignments**: Resource allocation workflows
- **Quality Management**: Rework and quality issue handling

#### 5. **Error Handling Tests** (`test_error_handling.py`)
- **Connection Errors**: Database unavailability, timeouts
- **Constraint Violations**: Unique keys, foreign keys, check constraints
- **Business Rule Violations**: Status transitions, validation errors
- **Transaction Errors**: Rollback scenarios, deadlock handling
- **Recovery Mechanisms**: Circuit breakers, retry logic

#### 6. **Performance Tests** (`test_performance.py`)
- **Query Performance**: Single entity, collection, and filtered queries
- **Bulk Operations**: Batch inserts, updates, deletions
- **Concurrency**: Concurrent read/write operations
- **Scalability**: Performance with increasing data sizes
- **Memory Usage**: Large dataset memory efficiency

### Supporting Infrastructure

#### **Test Data Factories** (`factories.py`)
- `JobFactory`: Creates test jobs with various configurations
- `TaskFactory`: Creates tasks in different states (pending, ready, scheduled, etc.)
- `OperatorAssignmentFactory`: Creates operator assignments
- `TestDataBuilder`: Creates complex scenarios for integration testing

#### **Test Utilities** (`test_utils.py`)
- `DatabaseTestHelper`: Database operations and statistics
- `PerformanceBenchmark`: Performance measurement and comparison
- `TestDataManager`: Test data lifecycle management
- `ConcurrencyTestHelper`: Concurrent operation testing

#### **Test Configuration** (`conftest.py`)
- Database session fixtures with proper cleanup
- Sample data fixtures for common test scenarios
- Performance monitoring fixtures
- Transaction management utilities

## Test Categories

### **Unit Tests**
- Individual model validation
- Repository method testing
- Business rule enforcement
- Data transformation validation

### **Integration Tests**
- End-to-end workflow scenarios
- Cross-entity relationship testing
- Real database operations
- Transaction boundary testing

### **Performance Tests**
- Query performance benchmarks
- Load testing with realistic data volumes
- Concurrent operation validation
- Memory usage verification

### **Error Handling Tests**
- Database connection failures
- Constraint violation recovery
- Business rule exception handling
- Data validation error scenarios

## Key Test Scenarios

### **Manufacturing Workflow Tests**
1. **Job Lifecycle**: Creation → Release → In Progress → Completion
2. **Task Progression**: Sequential task completion with dependency management
3. **Priority Adjustments**: Dynamic job priority changes and rescheduling
4. **Resource Allocation**: Operator assignment and machine scheduling
5. **Quality Management**: Rework tracking and completion workflows

### **Database Operation Tests**
1. **CRUD Operations**: All basic database operations for each entity
2. **Complex Queries**: Filtered queries with multiple conditions
3. **Bulk Operations**: Batch processing for performance
4. **Relationship Integrity**: Foreign key and referential integrity
5. **Transaction Management**: ACID compliance and rollback scenarios

### **Performance Benchmarks**
1. **Single Entity Retrieval**: < 1ms average response time
2. **Collection Queries**: < 10ms for filtered collections
3. **Bulk Operations**: > 100 entities/second processing
4. **Concurrent Operations**: No significant performance degradation
5. **Memory Usage**: Linear scaling with data size

## Usage Instructions

### **Running Tests**

#### **All Database Tests**
```bash
# Run complete database test suite
./scripts/run-db-tests.sh

# With coverage reporting
./scripts/run-db-tests.sh --coverage --format html
```

#### **Specific Test Categories**
```bash
# Connectivity tests only
./scripts/run-db-tests.sh --connectivity

# Performance tests with benchmarking
./scripts/run-db-tests.sh --performance --benchmark

# Integration tests with verbose output
./scripts/run-db-tests.sh --integration --verbose
```

#### **Direct Pytest Execution**
```bash
# Run all database tests
pytest app/tests/database/

# Run with markers
pytest app/tests/database/ -m "connectivity"
pytest app/tests/database/ -m "performance"

# Run with coverage
pytest app/tests/database/ --cov=app.domain --cov=app.core.db --cov-report=html
```

### **Test Data Management**

```python
# Using test factories in your tests
from app.tests.database.factories import JobFactory, TaskFactory

def test_job_workflow():
    # Create test job with tasks
    job = JobFactory.create_with_tasks(task_count=5)

    # Create specific scenarios
    urgent_job = JobFactory.create_urgent()
    overdue_job = JobFactory.create_overdue()

def test_performance_scenario():
    # Create realistic workload
    workload = TestDataBuilder.create_workload_scenario()
    jobs = workload['jobs']
    tasks = workload['tasks']
```

### **Performance Monitoring**

```python
# Using performance monitor fixture
def test_with_performance_monitoring(performance_monitor):
    with performance_monitor.time_operation("bulk_insert"):
        jobs = JobFactory.create_batch(1000)

    stats = performance_monitor.get_stats()
    assert stats['avg_time'] < 1.0  # Assert performance requirement
```

## Coverage Requirements

### **Database Layer Coverage**
- **Connection Management**: 100% coverage of connection scenarios
- **CRUD Operations**: 100% coverage of all repository methods
- **Business Rules**: 100% coverage of validation logic
- **Error Handling**: 95% coverage of exception scenarios

### **Performance Requirements**
- **Query Performance**: 95th percentile < 50ms for complex queries
- **Throughput**: > 1000 operations/second for bulk operations
- **Concurrency**: No deadlocks under normal concurrent load
- **Memory**: Linear memory usage scaling with data size

### **Reliability Requirements**
- **Connection Recovery**: Automatic recovery from temporary failures
- **Transaction Integrity**: ACID compliance for all operations
- **Data Consistency**: Referential integrity maintained
- **Error Recovery**: Graceful degradation under error conditions

## CI/CD Integration

### **Test Execution Pipeline**
1. **Database Setup**: Automated test database creation
2. **Migration Validation**: Schema migration testing
3. **Test Execution**: All test categories with parallelization
4. **Performance Validation**: Benchmark comparison with baselines
5. **Coverage Reporting**: Comprehensive coverage analysis

### **Quality Gates**
- **Test Coverage**: Minimum 95% coverage for database layer
- **Performance Benchmarks**: No regression beyond 10% performance degradation
- **Error Handling**: All error scenarios must have test coverage
- **Integration Tests**: All critical workflows must pass

## Test Data and Fixtures

### **Test Database Configuration**
- **Isolated Test Environment**: Separate test database with automatic cleanup
- **Transaction Isolation**: Each test runs in isolated transaction
- **Parallel Execution Support**: Safe concurrent test execution
- **Data Reset**: Automatic cleanup between test runs

### **Realistic Test Data**
- **Manufacturing Scenarios**: Realistic job/task/operator combinations
- **Volume Testing**: Large datasets for performance validation
- **Edge Cases**: Boundary conditions and error scenarios
- **Historical Data**: Time-based scenarios for scheduling validation

## Maintenance and Updates

### **Test Maintenance**
- **Regular Performance Baseline Updates**: Monthly benchmark updates
- **Test Data Refresh**: Quarterly realistic scenario updates
- **Coverage Analysis**: Weekly coverage reporting
- **Performance Monitoring**: Continuous performance trend analysis

### **Adding New Tests**
1. **Create Test File**: Follow naming convention `test_*.py`
2. **Use Test Factories**: Leverage existing factories for data creation
3. **Add Fixtures**: Create reusable fixtures in `conftest.py`
4. **Document Coverage**: Update coverage requirements
5. **Performance Benchmarks**: Add performance assertions for new operations

This comprehensive test suite ensures the database layer is robust, performant, and ready to support the `/solve` API endpoint implementation.
