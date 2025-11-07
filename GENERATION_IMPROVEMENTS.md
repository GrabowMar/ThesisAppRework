"""
Generation Quality Improvements - Action Plan
==============================================

Based on validation of generated apps, here are the issues and fixes:

## Issues Found:

### 1. App2 Backend Failure
- **Problem**: Markdown fence validation error prevented code merge
- **Status**: FIXED in app3 by validating AFTER fence stripping
- **Evidence**: App3 has full 261-line backend, app2 has only scaffold

### 2. Response Format Mismatch Risk
- **Problem**: Backend might return different format than frontend expects
- **Current**: Frontend expects `response.data.todos` 
- **Risk**: If backend returns different structure, app breaks
- **Solution**: Add explicit response format validation

### 3. SQLite in /tmp Directory
- **Problem**: Data lost on container restart
- **Current**: `'sqlite:////tmp/todo_app.db'`
- **Better**: Use volume-mounted path or relative path

### 4. Complex Frontend State
- **Problem**: 10+ useState hooks makes debugging hard
- **Impact**: Medium - works but hard to maintain
- **Solution**: Guide AI to use reducer pattern for complex state

### 5. Missing API Contract Validation
- **Problem**: No guarantee frontend/backend APIs match
- **Solution**: Add response structure validation in tests

## Improvements to Implement:

### Priority 1: Critical (Prevents Working Apps)
✓ 1. Markdown fence stripping before validation - DONE
□ 2. Verify setup_app() is called properly in __main__
□ 3. Add response format tests to validation

### Priority 2: Important (Improves Reliability)  
□ 4. Update templates to guide better SQLite paths
□ 5. Add API contract checking between frontend/backend
□ 6. Improve error messages in validation
□ 7. Add truncation detection and warnings

### Priority 3: Nice-to-Have (Quality of Life)
□ 8. Guide AI toward simpler state management patterns
□ 9. Add automatic dependency inference improvements
□ 10. Template hints for Docker volume usage

## Template Improvements Needed:

### Backend Template (backend.md.jinja2):
1. **Database path guidance**:
   ```
   Use 'sqlite:///app.db' (relative path) instead of '/tmp/...'
   This ensures data persists across container restarts when properly mounted.
   ```

2. **Response format contract**:
   ```
   All list endpoints MUST return:
   {
     "items": [...],  // or "todos", "posts", etc. matching the entity
     "total": 123,
     "page": 1,
     "per_page": 25
   }
   ```

3. **Explicit setup_app call**:
   ```
   The scaffold will call setup_app(app) if it exists.
   Your setup_app MUST:
   - Initialize db with app
   - Create tables with db.create_all()
   - Use app.app_context()
   ```

### Frontend Template (frontend.md.jinja2):
1. **State management guidance**:
   ```
   For apps with >5 state values, use useReducer instead of multiple useState.
   Example: const [state, dispatch] = useReducer(reducer, initialState);
   ```

2. **API client consistency**:
   ```
   Always use axios for consistency.
   Always handle response.data properly.
   Always check for response.data.items or response.data.[entity] arrays.
   ```

## Validation Improvements:

### Add to validate_generated_code():
1. Check if db instance matches setup_app usage
2. Verify route response formats match frontend expectations  
3. Detect truncation (finish_reason=='length')
4. Warn about /tmp database paths
5. Check if all CRUD operations present (GET, POST, PUT, DELETE)

### Add Integration Test:
1. Parse backend routes and response formats
2. Parse frontend API calls
3. Match them up and report mismatches
4. Example: "Frontend calls GET /api/todos expecting .todos but backend returns .items"

## Next Steps:

1. ✓ Fix markdown fence issue - DONE
2. Update backend template with database path guidance
3. Update both templates with response format contracts
4. Add truncation detection and auto-retry with more tokens
5. Add API contract validation to validate_generated_apps.py
6. Test with multiple models to ensure consistency
"""
