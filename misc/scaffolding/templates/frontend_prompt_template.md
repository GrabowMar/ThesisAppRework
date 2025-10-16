# Prompt Template for Frontend Generation

{scaffolding_info}

---

## Application Specification

**Application Name:** {app_name}

**Description:** {app_description}

---

## Frontend Requirements

{frontend_requirements}

---

## Implementation Guidelines

### Component Structure
- Use functional components with React hooks
- Implement proper state management with useState
- Use useEffect for side effects and data fetching
- Keep components organized and readable

### API Integration
- Use axios for HTTP requests
- Handle loading states during API calls
- Show error messages for failed requests
- Use async/await for cleaner code

### User Experience
- Add loading indicators during operations
- Show success/error feedback to users
- Implement proper form validation
- Use confirmation dialogs for destructive actions

### Styling
- Use className for CSS classes (App.css is available)
- Keep styles clean and responsive
- Use semantic HTML elements
- Ensure mobile-friendly design

### Code Quality
- Add comments for complex logic
- Use descriptive variable and function names
- Handle edge cases and errors
- Keep code DRY (Don't Repeat Yourself)

---

## Important Constraints

✅ **DO:**
- Generate complete, working React App.jsx component
- Include all necessary imports (React, axios, useState, useEffect)
- Implement all specified frontend requirements
- Add proper error handling and loading states
- Use modern React patterns and best practices
- Make API calls to `/api/*` endpoints (proxy configured)

❌ **DO NOT:**
- Generate index.html, package.json, vite.config.js, or infrastructure
- Create separate component files (single App.jsx only)
- Include CSS in the JSX (use className, App.css exists)
- Regenerate main.jsx or React initialization

---

## Output Format

Generate ONLY the JSX/JavaScript code in a single code block:

```jsx
// Your complete React App.jsx component here
// This will replace the scaffolding's App.jsx
```
