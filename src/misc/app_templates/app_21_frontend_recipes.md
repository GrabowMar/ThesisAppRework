# Goal: Generate an Intuitive React Recipe & Meal Planning SPA

This prompt directs the generation of the frontend of a full-stack recipe management application. The output must be a complete, responsive, and user-friendly single-page application.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** who excels at building consumer-facing applications with a focus on great user experience, especially for lifestyle and planning tools.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite, designed to be a kitchen-friendly tool for finding, creating, and planning meals.
* **Backend API Integration:** The frontend will consume all backend endpoints for recipes, meal plans, and shopping lists using relative paths.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the UI for a recipe card, a detailed recipe view, a calendar for meal planning, and an interactive shopping list. Plan the state management for these interconnected features.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Recipe Discovery & Viewing:** A main view to browse and search for recipes, and a detailed view to display a single recipe's ingredients, step-by-step instructions, and nutritional information.
2.  **Recipe Creation & Editing:** A form-based interface for users to create their own new recipes, including adding ingredients with quantities and writing out the cooking instructions.
3.  **Visual Meal Planner:** An interactive calendar view where users can drag and drop recipes onto specific dates to create a weekly or monthly meal plan.
4.  **Shopping List Generator:** A view that automatically generates a consolidated shopping list from a selected meal plan, with checkboxes for users to mark off items as they shop.

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
      // 1. State Management: Define state for recipes, meal plan, shopping list, current view, etc.
      
      // 2. Lifecycle Hooks: Use useEffect for initial data fetching (e.g., all recipes).
      
      // 3. Event Handlers & API Calls: Define functions for creating recipes, adding to the meal plan, and generating the shopping list.

      // 4. Render Logic: Conditionally render different views (RecipeList, RecipeView, MealPlanner, ShoppingList).
      
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
* **`package.json`:** Must include `react`, `react-dom`, and `axios`. A calendar library like `react-calendar` is recommended for the meal planner.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the meal planner correctly populates the shopping list and that recipe data is displayed clearly. You may now begin.