# Goal: Generate an Intuitive & Responsive React Authentication UI

This prompt directs the generation of the frontend for a complete user authentication system.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** who specializes in creating clean, intuitive, and secure user authentication interfaces.

---

### **2. Context (Additional Information)**

* **Application Architecture:** This is a React SPA built with Vite.
* **Backend API Integration:** The frontend will consume the `/api/register`, `/api/login`, `/api/logout`, and `/api/dashboard` endpoints using relative paths to leverage the Vite proxy.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the state needed for the current view, form inputs, and validation. Plan the logic for checking auth status on initial load.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **User Registration Form:** A view with a form for username, email, and password. Implement real-time client-side validation.
2.  **User Login Form:** A view with a form to accept a user's email and password.
3.  **Protected Dashboard View:** A view accessible only after login. It should display a welcome message and a logout button. Unauthenticated users should be redirected.
4.  **Client-Side View Routing:** Manage the display of the three views (Login, Register, Dashboard) within the single `App` component using conditional rendering based on application state.

---

### **5. Output Specification (Answer Engineering)**

#### **Deliverables**

Generate the following four files. Do **not** generate a `Dockerfile` or `vite.config.js`.

1.  `package.json`
2.  `index.html`
3.  `src/App.jsx`: A completed version of the skeleton provided below.
4.  `src/App.css`

#### **Code Quality & UX Mandates**

* **`App.jsx` Skeleton:**
    ```javascript
    // 1. Imports
    import React, { useState, useEffect } from 'react';
    import ReactDOM from 'react-dom/client';
    import axios from 'axios';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for the current user, the current view, loading status, and errors.
      
      // 2. Lifecycle Hooks: Use useEffect to check for an active session on initial application load.
      
      // 3. Event Handlers & API Calls: Define functions to handle form submissions (login, register) and user actions (logout).
      
      // 4. Render Logic: Conditionally render different components/views based on the application's state (e.g., show login form, register form, or dashboard).

      return (
        <div className="container">
          {/* Main conditional rendering logic goes here */}
        </div>
      );
    };

    // 5. Mounting Logic
    const container = document.getElementById('root');
    if (container) {
      const root = ReactDOM.createRoot(container);
      root.render(<App />);
    }

    export default App;
    ```

* **`package.json`:**
    * Must include `react`, `react-dom`, and `axios`.
* **Configuration:** The app must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure form validation is working, the dashboard is correctly protected, and state is managed correctly across login and logout actions. You may now begin.