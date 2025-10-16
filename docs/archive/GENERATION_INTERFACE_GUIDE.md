# Sample Generator - Unified Generation Interface Guide

## Quick Start

The new unified generation interface combines individual and batch generation into one streamlined workflow.

### Basic Workflow

```
1. Select Templates (Single/Multiple/All)
   ↓
2. Select Models (Single/Multiple/All) - Only scaffolded models shown
   ↓
3. Configure Options (Scope, Workers, Timeout, Backup)
   ↓
4. Review Summary (Templates × Models = Total Jobs)
   ↓
5. Preview or Start Generation
   ↓
6. Monitor Active Generations
```

## Interface Sections

### 1. Template Selection (Left Column)

**Mode Options:**
- **Single** - Choose one template from dropdown
- **Multiple** - Select multiple templates with checkboxes
- **All** - Select all available templates

**Features:**
- Live preview of template content
- Selection count indicator
- Toggle all button (Multiple mode)
- Reload templates button

### 2. Model Selection (Left Column)

**Mode Options:**
- **Single** - Choose one model from dropdown
- **Multiple** - Select multiple models with checkboxes
- **All** - Select all scaffolded models

**Features:**
- Only shows models with scaffolded projects
- Selection count indicator
- Toggle all button (Multiple mode)
- Refresh models button

**Important:** Only scaffolded models are shown to prevent generation errors.

### 3. Generation Options (Right Column)

**Scope Selection:**
- ☑️ Frontend - Generate frontend code
- ☑️ Backend - Generate backend code
- ☐ Tests - Generate test files

**Advanced Settings:**
- **Concurrent Workers** (1-10) - Parallel API requests
- **Timeout** (60-900s) - Per-request timeout
- **Create Backups** - Backup existing files before overwriting

### 4. Generation Summary (Right Column)

Real-time calculation showing:
- **Templates**: Number of templates selected
- **Models**: Number of models selected
- **Total Jobs**: Templates × Models
- **Est. Time**: Estimated completion time

### 5. Action Buttons (Right Column)

**Preview Generation Plan**
- Shows what will be generated
- Lists all template/model combinations
- Displays warnings about file overwrites

**Start Generation**
- Initiates generation process
- Disabled until valid selections made
- Confirms before starting

### 6. Active Generations

Real-time tracking of running generations:
- Progress bars for each job
- Status messages
- Auto-refreshes every 5 seconds
- Shows model × template combinations

### 7. Recent Generations

Historical table showing last 20 runs:
- Timestamp
- Template name
- Model name
- Status badge
- Duration
- View details button

## Common Use Cases

### Use Case 1: Single App Generation

**Goal:** Generate one application with one model

**Steps:**
1. Mode: **Single** template, **Single** model
2. Select: Template #5, Model "openai/gpt-4o"
3. Options: Frontend ✓, Backend ✓
4. Click: **Start Generation**

**Result:** 1 job (App 5 with GPT-4o)

---

### Use Case 2: Test Multiple Models

**Goal:** Generate the same app with different models

**Steps:**
1. Mode: **Single** template, **Multiple** models
2. Select: Template #3, Models ["gpt-4o", "claude-3.5-sonnet", "gemini-1.5-pro"]
3. Options: Frontend ✓, Backend ✓, Workers: 3
4. Click: **Start Generation**

**Result:** 3 jobs (App 3 with 3 different models)

---

### Use Case 3: Generate Multiple Apps

**Goal:** Generate several apps with one model

**Steps:**
1. Mode: **Multiple** templates, **Single** model
2. Select: Templates [1, 2, 3, 5], Model "gpt-4o"
3. Options: Frontend ✓, Backend ✓, Workers: 2
4. Click: **Start Generation**

**Result:** 4 jobs (4 apps with GPT-4o)

---

### Use Case 4: Full Batch Generation

**Goal:** Generate all templates with all models

**Steps:**
1. Mode: **All** templates, **All** models
2. Options: Frontend ✓, Backend ✓, Workers: 5
3. Review: Check summary (e.g., 30 templates × 5 models = 150 jobs)
4. Click: **Preview Generation Plan** to confirm
5. Click: **Start Generation** and confirm

**Result:** 150 jobs (all combinations)

---

### Use Case 5: Backend Only Generation

**Goal:** Generate only backend code for testing

**Steps:**
1. Mode: **Single** or **Multiple** templates/models
2. Options: Frontend ✗, Backend ✓, Tests ✗
3. Click: **Start Generation**

**Result:** Only backend files generated

## Tips & Best Practices

### Performance Tips

1. **Adjust Workers**: 
   - Low: 1-2 workers for stability
   - Medium: 3-5 workers for balanced throughput
   - High: 6-10 workers for maximum speed (watch rate limits!)

2. **Timeout Settings**:
   - Quick apps: 60-120 seconds
   - Complex apps: 180-300 seconds
   - Very complex: 300-600 seconds

3. **Batch Size**:
   - Small batches (< 10 jobs): Run immediately
   - Medium batches (10-50 jobs): Review preview first
   - Large batches (> 50 jobs): Run during off-hours

### Selection Tips

1. **Template Selection**:
   - Use **Single** for testing/development
   - Use **Multiple** for specific app comparisons
   - Use **All** for complete model evaluation

2. **Model Selection**:
   - Use **Single** for focused development
   - Use **Multiple** for model comparison
   - Use **All** for comprehensive benchmarking

3. **Scope Selection**:
   - Frontend + Backend: Complete application
   - Backend only: API-focused development
   - Tests only: Test suite generation

### Safety Tips

1. **Always Enable Backups**: Protects existing work
2. **Preview First**: Review generation plan before large batches
3. **Start Small**: Test with 1-2 jobs before running large batches
4. **Monitor Progress**: Watch active generations for issues
5. **Check Scaffolding**: Ensure models are properly scaffolded first

## Keyboard Shortcuts

Currently not implemented, but planned:

- `Ctrl/Cmd + Enter` - Start generation
- `Ctrl/Cmd + P` - Preview generation plan
- `Ctrl/Cmd + A` - Toggle all templates/models
- `Escape` - Cancel/close modal

## Troubleshooting

### Problem: "Start Generation" button is disabled

**Solutions:**
- Ensure at least one template is selected
- Ensure at least one model is selected
- Check that models list loaded (not empty)
- Verify templates list loaded (not empty)

---

### Problem: No models appear in model selector

**Cause:** No scaffolded models found

**Solutions:**
1. Go to "Scaffolding Generation" tab (Step 1)
2. Generate project scaffolds for desired models
3. Return to generation tab and refresh models

---

### Problem: Generation fails immediately

**Causes:**
- Model not scaffolded
- Invalid template
- Network issues
- API rate limits

**Solutions:**
- Verify model is in scaffolded list
- Check template preview loads correctly
- Reduce concurrent workers
- Increase timeout setting
- Check API key is configured

---

### Problem: Progress stuck at 0%

**Causes:**
- Backend service not running
- WebSocket connection failed
- Task queue not processing

**Solutions:**
1. Check console for errors (F12)
2. Refresh the page
3. Restart backend services
4. Check task queue status in Logs tab

---

### Problem: Timeout errors during generation

**Solutions:**
- Increase timeout setting (e.g., 300 → 600 seconds)
- Reduce concurrent workers (e.g., 5 → 2)
- Check network stability
- Verify API endpoint is responsive

## Advanced Features

### Model Overrides

Use the sidebar "Model Settings" card to override default parameters:
- Temperature
- Top P / Top K
- Penalties
- Max tokens

Leave blank to use service defaults.

### Batch Control

During active generation:
- View real-time progress
- Monitor individual jobs
- Check for failures
- Cancel if needed (via Logs tab)

## API Integration

The unified interface uses these endpoints:

```
GET  /api/sample-gen/templates              # Load templates
GET  /api/sample-gen/models?mode=scaffolded # Load scaffolded models
GET  /api/sample-gen/templates/app/{num}.md # Preview template
POST /api/sample-gen/generate               # Single generation
POST /api/sample-gen/generate/batch         # Batch generation
GET  /api/sample-gen/status                 # Active generations
GET  /api/sample-gen/results                # Recent results
```

## Related Documentation

- [Architecture Overview](./ARCHITECTURE.md)
- [Sample Generator Rework](./SAMPLE_GENERATOR_REWORK.md)
- [API Reference](./API_REFERENCE.md)
- [User Guide](./USER_GUIDE.md)

## Support

For issues or questions:
1. Check Logs tab for error details
2. Review Recent Generations for patterns
3. Verify scaffolding is complete
4. Check API configuration
5. Review console logs (F12)
