# Tabler.io Component Design System Guide

**Complete reference for generating consistent, beautiful UI components using Tabler's design patterns**

---

## Overview

Tabler is a free and open-source HTML Dashboard UI Kit built on Bootstrap 5, featuring hundreds of responsive components and multiple layouts. Every component is created with attention to detail to make interfaces beautiful and user-friendly. The choice of colors and design harmony contributes to nice first impressions and encourages user engagement.

### Core Philosophy
- **Modern & Clean**: Professional aesthetic with attention to detail
- **Bootstrap Foundation**: Built on Bootstrap 5 for compatibility and flexibility  
- **Responsive First**: Compatible with all modern browsers and screen sizes
- **Customizable**: Easy to modify using SCSS variables and CSS classes
- **Accessibility**: Follows WAI-ARIA standards with keyboard navigation support

---

## Foundation Elements

### Color System

Tabler provides a comprehensive color palette for creating harmonious designs that indicate different states and suggest user actions.

#### Primary Color Palette
```scss
// Core Brand Colors
$primary: #206bc4;    // Main brand color
$secondary: #6c757d;  // Supporting gray
$success: #2fb344;    // Success states
$info: #4299e1;       // Information states  
$warning: #f76707;    // Warning states
$danger: #d63384;     // Error/danger states
```

#### Extended Color Palette
```scss
// Social & Contextual Colors
$blue: #206bc4;
$azure: #4299e1; 
$indigo: #4263eb;
$purple: #8b5cf6;
$pink: #d63384;
$red: #dc3545;
$orange: #fd7e14;
$yellow: #f59f00;
$lime: #74b816;
$green: #2fb344;
$teal: #17a2b8;
$cyan: #17a2b8;
```

#### Gray Palette
```scss
// Neutral Grays for backgrounds and text
$gray-50: #f8fafc;
$gray-100: #f1f5f9;
$gray-200: #e2e8f0; 
$gray-300: #cbd5e1;
$gray-400: #94a3b8;
$gray-500: #64748b;
$gray-600: #475569;
$gray-700: #334155;
$gray-800: #1e293b;
$gray-900: #0f172a;
```

#### Color Usage Guidelines
- **Primary**: Main actions, links, active states
- **Secondary**: Supporting content, disabled states
- **Success**: Confirmations, completed actions
- **Warning**: Caution, pending states  
- **Danger**: Errors, destructive actions
- **Info**: Informational content, tips

---

## Component Patterns

### Cards

Cards are flexible UI elements that organize content into meaningful sections and make it easier to display on different screen sizes.

#### Basic Card Structure
```html
<div class="card">
  <div class="card-body">
    <p>This is some text within a card body.</p>
  </div>
</div>
```

#### Card Variations
```html
<!-- Card with Header -->
<div class="card">
  <div class="card-header">
    <h3 class="card-title">Card Title</h3>
    <div class="card-actions">
      <a href="#" class="btn btn-primary">Action</a>
    </div>
  </div>
  <div class="card-body">
    <p class="text-secondary">Card content goes here</p>
  </div>
</div>

<!-- Card Sizing -->
<div class="card card-sm">    <!-- Small padding -->
<div class="card">           <!-- Default padding -->
<div class="card card-md">   <!-- Medium padding -->
<div class="card card-lg">   <!-- Large padding -->
```

#### Card Status Indicators
```html
<!-- Top Status -->
<div class="card">
  <div class="card-status-top bg-primary"></div>
  <div class="card-body">Content</div>
</div>

<!-- Side Status -->
<div class="card">
  <div class="card-status-start bg-green"></div>
  <div class="card-body">Content</div>
</div>
```

#### Card with Image
```html
<div class="card">
  <img class="card-img-top" src="image.jpg" alt="Card image">
  <div class="card-body">
    <h3 class="card-title">Image Card</h3>
    <p class="text-secondary">Card description</p>
  </div>
</div>
```

### Buttons

Tabler provides various button styles for different contexts, including action buttons for subtle interactions.

#### Button Hierarchy
```html
<!-- Primary Actions -->
<button class="btn btn-primary">Primary Action</button>
<button class="btn btn-secondary">Secondary</button>

<!-- Contextual Buttons -->
<button class="btn btn-success">Success</button>
<button class="btn btn-info">Info</button>  
<button class="btn btn-warning">Warning</button>
<button class="btn btn-danger">Danger</button>

<!-- Button Styles -->
<button class="btn btn-outline-primary">Outlined</button>
<button class="btn btn-ghost-primary">Ghost</button>
```

#### Button Sizes
```html
<button class="btn btn-primary btn-lg">Large</button>
<button class="btn btn-primary">Default</button>  
<button class="btn btn-primary btn-sm">Small</button>
```

#### Buttons with Icons
```html
<button class="btn btn-primary">
  <!-- Tabler Icon SVG -->
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon">
    <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2"/>
    <path d="M7 9l5 -5l5 5"/>
    <path d="M12 4l0 12"/>
  </svg>
  Upload
</button>
```

#### Action Buttons
```html
<div class="btn-actions">
  <a href="#" class="btn btn-action" aria-label="Edit">
    <svg class="icon"><!-- Edit icon --></svg>
  </a>
  <a href="#" class="btn btn-action" aria-label="Delete">  
    <svg class="icon"><!-- Delete icon --></svg>
  </a>
</div>
```

### Tables

Tables visualize data in a clear way with light padding and horizontal dividers to provide necessary information without overwhelming visuals.

#### Basic Table
```html
<div class="table-responsive">
  <table class="table table-vcenter">
    <thead>
      <tr>
        <th>Name</th>
        <th>Title</th>
        <th>Email</th>
        <th>Role</th>
        <th class="w-1"></th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>John Doe</td>
        <td class="text-secondary">Designer</td>
        <td class="text-secondary">
          <a href="#" class="text-reset">john@example.com</a>
        </td>
        <td class="text-secondary">Admin</td>
        <td>
          <a href="#">Edit</a>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

#### Table Modifiers
```html
<table class="table table-vcenter table-nowrap">  <!-- No text wrapping -->
<table class="table table-hover">                <!-- Hover effects -->
<table class="table table-striped">              <!-- Striped rows -->
```

### Forms

#### Form Groups
```html
<div class="mb-3">
  <label class="form-label">Input Label</label>
  <input type="text" class="form-control" placeholder="Enter text...">
  <small class="form-hint">This is a form hint</small>
</div>
```

#### Input States
```html
<!-- Success State -->
<input type="text" class="form-control is-valid">
<div class="valid-feedback">Looks good!</div>

<!-- Error State -->  
<input type="text" class="form-control is-invalid">
<div class="invalid-feedback">Please provide a valid input.</div>
```

### Navigation

#### Page Structure
```html
<div class="page">
  <header class="navbar navbar-expand-sm navbar-light d-print-none">
    <div class="container-xl">
      <h1 class="navbar-brand">
        <img src="logo.svg" width="110" height="32" alt="Logo">
      </h1>
      <div class="navbar-nav flex-row order-md-last">
        <!-- User menu -->
      </div>
    </div>
  </header>
  
  <div class="page-wrapper">
    <div class="page-body">
      <div class="container-xl">
        <!-- Main content -->
      </div>
    </div>
  </div>
</div>
```

---

## Layout System

### Grid Layout
```html
<!-- Card Grid -->
<div class="row row-deck row-cards">
  <div class="col-4">
    <div class="card">
      <div class="card-body">Content</div>
    </div>
  </div>
  <div class="col-4">
    <div class="card">
      <div class="card-body">Content</div>  
    </div>
  </div>
  <div class="col-4">
    <div class="card">
      <div class="card-body">Content</div>
    </div>
  </div>
</div>
```

### Spacing Utilities
```scss
// Margin classes: m-{size}
.m-0   { margin: 0; }
.m-1   { margin: 0.25rem; }
.m-2   { margin: 0.5rem; }
.m-3   { margin: 1rem; }
.m-4   { margin: 1.5rem; }
.m-5   { margin: 3rem; }

// Padding classes: p-{size}  
.p-0   { padding: 0; }
.p-1   { padding: 0.25rem; }
.p-2   { padding: 0.5rem; }
.p-3   { padding: 1rem; }
.p-4   { padding: 1.5rem; }
.p-5   { padding: 3rem; }
```

---

## Typography System

### Text Hierarchy
```html
<h1>Heading 1 (2.5rem)</h1>
<h2>Heading 2 (2rem)</h2>
<h3>Heading 3 (1.75rem)</h3>
<h4>Heading 4 (1.5rem)</h4>
<h5>Heading 5 (1.25rem)</h5>
<h6>Heading 6 (1rem)</h6>

<p>Body text (1rem)</p>
<small>Small text (0.875rem)</small>
```

### Text Utilities
```html
<!-- Color Utilities -->
<p class="text-primary">Primary text</p>
<p class="text-secondary">Secondary text</p>
<p class="text-success">Success text</p>
<p class="text-danger">Danger text</p>
<p class="text-muted">Muted text</p>

<!-- Weight Utilities -->
<p class="fw-light">Light weight</p>
<p class="fw-normal">Normal weight</p>
<p class="fw-bold">Bold weight</p>

<!-- Alignment -->
<p class="text-start">Left aligned</p>
<p class="text-center">Center aligned</p>
<p class="text-end">Right aligned</p>
```

---

## Icon System

Tabler includes over 5880 free MIT-licensed icons from the Tabler Icons set, available in SVG, PNG, and React formats.

### Icon Usage
```html
<!-- Standard Icon -->
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon">
  <path d="M12 2l-2 7h-7l5.5 4.5-2.5 7.5 6-4.5 6 4.5-2.5-7.5 5.5-4.5h-7z"/>
</svg>

<!-- Icon Sizes -->
<svg class="icon icon-sm">   <!-- Small: 16px -->  
<svg class="icon">           <!-- Default: 24px -->
<svg class="icon icon-lg">   <!-- Large: 32px -->
<svg class="icon icon-xl">   <!-- Extra large: 48px -->
```

### Icon Colors  
```html
<svg class="icon text-primary">   <!-- Primary color -->
<svg class="icon text-success">   <!-- Success color -->
<svg class="icon text-danger">    <!-- Danger color -->
<svg class="icon text-muted">     <!-- Muted color -->
```

---

## Component Generation Patterns

### 1. Component Anatomy Template
```html
<!-- Component Container -->
<div class="[component-name]">
  
  <!-- Optional Header -->
  <div class="[component-name]-header">
    <h3 class="[component-name]-title">Title</h3>
    <div class="[component-name]-actions">
      <!-- Actions -->
    </div>
  </div>
  
  <!-- Main Content -->
  <div class="[component-name]-body">
    <!-- Primary content -->
  </div>
  
  <!-- Optional Footer -->
  <div class="[component-name]-footer">
    <!-- Footer content -->
  </div>
  
</div>
```

### 2. State Modifiers Pattern
```scss
// Base component
.component {
  // Base styles
}

// Size modifiers
.component-sm { /* Small variant */ }
.component-md { /* Medium variant */ }  
.component-lg { /* Large variant */ }

// State modifiers
.component-active { /* Active state */ }
.component-disabled { /* Disabled state */ }
.component-loading { /* Loading state */ }

// Color modifiers  
.component-primary { /* Primary theme */ }
.component-secondary { /* Secondary theme */ }
.component-success { /* Success theme */ }
```

### 3. Responsive Patterns
```scss
// Mobile-first responsive design
.component {
  // Mobile styles (default)
  
  @media (min-width: 576px) {
    // Small devices and up
  }
  
  @media (min-width: 768px) {
    // Medium devices and up  
  }
  
  @media (min-width: 992px) {
    // Large devices and up
  }
  
  @media (min-width: 1200px) {
    // Extra large devices and up
  }
}
```

---

## Best Practices

### Naming Conventions
1. **BEM Methodology**: Use Block-Element-Modifier naming
   ```css
   .card {}              /* Block */
   .card__header {}      /* Element */  
   .card--large {}       /* Modifier */
   ```

2. **Semantic Class Names**: Choose descriptive, purpose-driven names
   ```css
   .user-profile {}      /* ✓ Good */  
   .blue-box {}          /* ✗ Avoid */
   ```

### Consistency Guidelines

1. **Color Usage**
   - Stick to the defined color palette
   - Use contextual colors appropriately (success, warning, danger)
   - Maintain sufficient contrast ratios for accessibility

2. **Spacing System** 
   - Use consistent spacing increments (0.25rem, 0.5rem, 1rem, etc.)
   - Apply uniform padding and margins across similar components
   - Follow the established grid system

3. **Typography**
   - Maintain clear hierarchy with heading levels  
   - Use consistent font weights and sizes
   - Ensure readable line heights and letter spacing

4. **Interactive Elements**
   - Provide clear hover and focus states
   - Use consistent button sizes within contexts
   - Include appropriate loading and disabled states

### Accessibility Standards

1. **Semantic HTML**
   ```html
   <button type="button">Button</button>  <!-- ✓ Semantic -->
   <div onclick="">Button</div>           <!-- ✗ Avoid -->
   ```

2. **ARIA Labels**
   ```html  
   <button aria-label="Close dialog">×</button>
   <input aria-describedby="help-text">
   ```

3. **Keyboard Navigation**
   - Ensure all interactive elements are focusable
   - Provide visible focus indicators
   - Support standard keyboard shortcuts

### Performance Optimization

1. **CSS Organization**
   - Group related styles together  
   - Use CSS custom properties for theming
   - Minimize specificity conflicts

2. **Asset Optimization**
   - Optimize icon SVGs for size
   - Use appropriate image formats
   - Leverage CSS-in-JS for component-specific styles

---

## Dark Mode Support

Tabler supports both dark and light modes, with dark mode reducing eye fatigue and improving focus in low-light conditions.

### Implementation Pattern
```scss
// Light mode (default)
:root {
  --color-bg: #ffffff;
  --color-text: #1e293b;
  --color-border: #e2e8f0;
}

// Dark mode
:root[data-bs-theme="dark"] {
  --color-bg: #1e293b; 
  --color-text: #f8fafc;
  --color-border: #334155;
}

// Component using CSS variables
.component {
  background-color: var(--color-bg);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}
```

---

## Customization with SCSS

### Variable Overrides
```scss
// custom-variables.scss
$primary: #your-brand-color;
$secondary: #your-secondary-color;
$border-radius: 0.5rem;
$font-family-sans-serif: 'Your Font', sans-serif;

// Import Tabler after overrides
@import 'tabler';
```

### Component Customization
```scss
// Extend existing components
.card-custom {
  @extend .card;
  
  border: 2px solid $primary;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  
  &:hover {
    transform: translateY(-2px);
    transition: transform 0.2s ease;
  }
}
```

---

## Quick Reference Checklist

**Before creating a new component:**

- [ ] Does it follow Tabler's visual hierarchy?
- [ ] Are you using colors from the established palette? 
- [ ] Does it work in both light and dark modes?
- [ ] Is the component responsive across all screen sizes?
- [ ] Are interactive elements accessible via keyboard?
- [ ] Does it follow the established naming conventions?
- [ ] Are ARIA labels included where necessary?
- [ ] Is the component properly documented?

**Component structure checklist:**

- [ ] Container with semantic class name
- [ ] Consistent spacing using Tabler utilities
- [ ] Proper heading hierarchy if applicable
- [ ] Icon integration following Tabler patterns
- [ ] State management (hover, focus, disabled, loading)
- [ ] Responsive behavior defined
- [ ] Color variants implemented
- [ ] Size variants provided where appropriate

---

This guide provides the foundation for creating consistent, beautiful components that align with Tabler's design system. Use it as a reference when building new interface elements or customizing existing ones to maintain design coherence across your application.