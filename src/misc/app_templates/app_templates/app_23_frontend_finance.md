# Goal: Generate an Intuitive React Personal Finance Dashboard

This prompt directs the generation of the frontend of a full-stack personal finance application. The output must be a complete, responsive, and user-friendly single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** specializing in FinTech and data visualization. Your focus is on creating clear, intuitive, and secure interfaces for managing financial data.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite, designed to provide users with a clear overview of their financial health.
* **Backend API Integration:** The frontend will consume all backend endpoints for transactions, budgets, goals, and reports using relative paths.
* **User Goal:** The user wants an easy way to track their spending, see if they are sticking to their budget, and monitor their progress toward savings goals.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the main dashboard layout for displaying key metrics. Plan the UI for logging a new transaction, creating a budget, and visualizing data with charts.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Financial Dashboard:** A main view displaying key financial metrics like current account balances (mocked), a summary of recent income vs. expenses, and the status of user-created budgets.
2.  **Transaction Management:** An interface for manually adding new transactions (income or expense) and a view that displays a filterable and searchable list of all past transactions.
3.  **Budget Tracking Interface:** A view where users can create budgets for different spending categories and visually track their current spending against those budget limits using progress bars.
4.  **Goal Progress View:** A dedicated view for users to set financial goals (e.g., "Save $1000 for vacation") and see their progress towards achieving them.

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
    import { Chart as ChartJS, ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement } from 'chart.js';
    import { Doughnut, Bar } from 'react-chartjs-2';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for transactions, budgets, goals, current view, etc.
      
      // 2. Lifecycle Hooks: Use useEffect for initial data fetching.
      
      // 3. Event Handlers & API Calls: Define functions for adding transactions, creating budgets, etc.

      // 4. Render Logic: Conditionally render different views (Dashboard, Transactions, Budgets).
      
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

After generating the code, perform a final internal review to ensure the budget progress bars and financial charts accurately reflect the user's transaction data. You may now begin.