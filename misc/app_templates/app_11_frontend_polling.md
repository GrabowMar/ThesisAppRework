# Goal: Generate an Engaging & Real-Time React Polling SPA

This prompt directs the generation of the frontend of a full-stack polling application. The output must be a complete, responsive, and highly engaging single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **UX-focused Front-End Developer** who specializes in creating interactive and data-driven applications. Your goal is to make the process of voting engaging and the display of results clear and immediate.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite.
* **Backend API Integration:** The frontend will consume the Flask polling backend, frequently calling endpoints for poll lists, voting, and real-time results using relative paths.
* **User Goal:** Users want to easily participate in polls and see the results update as new votes come in.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider how to visually represent poll results with charts, how to manage the state of the voting process, the logic for a periodically updating results view, and a countdown timer.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Poll Discovery & Creation:** A main view to browse existing polls and a dedicated form/view to create new polls with custom options and settings.
2.  **Interactive Voting Interface:** A view that presents a poll's options to the user, allows them to cast their vote, and provides immediate feedback upon submission.
3.  **Live Results Visualization:** A results view that displays vote counts and percentages for each option using a visual bar chart. The results should auto-update periodically.
4.  **Time-Aware Display:** The UI must display the status of polls (active/closed) and show a live countdown timer for polls with a specific end date.

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
    // ... other imports from chart.js ...
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for polls, currentPoll, results, currentView, timers, etc.

      // 2. Lifecycle Hooks: Use useEffect for initial data fetching and for setting up intervals for live results/timers. Remember to clean up intervals.

      // 3. Event Handlers & API Calls: Define functions to handle creating polls, submitting votes, and fetching data.

      // 4. Render Logic: Conditionally render different views (PollsList, VotingView, ResultsView).
      
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
* **Libraries:** Must use `axios` and `react-chartjs-2`.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, `chart.js`, and `react-chartjs-2`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure that the live results polling is working correctly and the charts render accurately. You may now begin.