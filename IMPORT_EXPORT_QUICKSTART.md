# Import/Export Quick Start Guide

## 📦 What Was Exported

### Main Export File
**`thesis_export_20260120_072049.zip`** (9.82 MB)
- ✅ 147 analysis result files
- ✅ 2,100 generated app source files
- ✅ 105 AI-generated applications
- ✅ Complete metadata

### Backup File
**`results_backup_20260120_070406.tar.gz`** (7.6 MB)
- Original analysis results backup (created before any changes)

---

## 🎯 Quick Actions

### Export Data (Web UI)
1. Open browser → `http://localhost:5000`
2. Go to **Automation Pipeline** page
3. Look for **"Results Management"** card in right sidebar
4. Click **Export** button
5. Choose what to export:
   - ☑ Analysis Results
   - ☑ Generated Apps
6. Click **Export** → file downloads automatically

### Import Data (Web UI)
1. Same steps 1-3 above
2. Click **Import** button
3. Select ZIP file
4. Choose options:
   - ☑ Create backup (recommended)
   - ☐ Overwrite existing
5. Click **Import** → shows progress and results

---

## 📊 Dataset Summary

| Category | Count | Size |
|----------|-------|------|
| Analysis Results | 147 files | ~96 MB (uncompressed) |
| Generated Apps | 2,100 files | ~14 MB |
| Total in Export | 2,247 files | 9.82 MB (compressed) |

### Models Included
- qwen_qwen3-coder-30b-a3b-instruct (23 apps)
- deepseek_deepseek-r1-0528 (20 apps)
- google_gemini-2.5-flash (20 apps)
- anthropic_claude-4.5-sonnet (10 apps)
- openai_gpt-5-mini (10 apps)
- +2 more models

---

## 🔧 API Usage (Optional)

### Export via API
```bash
curl -X POST http://localhost:5000/api/automation/results/export \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "include_results": true,
    "include_apps": true,
    "include_metadata": true
  }' \
  --output thesis_export.zip
```

### Import via API
```bash
curl -X POST http://localhost:5000/api/automation/results/import \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@thesis_export.zip" \
  -F "backup=true" \
  -F "overwrite=false"
```

---

## 📁 File Locations

```
/opt/thesisapp/
├── thesis_export_20260120_072049.zip  ← MAIN EXPORT (download this!)
├── results_backup_20260120_070406.tar.gz  ← Safety backup
├── EXPORT_README.md                   ← Full documentation
├── IMPORT_EXPORT_QUICKSTART.md        ← This file
├── results/                           ← Analysis results (96 MB)
└── generated/apps/                    ← Generated apps (14 MB)
```

---

## ⚠️ Important Notes

1. **Backup Created**: Your original data is backed up before any changes
2. **Smart Exclusions**: Export automatically excludes:
   - `node_modules/` (can reinstall with `npm install`)
   - `.venv/`, `venv/` (can recreate virtual env)
   - `__pycache__/`, `.git/` (temporary/cache files)
3. **Safe Import**: Import with backup enabled (default) creates safety backup first
4. **Conflict Handling**: Uncheck "overwrite" to skip existing files

---

## 🚀 Next Steps

1. **Download Export**: Transfer `thesis_export_20260120_072049.zip` to safe location
2. **Test Import**: Try importing on another machine to verify portability
3. **Keep Backups**: Store both export and backup files safely
4. **Use Web UI**: Access via Automation Pipeline page for easy export/import

---

**Questions?** See `EXPORT_README.md` for complete documentation.

**Created**: 2026-01-20  
**Platform**: ThesisAppRework v1.0
