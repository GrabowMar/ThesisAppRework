# Goal: Generate an Interactive React Dashboard for Sports Team Management

This prompt directs the generation of the frontend of a full-stack sports team management application. The output must be a complete, responsive, and highly functional single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Lead Front-End Engineer** who builds data-rich dashboards for sports analytics and team management. You focus on clear data visualization and intuitive interfaces for coaches and players.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite, designed for coaches to manage their team on desktop or tablet.
* **Backend API Integration:** The frontend will consume all backend endpoints for the roster, schedule, and performance data using relative paths.
* **User Goal:** A coach needs a single place to manage their player roster, schedule practices and games, and track player stats and health.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider a dashboard overview, a detailed roster view, a calendar for scheduling, and a player profile page that visualizes performance data with charts.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Team Roster & Profiles:** A view to display the full team roster. Clicking a player should navigate to a detailed profile page showing their information, stats, and injury history.
2.  **Event Calendar & Scheduling:** An interactive calendar that displays all upcoming training sessions and matches. Provide an interface for coaches to schedule new events.
3.  **Performance Dashboard:** A view that uses charts and graphs to visualize key team and individual player statistics over time, such as goals per game or training attendance rates.
4.  **Health & Injury Status Board:** A simple view that lists all players' current health status, highlighting any ongoing injuries and their expected recovery timelines.

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
    import { Bar, Line } from 'react-chartjs-2';
    // ... other chart.js imports
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for roster, schedule, performance data, current view, etc.
      
      // 2. Lifecycle Hooks: Use useEffect for initial data fetching.

      // 3. Event Handlers & API Calls: Define functions to handle adding players, scheduling events, etc.

      // 4. Render Logic: Conditionally render different views (Dashboard, Roster, Calendar, etc.).
      
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
* **Libraries:** Must use `axios` for API calls and `react-chartjs-2` for data visualization. A calendar library like `react-calendar` is recommended.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, `chart.js`, `react-chartjs-2`, and `react-calendar`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the roster and schedule are displayed clearly and that the performance charts accurately reflect player data. You may now begin.