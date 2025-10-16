# Prompt Template for Frontend Generation

{scaffolding_info}

---

## Application Specification

**Application Name:** {app_name}

**Description:** {app_description}

---

## Frontend Requirements

**IMPORTANT:** You MUST implement ALL of the following requirements completely. This task is critical to the success of the project.

{frontend_requirements}

---

## Implementation Guidelines

**Think step by step** as you implement each requirement:

### Component Structure
1. Use functional components with React hooks
2. Implement proper state management with useState
3. Use useEffect for side effects and data fetching
4. Keep components organized and readable

### API Integration
1. Use axios for HTTP requests
2. Handle loading states during API calls
3. Show error messages for failed requests
4. Use async/await for cleaner code

### User Experience
1. Add loading indicators during operations
2. Show success/error feedback to users
3. Implement proper form validation
4. Use confirmation dialogs for destructive actions

### Styling
1. Use className for CSS classes (App.css is available)
2. Keep styles clean and responsive
3. Use semantic HTML elements
4. Ensure mobile-friendly design

### Code Quality
1. Add comments for complex logic
2. Use descriptive variable and function names
3. Handle edge cases and errors
4. Keep code DRY (Don't Repeat Yourself)

---

## Important Constraints

✅ **DO:**
1. Generate complete, working React App.jsx component
2. Include all necessary imports (React, axios, useState, useEffect)
3. Implement all specified frontend requirements
4. Add proper error handling and loading states
5. Use modern React patterns and best practices
6. Make API calls to `/api/*` endpoints (proxy configured)
7. Implement every requirement listed above without exception

❌ **DO NOT:**
1. Generate index.html, package.json, vite.config.js, or infrastructure
2. Create separate component files (single App.jsx only)
3. Include CSS in the JSX (use className, App.css exists)
4. Regenerate main.jsx or React initialization
5. Skip any requirements or use placeholder comments like TODO or FIXME

---

## Output Format

Generate ONLY the JSX/JavaScript code in a single code block:

```jsx
// Your complete React App.jsx component here
// This will replace the scaffolding's App.jsx
```
