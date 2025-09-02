# Goal: Generate a Motivational React Environmental Impact Dashboard

This prompt directs the generation of the frontend of a full-stack environmental tracking application. The output must be a complete, responsive, and inspiring single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **UX-Focused Front-End Developer** specializing in building engaging, data-driven applications that motivate user action and behavioral change.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite, designed to make tracking one's environmental impact easy and rewarding.
* **Backend API Integration:** The frontend will consume all backend endpoints for logging activities, tracking challenges, and viewing progress, using relative paths.
* **User Goal:** Users want a simple way to understand their environmental impact and discover actionable steps to live more sustainably.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the UI for a central dashboard, simple forms for logging daily activities, and how to use charts and progress bars to visualize impact and challenge progress effectively.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Environmental Dashboard:** A main view that displays the user's overall carbon footprint score, progress in current sustainability challenges, and personalized eco-tips.
2.  **Activity Logging Interface:** Simple forms for users to log their daily activities related to transport, energy use, and waste, providing instant feedback on the calculated carbon impact.
3.  **Sustainability Challenges View:** An interface to browse available environmental challenges (e.g., "Meatless Mondays"), join them, and track progress towards completion.
4.  **Progress Visualization:** A dedicated view that uses charts to show the user's carbon footprint trend over time, broken down by category (transport, energy, etc.), to help them identify areas for improvement.

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
    import { Bar, Doughnut } from 'react-chartjs-2';
    // ... other chart.js imports
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for carbon data, challenges, tips, current view, etc.
      
      // 2. Lifecycle Hooks: Use useEffect for initial data fetching.
      
      // 3. Event Handlers & API Calls: Define functions to handle logging activities and joining challenges.

      // 4. Render Logic: Conditionally render different views (Dashboard, LogActivity, Challenges).
      
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

After generating the code, perform a final internal review to ensure the activity logging flow is intuitive and that the dashboard charts accurately reflect the user's data. You may now begin.