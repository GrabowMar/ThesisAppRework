# Dead Code Cleanup - Quick Reference

## 🚀 Quick Start

### Run Analysis
```bash
# Full analysis
python scripts/find_dead_code.py

# Quick dry-run of cleanup
pwsh -NoProfile -ExecutionPolicy Bypass -File .\cleanup.ps1 -DryRun -All
```

### Safe Cleanup (Recommended First Steps)
```bash
# 1. Clean bytecode files only
pwsh -NoProfile -ExecutionPolicy Bypass -File .\cleanup.ps1 -CleanBytecode

# 2. Verify everything still works
pytest -q
python scripts/http_smoke.py
```

## 📊 Current State

| Category | Count | Size | Action |
|----------|-------|------|--------|
| Python files | 129 | - | ✅ Analyzed |
| Bloated files (>50KB) | 6 | 470KB total | ⚠️ Refactor needed |
| `__pycache__` dirs | 248 | - | 🗑️ Delete |
| `.pyc` files | 2,264 | 36 MB | 🗑️ Delete |
| Archive docs | 46 | 0.45 MB | 📦 Archive/Delete |
| High coupling files | 10 | - | ⚠️ Refactor |
| Legacy compatibility | Active | - | 🔄 Migration needed |

## 🎯 Priority Actions

### ✅ Safe to Do Now (Zero Risk)
1. **Clean bytecode files** - 36 MB savings
   ```bash
   pwsh .\cleanup.ps1 -CleanBytecode
   ```

2. **Update .gitignore** - Prevent future bytecode commits
   ```bash
   pwsh .\cleanup.ps1 -All
   ```

### ⚠️ Review Before Doing (Low Risk)
3. **Archive old documentation** - 0.45 MB, historical value only
   ```bash
   pwsh .\cleanup.ps1 -ArchiveDocs
   ```

### 🔄 Requires Planning (Medium Risk)
4. **Remove template compatibility layer**
   - Used in 20+ files
   - Plan migration over 2-3 weeks
   - See CLEANUP_REPORT.md Phase 1-3

5. **Refactor bloated files**
   - Start with `sample_generation_service.py` (170KB)
   - Split into focused modules
   - Requires comprehensive tests

## 📋 Files to Review

### Bloated Files Requiring Refactoring
```
src/app/services/sample_generation_service.py    170.4 KB  35 imports
src/app/services/analyzer_integration.py          61.8 KB  LEGACY markers
src/app/tasks.py                                  61.0 KB  53 imports
src/app/services/task_execution_service.py        60.2 KB
src/app/routes/jinja/analysis.py                  59.3 KB
src/app/services/analysis_inspection_service.py   56.0 KB  LEGACY markers
```

### Legacy/Suspicious Files
```
src/app/utils/template_paths.py                  Legacy compatibility layer
src/app/services/analyzer_integration.py         Contains LEGACY markers
src/app/services/analysis_inspection_service.py  Contains LEGACY markers
src/app/services/model_sync_service.py           Contains LEGACY markers
```

### High Import Coupling
```
src/app/tasks.py                    53 imports
src/app/routes/api/dashboard.py    51 imports
src/app/models/__init__.py          40 imports (OK - barrel export)
src/app/factory.py                  37 imports
```

## 🛠️ Tools Created

### 1. `scripts/find_dead_code.py`
Full Python codebase analyzer
- Detects bloated files
- Finds legacy patterns
- Analyzes import coupling
- Identifies suspicious files

### 2. `cleanup.ps1`
Automated cleanup script with safety checks
- `-DryRun`: Preview changes
- `-CleanBytecode`: Remove Python bytecode
- `-ArchiveDocs`: Archive old documentation
- `-All`: Complete cleanup

### 3. `CLEANUP_REPORT.md`
Comprehensive cleanup guide with:
- Detailed analysis of each issue
- Step-by-step migration plans
- Risk assessments
- Timeline recommendations

## ⏱️ Estimated Effort

| Task | Time | Risk | Impact |
|------|------|------|--------|
| Clean bytecode | 5 min | None | Low |
| Archive docs | 30 min | Low | Low |
| Remove template compat | 2-3 weeks | Medium | High |
| Refactor services | 4-6 weeks | Medium | High |
| Reduce coupling | Ongoing | Low | Medium |

## 🎯 Recommended Timeline

### Week 1 (Immediate)
- [x] Run analysis tools
- [ ] Clean bytecode files
- [ ] Review and archive old docs
- [ ] Run tests to verify

### Week 2-3 (Short-term)
- [ ] Audit template path usage
- [ ] Create template migration plan
- [ ] Start refactoring largest service

### Month 2 (Medium-term)
- [ ] Complete template migration
- [ ] Remove legacy compatibility
- [ ] Refactor 2-3 bloated files

### Ongoing (Long-term)
- [ ] Establish file size limits
- [ ] Monthly cleanup routine
- [ ] Quarterly refactoring

## 🧪 Testing Checklist

Before each cleanup action:
```bash
# 1. Run full test suite
pytest -v

# 2. Run smoke tests
python scripts/http_smoke.py

# 3. Check for errors
pytest --lf  # Last failed

# 4. Coverage check (optional)
pytest --cov=src --cov-report=term-missing
```

## 📈 Success Metrics

After cleanup completion, you should see:
- ✅ No `__pycache__` or `.pyc` files in repo
- ✅ No files >50KB (except data files)
- ✅ No files with >30 imports
- ✅ No legacy compatibility layers
- ✅ <50 files in docs/
- ✅ Clean `git status`

## 🆘 Rollback Plan

If something breaks:
```bash
# 1. Check what changed
git status
git diff

# 2. Revert specific file
git checkout HEAD -- path/to/file

# 3. Revert all changes
git reset --hard HEAD

# 4. Restore from backup (if created)
# (cleanup.ps1 doesn't modify code, only deletes generated files)
```

## 📚 Additional Resources

- **Full Report**: `CLEANUP_REPORT.md`
- **Analysis Script**: `scripts/find_dead_code.py`
- **Cleanup Script**: `cleanup.ps1`
- **Project Docs**: `docs/`

## 🔗 Related Commands

```bash
# Find large files
Get-ChildItem -Recurse -File | Where { $_.Length -gt 50KB } | Sort Length -Desc

# Find TODO/FIXME
Get-ChildItem -Recurse -Filter *.py | Select-String "TODO|FIXME|XXX"

# Count lines of code
Get-ChildItem -Recurse -Filter *.py | Get-Content | Measure-Object -Line

# Find unused imports (requires pylint)
pylint --disable=all --enable=unused-import src/

# Check for security issues
bandit -r src/
```

## ✅ Done!

You now have:
1. ✅ Complete analysis of dead code
2. ✅ Automated cleanup tools
3. ✅ Detailed cleanup plan
4. ✅ Risk assessments
5. ✅ Testing procedures

**Next Step**: Run `pwsh .\cleanup.ps1 -CleanBytecode` to start with the safest cleanup!
