# Goal: Generate an Intuitive React Dashboard for Event Planning

This prompt directs the generation of the frontend of a full-stack event planning application. The output must be a complete, responsive, and highly organized single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** specializing in building productivity tools and project management dashboards. Your focus is on clear information hierarchy and intuitive user workflows.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite, designed as a central dashboard for planning all aspects of an event.
* **Backend API Integration:** The frontend will consume all backend endpoints for events, guests, budgets, and tasks using relative paths.
* **User Goal:** An event planner needs a single, reliable tool to manage guests, track spending, and stay on top of deadlines.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the main dashboard layout for a single event. Plan the UI for managing a guest list, a budget table, and an interactive checklist.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Event Dashboard:** A central view for a selected event that provides a summary of key information: guest RSVP count, budget status (e.g., "$500/$2000 spent"), and a list of upcoming tasks.
2.  **Guest List Management:** An interactive table or list for managing the event's guest list, including adding guests and updating their RSVP status.
3.  **Budget Tracker:** An interface to log expenses against different categories and visualize the budget, showing total spent versus total budgeted.
4.  **Interactive Checklist/Timeline:** A view that displays the event's to-do list, allowing the planner to check off completed tasks.

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
    import { Bar } from 'react-chartjs-2';
    // ... other chart.js imports
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for the event, guests, budget items, tasks, etc.

      // 2. Lifecycle Hooks: Use useEffect for initial data fetching for a selected event.

      // 3. Event Handlers & API Calls: Define functions for adding guests, logging expenses, and completing tasks.

      // 4. Render Logic: Render the main dashboard, which contains components for displaying the guest list, budget, and checklist.
      
      return (
        <div className="container">
          {/* Main JSX for the event planning dashboard goes here */}
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
* **Libraries:** Must use `axios` for API calls and `react-chartjs-2` for budget visualization.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, `chart.js`, and `react-chartjs-2`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the budget visualization accurately reflects the expense data and that RSVP counts are tallied correctly. You may now begin.