# Testing Container Models - Compatibility Guide

## Overview

This directory contains the models used by the security scanner containerized service. These models are designed to maintain **strict compatibility** with the main Flask application while providing the necessary abstractions for containerized testing services.

## Compatibility Strategy

### 1. **Synchronized Enums**
- `TestingStatus` maps to main app's `AnalysisStatus`
- `SeverityLevel` matches exactly between systems
- `TestType` includes all analysis types from main app

### 2. **Compatible Data Structures**
- All models can be serialized to JSON that the main app expects
- Field names match database column names where applicable
- Additional utility functions convert between formats

### 3. **Conversion Functions**
- `convert_testing_status_to_analysis_status()` - Maps container statuses to main app
- `create_main_app_compatible_result()` - Creates main app database-ready results

## Usage Examples

### Creating a Security Test Request
```python
from models import SecurityTestRequest, TestType

request = SecurityTestRequest(
    model="anthropic_claude-3.7-sonnet",
    app_num=1,
    test_type=TestType.SECURITY_BACKEND,
    tools=["bandit", "safety", "pylint"],
    bandit_enabled=True,
    safety_enabled=True,
    pylint_enabled=False
)
```

### Processing Results for Main App
```python
from models import SecurityTestResult, create_main_app_compatible_result

# Create container result
result = SecurityTestResult(
    test_id="test-123",
    status=TestingStatus.COMPLETED,
    tools_used=["bandit", "safety"]
)

# Convert for main app database storage
main_app_data = create_main_app_compatible_result(result)

# main_app_data now contains all fields expected by SecurityAnalysis model
```

## Maintenance

### Synchronization Checks
Run the synchronization script to check compatibility:
```bash
python ../../../sync_models.py --report
```

### When to Update
Update these models when:
1. Main app adds new analysis types
2. Database schema changes in main app
3. New status values are added
4. API contracts change

### Critical Compatibility Points
1. **Status Mapping**: `TIMEOUT` status maps to `FAILED` for main app
2. **Severity Counts**: Both `critical_count` and `critical_severity_count` fields are provided
3. **Tool Flags**: Boolean fields match main app's SecurityAnalysis model
4. **JSON Serialization**: All `to_dict()` methods produce main app compatible output

## Architecture Benefits

1. **Loose Coupling**: Containers can evolve independently while maintaining compatibility
2. **Type Safety**: Full type hints for development and IDE support
3. **Validation**: Built-in validation and conversion functions
4. **Extensibility**: Can add container-specific fields without breaking main app
5. **Testing**: Models can be unit tested for compatibility

## Error Handling

The models include robust error handling:
- Graceful degradation for unknown status values
- Default values for missing fields
- Validation of required fields before conversion

This approach ensures that even if the container models evolve, they remain compatible with the main application's expectations.
