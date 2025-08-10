"""
API Contract Testing

Comprehensive contract testing using OpenAPI schema validation,
ensuring API consistency and backward compatibility.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from jsonschema import validate
from openapi_spec_validator import validate_spec
from pydantic import BaseModel

from app.main import app


class APIContractTester:
    """Comprehensive API contract testing framework."""
    
    def __init__(self, client: TestClient):
        self.client = client
        self.openapi_spec = None
        self.load_openapi_spec()
    
    def load_openapi_spec(self):
        """Load and validate OpenAPI specification."""
        response = self.client.get("/openapi.json")
        assert response.status_code == 200
        
        self.openapi_spec = response.json()
        
        # Validate OpenAPI spec itself
        try:
            validate_spec(self.openapi_spec)
        except Exception as e:
            pytest.fail(f"Invalid OpenAPI specification: {e}")
    
    def validate_response_schema(self, endpoint: str, method: str, response_data: Any, status_code: int = 200):
        """Validate response against OpenAPI schema."""
        if not self.openapi_spec:
            return
        
        # Find endpoint in spec
        path_item = None
        for path_pattern, path_data in self.openapi_spec.get("paths", {}).items():
            if self._matches_path_pattern(endpoint, path_pattern):
                path_item = path_data.get(method.lower())
                break
        
        if not path_item:
            pytest.fail(f"Endpoint {method} {endpoint} not found in OpenAPI spec")
        
        # Get response schema
        responses = path_item.get("responses", {})
        response_spec = responses.get(str(status_code)) or responses.get("default")
        
        if not response_spec:
            return  # No schema defined for this response
        
        content = response_spec.get("content", {})
        json_content = content.get("application/json")
        
        if not json_content:
            return  # No JSON schema defined
        
        schema = json_content.get("schema")
        if schema:
            # Resolve $ref if present
            schema = self._resolve_schema_ref(schema)
            
            # Validate response data
            try:
                validate(instance=response_data, schema=schema)
            except Exception as e:
                pytest.fail(f"Response schema validation failed for {method} {endpoint}: {e}")
    
    def _matches_path_pattern(self, actual_path: str, pattern: str) -> bool:
        """Check if actual path matches OpenAPI path pattern."""
        # Simple pattern matching - could be enhanced with regex
        pattern_parts = pattern.split("/")
        actual_parts = actual_path.split("/")
        
        if len(pattern_parts) != len(actual_parts):
            return False
        
        for pattern_part, actual_part in zip(pattern_parts, actual_parts):
            if pattern_part.startswith("{") and pattern_part.endswith("}"):
                continue  # Path parameter
            if pattern_part != actual_part:
                return False
        
        return True
    
    def _resolve_schema_ref(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve $ref in schema."""
        if "$ref" in schema:
            ref_path = schema["$ref"]
            if ref_path.startswith("#/components/schemas/"):
                schema_name = ref_path.replace("#/components/schemas/", "")
                components = self.openapi_spec.get("components", {})
                schemas = components.get("schemas", {})
                return schemas.get(schema_name, schema)
        return schema


@pytest.fixture
def contract_tester(client: TestClient) -> APIContractTester:
    """Provide API contract tester."""
    return APIContractTester(client)


class TestAPIContracts:
    """API contract validation tests."""
    
    def test_openapi_spec_validity(self, client: TestClient):
        """Verify OpenAPI specification is valid."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        spec = response.json()
        
        # Basic structure validation
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec
        
        # Version validation
        assert spec["openapi"].startswith("3.")
        
        # Info validation
        info = spec["info"]
        assert "title" in info
        assert "version" in info
        
        # Validate spec format
        validate_spec(spec)
    
    def test_health_endpoint_contract(self, contract_tester: APIContractTester):
        """Test health endpoint contract compliance."""
        response = contract_tester.client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        contract_tester.validate_response_schema("/health", "GET", data)
        
        # Additional business logic validation
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy", "degraded"]
        assert "timestamp" in data
        assert "version" in data
    
    def test_jobs_crud_contract(self, contract_tester: APIContractTester, superuser_token_headers: dict):
        """Test jobs CRUD endpoints contract compliance."""
        client = contract_tester.client
        
        # Test job creation
        job_data = {
            "job_number": "CONTRACT_TEST_001",
            "customer_name": "Test Customer",
            "part_number": "TEST-PART-001",
            "quantity": 10,
            "priority": "NORMAL",
            "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }
        
        response = client.post("/api/v1/jobs/", json=job_data, headers=superuser_token_headers)
        assert response.status_code == 201
        
        created_job = response.json()
        contract_tester.validate_response_schema("/api/v1/jobs/", "POST", created_job, 201)
        
        job_id = created_job["id"]
        
        # Test job retrieval
        response = client.get(f"/api/v1/jobs/{job_id}", headers=superuser_token_headers)
        assert response.status_code == 200
        
        job_detail = response.json()
        contract_tester.validate_response_schema(f"/api/v1/jobs/{job_id}", "GET", job_detail)
        
        # Test job listing
        response = client.get("/api/v1/jobs/", headers=superuser_token_headers)
        assert response.status_code == 200
        
        jobs_list = response.json()
        contract_tester.validate_response_schema("/api/v1/jobs/", "GET", jobs_list)
        
        # Test job update
        update_data = {"priority": "HIGH"}
        response = client.patch(f"/api/v1/jobs/{job_id}", json=update_data, headers=superuser_token_headers)
        assert response.status_code == 200
        
        updated_job = response.json()
        contract_tester.validate_response_schema(f"/api/v1/jobs/{job_id}", "PATCH", updated_job)
        
        # Clean up
        client.delete(f"/api/v1/jobs/{job_id}", headers=superuser_token_headers)
    
    def test_scheduling_endpoints_contract(self, contract_tester: APIContractTester, superuser_token_headers: dict):
        """Test scheduling endpoints contract compliance."""
        client = contract_tester.client
        
        # Test solver status
        response = client.get("/api/v1/scheduling/solve/status")
        # Allow both 200 (available) and 503 (unavailable) for OR-Tools
        assert response.status_code in [200, 503]
        
        status_data = response.json()
        contract_tester.validate_response_schema("/api/v1/scheduling/solve/status", "GET", status_data, response.status_code)
        
        # Test examples endpoint
        response = client.get("/api/v1/scheduling/solve/examples")
        assert response.status_code == 200
        
        examples_data = response.json()
        contract_tester.validate_response_schema("/api/v1/scheduling/solve/examples", "GET", examples_data)
        
        # Test solve endpoint with minimal data
        solve_data = {
            "problem_name": "Contract Test",
            "schedule_start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "jobs": [{
                "job_number": "CONTRACT_SOLVE_001",
                "priority": "normal",
                "due_date": (datetime.utcnow() + timedelta(days=3)).isoformat(),
                "quantity": 1,
                "customer_name": "Test Customer",
                "part_number": "TEST-PART",
                "task_sequences": [10, 20],
            }],
            "optimization_parameters": {
                "max_time_seconds": 10,
            }
        }
        
        response = client.post("/api/v1/scheduling/solve", json=solve_data, headers=superuser_token_headers)
        # Various status codes are acceptable based on solver availability
        assert response.status_code in [200, 408, 422, 500, 503]
        
        solve_result = response.json()
        contract_tester.validate_response_schema("/api/v1/scheduling/solve", "POST", solve_result, response.status_code)
    
    def test_error_response_contracts(self, contract_tester: APIContractTester):
        """Test error response contract compliance."""
        client = contract_tester.client
        
        # Test 404 responses
        response = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        
        error_data = response.json()
        contract_tester.validate_response_schema("/api/v1/jobs/{id}", "GET", error_data, 404)
        
        # Test 422 validation errors
        invalid_job_data = {
            "job_number": "",  # Invalid empty job number
            "quantity": -1,    # Invalid negative quantity
        }
        
        response = client.post("/api/v1/jobs/", json=invalid_job_data)
        assert response.status_code == 422
        
        validation_error = response.json()
        contract_tester.validate_response_schema("/api/v1/jobs/", "POST", validation_error, 422)
        
        # Validation error should have specific structure
        assert "detail" in validation_error
        assert isinstance(validation_error["detail"], list)
    
    def test_pagination_contract(self, contract_tester: APIContractTester, superuser_token_headers: dict):
        """Test pagination response contract."""
        client = contract_tester.client
        
        # Test with pagination parameters
        response = client.get("/api/v1/jobs/?skip=0&limit=10", headers=superuser_token_headers)
        assert response.status_code == 200
        
        paginated_data = response.json()
        contract_tester.validate_response_schema("/api/v1/jobs/", "GET", paginated_data)
        
        # Verify pagination structure if implemented
        if isinstance(paginated_data, dict) and "items" in paginated_data:
            assert "items" in paginated_data
            assert "total" in paginated_data
            assert "skip" in paginated_data
            assert "limit" in paginated_data


class TestBackwardCompatibility:
    """Test backward compatibility of API changes."""
    
    def test_api_version_consistency(self, client: TestClient):
        """Ensure API version is consistent across endpoints."""
        response = client.get("/openapi.json")
        spec = response.json()
        
        # Check that all endpoints use consistent versioning
        for path in spec.get("paths", {}).keys():
            if path.startswith("/api/"):
                # Should follow /api/v1/ pattern
                assert path.startswith("/api/v1/") or path in ["/api/health", "/api/status"]
    
    def test_required_fields_stability(self, contract_tester: APIContractTester):
        """Ensure required fields in requests haven't changed unexpectedly."""
        spec = contract_tester.openapi_spec
        
        # Define expected required fields for key endpoints
        expected_required = {
            "/api/v1/jobs/": {
                "POST": ["job_number", "customer_name", "part_number", "quantity"]
            }
        }
        
        for path, methods in expected_required.items():
            for method, required_fields in methods.items():
                path_spec = spec["paths"].get(path, {})
                method_spec = path_spec.get(method.lower(), {})
                
                request_body = method_spec.get("requestBody", {})
                if request_body:
                    content = request_body.get("content", {})
                    json_content = content.get("application/json", {})
                    schema = json_content.get("schema", {})
                    
                    actual_required = schema.get("required", [])
                    
                    # Check that all expected required fields are still required
                    for field in required_fields:
                        assert field in actual_required, f"Required field '{field}' missing from {method} {path}"


class TestResponseTimeContracts:
    """Test response time contracts for API endpoints."""
    
    @pytest.mark.performance
    def test_endpoint_response_times(self, client: TestClient, superuser_token_headers: dict):
        """Test that critical endpoints meet response time SLAs."""
        import time
        
        # Define response time SLAs (in seconds)
        sla_requirements = {
            "GET /health": 0.1,
            "GET /api/v1/jobs/": 2.0,
            "GET /api/v1/scheduling/solve/status": 0.5,
            "GET /api/v1/scheduling/solve/examples": 1.0,
        }
        
        for endpoint_description, max_time in sla_requirements.items():
            method, path = endpoint_description.split(" ", 1)
            
            start_time = time.time()
            
            if method == "GET":
                headers = superuser_token_headers if path.startswith("/api/v1/") else None
                response = client.get(path, headers=headers)
            else:
                continue  # Skip other methods for now
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Allow some tolerance for test environment variations
            tolerance_factor = 2.0
            max_allowed_time = max_time * tolerance_factor
            
            assert duration < max_allowed_time, f"{endpoint_description} took {duration:.3f}s, exceeding SLA of {max_time}s (with {tolerance_factor}x tolerance)"
            
            # Log performance for monitoring
            print(f"Performance: {endpoint_description} = {duration:.3f}s (SLA: {max_time}s)")


class ContractTestReporter:
    """Generate contract testing reports."""
    
    def __init__(self):
        self.results = []
    
    def record_test_result(self, endpoint: str, method: str, status: str, details: str = ""):
        """Record a contract test result."""
        self.results.append({
            "endpoint": endpoint,
            "method": method,
            "status": status,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive contract testing report."""
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r["status"] == "PASS"])
        failed_tests = len([r for r in self.results if r["status"] == "FAIL"])
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "pass_rate": passed_tests / total_tests if total_tests > 0 else 0,
            },
            "details": self.results,
            "generated_at": datetime.utcnow().isoformat(),
        }


@pytest.fixture
def contract_reporter():
    """Provide contract test reporter."""
    return ContractTestReporter()
