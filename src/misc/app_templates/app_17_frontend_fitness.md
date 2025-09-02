# Goal: Generate a Motivational & Data-Rich React Fitness Logger SPA

This prompt directs the generation of the frontend of a full-stack fitness tracking application. The output must be a complete, responsive, and user-friendly single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** who excels at building data visualization dashboards and intuitive logging interfaces for fitness and health applications.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite. The UX should be motivational and make data logging as simple as possible.
* **Backend API Integration:** The frontend will consume all backend endpoints for workouts, exercises, progress, and goals using relative paths.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the UI for logging an active workout, how to use charts to visualize progress, an interface for setting goals, and a central dashboard to tie everything together.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Workout Logging Interface:** An interactive view to log a new workout session, allowing users to search and add exercises from a library, and input sets, reps, and weight for each.
2.  **Progress Tracking & Visualization:** A dashboard or dedicated view that uses charts to visualize the user's progress over time (e.g., a line chart for weight, a bar chart for strength gains).
3.  **Exercise Library:** A searchable and filterable view that displays a library of available exercises, including instructions and muscle groups targeted.
4.  **Goal Management:** A UI for users to set new fitness goals (e.g., "Run 5k in under 25 minutes") and view their progress towards active goals.

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
    import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
    import { Line } from 'react-chartjs-2';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for workouts, exercises, progress data, goals, current view, etc.

      // 2. Lifecycle Hooks: Use useEffect for initial data fetching.

      // 3. Event Handlers & API Calls: Define functions to handle logging workouts, progress, and goals.

      // 4. Render Logic: Conditionally render different views (Dashboard, WorkoutLogger, ProgressView, etc.).
      
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
* **Libraries:** Must use `axios` for API calls and `react-chartjs-2` for data visualization.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, `chart.js`, and `react-chartjs-2`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the workout logging flow is intuitive and that progress charts render correctly with fetched data. You may now begin.