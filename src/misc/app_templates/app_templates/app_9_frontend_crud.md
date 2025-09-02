# Goal: Generate a Data-Intensive React Inventory Management Dashboard

This prompt directs the generation of the frontend of a full-stack inventory management application.

---

### **1. Persona (Role)**

Adopt the persona of a **Lead Front-End Engineer** who specializes in building complex, data-intensive dashboard applications for business users.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite, designed as a data-rich dashboard for managing a large inventory. Speed and accuracy are key.
* **Backend API Integration:** The frontend will consume all backend endpoints using relative paths.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider efficient rendering of large data tables, complex filtering state, a robust form component for adding/editing items, and data visualization for reports.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Inventory Dashboard & Analytics:** A main dashboard view that displays key metrics (total value, low stock count) and visualizes data, such as items per category, using charts.
2.  **Data Table for Item Management:** A comprehensive table view for listing all inventory items, with robust client-side controls for searching, sorting, and filtering.
3.  **Item Creation & Editing Form:** A single, reusable form, likely presented in a modal, for creating new items and editing existing ones, complete with real-time validation.
4.  **Stock Level Alerts & Adjustments:** A dedicated view or dashboard section to display low-stock alerts and provide a simple interface to trigger stock adjustments.

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
    import { Bar, Pie } from 'react-chartjs-2';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for items, categories, dashboard metrics, current view, etc.
      
      // 2. Lifecycle Hooks: Use useEffect for initial data fetching for the dashboard and items list.

      // 3. Event Handlers & API Calls: Define functions to handle CRUD operations and stock adjustments.

      // 4. Render Logic: Conditionally render different views (Dashboard, ItemsList, ItemForm).
      
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

After generating the code, perform a final internal review to ensure that data is displayed clearly in tables and charts, and that forms are properly validated. You may now begin.