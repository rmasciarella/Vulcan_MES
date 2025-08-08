# End-to-End Workflow Integration Tests

This directory contains comprehensive end-to-end integration tests that verify the complete production scheduling workflow from job creation through schedule optimization to execution and monitoring.

## Test Coverage

### 1. Complete Workflow Integration (`test_scheduling_workflow_e2e.py`)
- **Job Creation → Schedule Execution**: Complete workflow from job creation through task assignment, schedule optimization, publication, and execution
- **Rescheduling Workflows**: Dynamic rescheduling and conflict resolution
- **Schedule Optimization**: Multiple optimization strategies and validation
- **Error Handling**: Recovery from invalid configurations and solver failures

### 2. Multi-User Role-Based Workflows (`test_multi_user_workflow_e2e.py`)
- **Collaborative Job Creation**: Multi-role job creation and approval workflows
- **Concurrent User Operations**: Simultaneous operations by different users
- **Role-Based Access Control**: Permission enforcement across workflow steps
- **Workflow State Transitions**: Role-controlled state changes
- **Cross-Role Notifications**: Communication and updates between roles

### 3. Error Handling and Recovery (`test_error_recovery_workflow_e2e.py`)
- **Invalid Job Creation Recovery**: Handling and recovery from validation errors
- **Database Failure Recovery**: Connection failures and transaction rollbacks
- **Solver Failure Recovery**: Optimization failures and fallback strategies
- **Concurrent Modification Conflicts**: Optimistic locking and conflict resolution
- **Resource Constraint Violations**: Capacity conflicts and resolution
- **Network Timeout Recovery**: Circuit breaker patterns and retry logic
- **Data Corruption Recovery**: Integrity checks and cleanup procedures
- **System Overload Recovery**: Rate limiting and load shedding

### 4. Performance Integration (`test_performance_integration_e2e.py`)
- **Large-Scale Job Creation**: Performance with 100+ jobs and 500+ tasks
- **Complex Scheduling Optimization**: Multi-objective optimization performance
- **Concurrent User Load**: System behavior under concurrent access
- **Memory Usage Patterns**: Memory efficiency and garbage collection
- **Database Performance**: Query performance under load
- **Response Time Analysis**: Latency distribution and percentile analysis

### 5. Data Integrity and Transactions (`test_data_integrity_e2e.py`)
- **Transaction Atomicity**: Ensuring atomic operations across entities
- **Constraint Violation Rollback**: Proper rollback on integrity violations
- **Concurrent Transaction Isolation**: ACID compliance under concurrency
- **Cascading Delete Integrity**: Referential integrity with related entities
- **Schedule Optimization Consistency**: Data consistency during complex operations
- **Audit Trail Consistency**: Maintaining audit integrity during operations
- **Partial Failure Recovery**: Recovery from incomplete transactions

### 6. WebSocket Real-Time Updates (`test_websocket_integration_e2e.py`)
- **Single Client Workflow Updates**: Real-time updates during workflow operations
- **Multi-Client Event Broadcasting**: Broadcasting to multiple connected clients
- **Topic-Based Subscription Filtering**: Filtered updates based on subscriptions
- **Connection Management**: Connection lifecycle and error handling
- **High-Frequency Events**: Performance under rapid event generation
- **Memory Usage Under Load**: Resource management with many connections
- **REST API Integration**: WebSocket events triggered by API operations

### 7. Security Integration (`test_security_integration_e2e.py`)
- **Authentication Workflow Integration**: End-to-end authentication flows
- **Token Validation and Expiry**: JWT lifecycle and validation
- **Role-Based Access Control**: Permission enforcement throughout workflows
- **Permission-Based Scheduling**: Access control for scheduling operations
- **Concurrent Security Operations**: Security enforcement under concurrency
- **API Rate Limiting**: Rate limiting for security
- **Password Security**: Hashing and validation mechanisms
- **Session Management**: Token lifecycle and revocation
- **Security Audit Logging**: Security event logging and tracking

### 8. Audit Trail and Compliance (`test_audit_compliance_e2e.py`)
- **Complete Audit Trail Workflow**: Comprehensive audit logging through regulated workflows
- **Compliance Data Retention**: Long-term data retention and historical access
- **Regulatory Compliance Reporting**: FDA, ISO, and other compliance standards
- **Audit Trail Immutability**: Tamper detection and integrity verification
- **Cross-System Audit Correlation**: Audit correlation across system components

## Test Architecture

### Base Test Classes
- **TestCompleteSchedulingWorkflowE2E**: Complete workflow integration
- **TestMultiUserWorkflowE2E**: Multi-user collaboration scenarios
- **TestErrorHandlingWorkflowE2E**: Error scenarios and recovery
- **TestPerformanceIntegrationE2E**: Large-scale performance scenarios
- **TestDataIntegrityE2E**: Data consistency and transaction safety
- **TestWebSocketIntegrationE2E**: Real-time update integration
- **TestSecurityIntegrationE2E**: Security and authorization flows
- **TestAuditComplianceE2E**: Audit and compliance verification

### Test Utilities and Helpers

#### Performance Monitoring
```python
class PerformanceMonitor:
    async def time_operation(self, operation_name: str):
        # Context manager for timing operations

    def get_stats(self) -> Dict[str, Any]:
        # Get comprehensive performance statistics
```

#### Test Data Factories
```python
class TestDataFactory:
    @staticmethod
    def create_job_data(job_number: str, **kwargs) -> Dict[str, Any]:
        # Create realistic job data

    @staticmethod
    def create_task_data(sequence: int, **kwargs) -> Dict[str, Any]:
        # Create realistic task data

    @staticmethod
    def create_optimization_parameters(**kwargs) -> Dict[str, Any]:
        # Create optimization parameters
```

#### Security Test Helpers
```python
class SecurityTestHelper:
    @staticmethod
    def create_expired_token(user_email: str) -> str:
        # Create expired JWT for testing

    @staticmethod
    def create_custom_role_token(user_email: str, roles: List[str]) -> str:
        # Create token with custom roles
```

#### Database Integrity Checkers
```python
class DatabaseIntegrityChecker:
    def check_referential_integrity(self) -> Dict[str, Any]:
        # Verify database referential integrity

    def check_business_rule_consistency(self) -> Dict[str, Any]:
        # Verify business rule consistency
```

#### WebSocket Test Clients
```python
class WebSocketTestClient:
    async def connect(self) -> bool:
        # Connect to WebSocket endpoint

    async def receive_messages(self, count: int) -> List[Dict[str, Any]]:
        # Receive multiple messages
```

#### Audit Test Helpers
```python
class AuditTestHelper:
    @staticmethod
    def verify_audit_completeness(audit_entries: List[Dict], expected_actions: List[str]) -> Dict[str, Any]:
        # Verify audit trail completeness

    @staticmethod
    def create_audit_scenario_workflow() -> List[Dict[str, Any]]:
        # Create comprehensive audit scenario
```

## Running the Tests

### Prerequisites
1. **Database Setup**: Ensure test database is configured
2. **Dependencies**: Install all test dependencies including `pytest`, `websockets`, `psutil`
3. **Environment**: Set up test environment variables
4. **Services**: Ensure required services (Redis, etc.) are available for integration tests

### Execute All E2E Tests
```bash
# Run all E2E tests
pytest app/tests/e2e/ -v

# Run with coverage
pytest app/tests/e2e/ --cov=app --cov-report=html

# Run specific test categories
pytest app/tests/e2e/ -m "e2e and not slow"
pytest app/tests/e2e/ -m "performance"
pytest app/tests/e2e/ -m "security"
```

### Execute Specific Test Files
```bash
# Complete workflow tests
pytest app/tests/e2e/test_scheduling_workflow_e2e.py -v

# Multi-user workflow tests
pytest app/tests/e2e/test_multi_user_workflow_e2e.py -v

# Performance tests (may take longer)
pytest app/tests/e2e/test_performance_integration_e2e.py -v -s

# Security tests
pytest app/tests/e2e/test_security_integration_e2e.py -v

# WebSocket tests (requires WebSocket server)
pytest app/tests/e2e/test_websocket_integration_e2e.py -v --tb=short
```

### Test Markers
- `@pytest.mark.e2e`: End-to-end integration tests
- `@pytest.mark.slow`: Slow-running tests (performance, load testing)
- `@pytest.mark.performance`: Performance-focused tests
- `@pytest.mark.security`: Security and authorization tests
- `@pytest.mark.websocket`: WebSocket integration tests
- `@pytest.mark.audit_compliance`: Audit and compliance tests
- `@pytest.mark.data_integrity`: Data integrity and transaction tests

### Skip Slow Tests
```bash
# Skip performance-heavy tests for faster feedback
pytest app/tests/e2e/ -m "not slow"

# Run only fast integration tests
pytest app/tests/e2e/ -m "e2e and not slow and not performance"
```

## Test Configuration

### Performance Thresholds
- **Job Creation**: < 2.0 seconds per job
- **Schedule Optimization**: < 30.0 seconds for complex scenarios
- **Concurrent Operations**: 85%+ success rate under load
- **Memory Usage**: < 20% increase during load testing
- **Response Times**: 99th percentile < 5.0 seconds

### Security Configuration
- **Token Expiry**: 60-second buffer for expiry testing
- **Max Login Attempts**: 5 attempts before lockout
- **Password Requirements**: Configurable complexity requirements

### Compliance Configuration
- **Audit Retention**: 2555 days (7 years) for regulatory compliance
- **Required Audit Fields**: timestamp, user, action, entity_type, entity_id
- **Immutability Verification**: Hash-based integrity checking

## Test Data Management

### Realistic Test Scenarios
- **Production Scenarios**: 15 jobs across 6 different customer types
- **Task Templates**: 5 different operation types with varying complexity
- **Optimization Scenarios**: 4 different optimization strategies
- **User Roles**: 9 different organizational roles with specific permissions

### Data Cleanup
- Automatic cleanup after each test function
- Session-level cleanup for heavy integration tests
- Manual cleanup utilities for debugging

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failures**
   - Ensure WebSocket server is running
   - Check firewall and port configuration
   - Verify authentication tokens are valid

2. **Performance Test Timeouts**
   - Increase timeout values in test configuration
   - Check system resources (CPU, memory)
   - Verify database connection pool settings

3. **Database Integrity Failures**
   - Check foreign key constraints
   - Verify transaction isolation levels
   - Review concurrent access patterns

4. **Security Test Failures**
   - Verify JWT secret configuration
   - Check token expiry settings
   - Review permission matrix configuration

### Debug Mode
```bash
# Run with detailed output
pytest app/tests/e2e/ -v -s --tb=long

# Run specific test with pdb debugging
pytest app/tests/e2e/test_scheduling_workflow_e2e.py::TestCompleteSchedulingWorkflowE2E::test_complete_job_to_schedule_workflow -v -s --pdb
```

## Continuous Integration

### CI Pipeline Integration
```yaml
# Example GitHub Actions configuration
- name: Run E2E Tests
  run: |
    pytest app/tests/e2e/ -m "e2e and not slow" --cov=app --cov-report=xml

- name: Run Performance Tests
  run: |
    pytest app/tests/e2e/ -m "performance" --tb=short
  continue-on-error: true  # Performance tests may be environment-dependent
```

### Test Reports
- **Coverage Reports**: HTML and XML coverage reports
- **Performance Reports**: JSON performance metrics
- **Security Reports**: Security test results and audit logs
- **Compliance Reports**: Audit trail verification results

## Contributing

### Adding New E2E Tests
1. Follow the existing test structure and naming conventions
2. Use appropriate test markers (`@pytest.mark.e2e`, etc.)
3. Include realistic test data using provided factories
4. Add performance monitoring for new operations
5. Document expected behavior and thresholds

### Test Best Practices
1. **Isolation**: Each test should be independent and repeatable
2. **Cleanup**: Always clean up created test data
3. **Realistic Data**: Use realistic test data that matches production scenarios
4. **Performance Awareness**: Monitor and assert on performance characteristics
5. **Error Scenarios**: Include both success and failure paths
6. **Documentation**: Document complex test scenarios and expected outcomes

This comprehensive E2E test suite ensures that the production scheduling system works correctly under realistic conditions and provides confidence for production deployments.
