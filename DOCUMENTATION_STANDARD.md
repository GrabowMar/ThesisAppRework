# Python Documentation Standard

## Overview

This document defines the standardized documentation approach for the ThesisAppRework codebase. All Python code should follow these conventions to ensure consistency and maintainability.

## Documentation Style

**Primary Style**: Google-style docstrings

**Format**: Use RST-style headers (`===`) for module-level docstrings

## Module-Level Docstrings

Every Python file must have a module-level docstring at the top, immediately after any `__future__` imports.

### Format

```python
"""
Module Title
============

Brief description of the module's purpose (1-2 sentences).

Detailed description explaining:
- Key functionality provided
- Main classes/functions
- Relationships to other modules
- Important design decisions

Optional sections:
- Examples
- Architecture notes
- Related modules
"""
```

### Example

```python
"""
Analysis Models
===============

Database models for storing various types of analysis results including security
analysis, performance testing, ZAP scanning, and AI-powered code analysis.

This module defines SQLAlchemy ORM models that track the execution and results of:
- SecurityAnalysis: Comprehensive security tool configurations and findings
- PerformanceTest: Load testing metrics and performance benchmarks
- ZAPAnalysis: OWASP ZAP security scan results
- OpenRouterAnalysis: AI-powered code quality assessments
"""
```

## Function/Method Docstrings

### Required Sections

All non-trivial functions must include:

1. **Summary** - One-line description
2. **Args** - Parameter documentation (if parameters exist)
3. **Returns** - Return value documentation (if function returns)
4. **Raises** - Exception documentation (if function raises exceptions)

### Format Template

```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """Brief one-line summary of what the function does.

    Optional longer description providing more context about the function's
    behavior, algorithm, or important implementation details.

    Args:
        param1: Description of first parameter
        param2: Description of second parameter, including:
            - Any constraints or valid values
            - Default behavior if applicable

    Returns:
        Description of the return value. For complex types, describe
        the structure:
            {
                'key1': 'description',
                'key2': 'description'
            }

    Raises:
        ValueError: When param1 is negative
        CustomError: When specific condition occurs

    Examples:
        >>> function_name(1, 2)
        {'result': 3}
    """
```

### Complexity-Based Requirements

| Function Complexity | Required Documentation |
|---------------------|------------------------|
| Simple (1-5 lines, obvious purpose) | Summary only |
| Standard (6-20 lines, single purpose) | Summary + Args + Returns |
| Complex (21-50 lines, multiple steps) | Full Google style + algorithm notes |
| Very Complex (50+ lines) | Full docs + detailed examples + architecture notes |

## Class Docstrings

### Format

```python
class ClassName:
    """Brief description of the class purpose.

    Detailed explanation of:
    - What the class represents or manages
    - Key responsibilities
    - Important relationships with other classes

    Attributes:
        attr1: Description of attribute
        attr2: Description of attribute

    Examples:
        >>> obj = ClassName(param1, param2)
        >>> obj.method()
    """
```

### Dataclass Format

```python
@dataclass
class DataClassName:
    """Brief description of the data structure.

    Attributes:
        field1: Description and valid values
        field2: Description and constraints
    """
    field1: str
    field2: int
```

## API Endpoint Documentation

API route handlers require additional documentation for the HTTP interface:

```python
@bp.route('/api/v1/resource/<int:id>', methods=['GET'])
def get_resource(id: int):
    """Retrieve a resource by ID.

    Endpoint: GET /api/v1/resource/<id>

    Path Parameters:
        id: Resource identifier (integer)

    Query Parameters:
        include_details: Include full details (bool, default: false)

    Request Body:
        None

    Response:
        200 OK:
            {
                "success": true,
                "data": {
                    "id": 1,
                    "name": "Resource Name"
                }
            }
        404 Not Found:
            {
                "success": false,
                "error": "Resource not found"
            }

    Returns:
        JSON response with resource data

    Raises:
        NotFoundError: When resource doesn't exist
    """
```

## Type Hints

All functions should include type hints:

```python
from typing import Dict, List, Optional, Any

def process_data(
    data: Dict[str, Any],
    options: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Process the input data with optional filters."""
    pass
```

## Common Patterns

### JSON Helper Methods

```python
def get_metadata(self) -> Dict[str, Any]:
    """Return metadata JSON as dictionary.

    Returns:
        Parsed metadata dictionary, or empty dict if parsing fails.
    """
    if not self.metadata_json:
        return {}
    try:
        data = json.loads(self.metadata_json)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}

def set_metadata(self, metadata: Optional[Dict[str, Any]]) -> None:
    """Persist metadata dictionary as JSON.

    Args:
        metadata: Metadata dictionary to store, or None to clear.
    """
    self.metadata_json = json.dumps(metadata or {})
```

### Service Methods

```python
def execute_operation(
    self,
    input_data: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute the primary operation on input data.

    This method performs [detailed description of what it does].

    Args:
        input_data: Dictionary containing:
            - 'field1': Description of required field
            - 'field2': Description of optional field
        options: Optional configuration including:
            - 'timeout': Operation timeout in seconds (default: 30)
            - 'retry': Enable retry on failure (default: True)

    Returns:
        Result dictionary with structure:
            {
                'status': 'success' | 'failed',
                'data': {...},
                'metadata': {...}
            }

    Raises:
        ValidationError: When input_data is invalid
        TimeoutError: When operation exceeds timeout
        ServiceError: When external service fails

    Examples:
        >>> result = service.execute_operation(
        ...     {'field1': 'value'},
        ...     {'timeout': 60}
        ... )
    """
```

## Documentation Maintenance

### When to Update Documentation

1. **Adding new code**: Document before commit
2. **Modifying function signature**: Update Args section
3. **Changing return type**: Update Returns section
4. **Adding exception handling**: Update Raises section
5. **Refactoring**: Verify docs still accurate

### Documentation Review Checklist

- [ ] Module docstring present and accurate
- [ ] All public functions have docstrings
- [ ] All parameters documented in Args section
- [ ] Return value documented
- [ ] Exceptions documented in Raises section
- [ ] Complex logic has explanatory comments
- [ ] Type hints present and correct
- [ ] Examples provided for complex APIs

## Tools and Validation

### Recommended Tools

1. **pydocstyle**: Validate docstring conventions
2. **pylint**: Check for missing docstrings
3. **mypy**: Validate type hints
4. **sphinx**: Generate HTML documentation

### Pre-commit Checks

```bash
# Check docstring style
pydocstyle src/app/

# Check for missing docstrings
pylint src/app/ --disable=all --enable=missing-docstring

# Validate type hints
mypy src/app/
```

## Priority Documentation Order

### Tier 1 (Critical - Must Have)

1. All public API endpoints
2. All service layer public methods
3. Complex functions (50+ lines)
4. All exception-raising code

### Tier 2 (High Priority)

5. All remaining service functions
6. Helper/utility functions (20+ lines)
7. Private methods in public classes
8. Database models

### Tier 3 (Standard Priority)

9. Simple getters/setters
10. Minor helper functions
11. Test utilities

## Examples from Codebase

### Good Examples

**Model with Complete Documentation**:
```python
"""
Core Models
===========

Core database models for AI model capabilities, generated applications, and port configurations.

This module contains the fundamental ORM models that power the application:
- ModelCapability: AI model metadata, pricing, and capability tracking
- GeneratedApplication: Full lifecycle tracking of AI-generated applications
- PortConfiguration: Docker port allocation and management
- GeneratedCodeResult: Code generation result persistence

These models form the backbone of the research platform's data persistence layer.
"""
```

**Service Method with Full Documentation**:
```python
def build_summary_payload() -> Dict[str, Any]:
    """Return aggregate counts and recent deltas for dashboard metrics.

    Computes total counts and time-windowed deltas (24h, 7d) for:
    - Models registered in system
    - Applications generated
    - Security analyses completed
    - Performance tests executed

    Returns:
        Dictionary containing:
            {
                "generated_at": ISO timestamp,
                "totals": {
                    "models": int,
                    "applications": int,
                    "security": int,
                    "performance": int
                },
                "recent": {
                    "last_24h": {...},
                    "last_7d": {...}
                }
            }
    """
```

## Anti-Patterns to Avoid

### ❌ Too Brief

```python
def process(data):
    """Process data."""
    pass
```

### ❌ Missing Args/Returns

```python
def calculate(x, y, z):
    """Calculate result from inputs."""
    return x + y * z
```

### ❌ Outdated Documentation

```python
def get_user(id):
    """Get user by ID.

    Args:
        username: User's username  # Wrong parameter name!
    """
    return User.query.get(id)
```

### ✅ Correct

```python
def calculate_total(subtotal: float, tax_rate: float, discount: float = 0.0) -> float:
    """Calculate final total with tax and optional discount.

    Args:
        subtotal: Pre-tax amount
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%)
        discount: Optional discount amount to subtract (default: 0.0)

    Returns:
        Final total after tax and discount

    Examples:
        >>> calculate_total(100.0, 0.08, 10.0)
        98.0
    """
    return (subtotal * (1 + tax_rate)) - discount
```

## Summary

Following these documentation standards ensures:

- **Consistency** across the codebase
- **Maintainability** for future developers
- **Discoverability** through IDE autocomplete
- **Reliability** by documenting contracts and exceptions
- **Onboarding** efficiency for new team members

All new code must follow these standards. Existing code should be gradually updated to meet these standards, prioritizing public APIs and complex functions first.
