# Goal: Generate a Fluid & Collaborative React Kanban Board SPA

This prompt directs the generation of the frontend of a full-stack Kanban board application.

---

### **1. Persona (Role)**

Adopt the persona of a **Lead Front-End Engineer** specializing in building complex, interactive UIs with features like drag-and-drop. You excel at managing complex application state and creating fluid, real-time collaborative experiences.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite. The core of the application is the interactive Kanban board.
* **Backend API Integration:** The frontend will consume the Flask Kanban backend. The most important interaction is updating the backend after a drag-and-drop action is completed.
* **User Experience:** The drag-and-drop experience must be smooth, intuitive, and provide immediate visual feedback through optimistic updates.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider using a dedicated library for drag-and-drop. Plan the state management for the board and the logic for optimistic updates when a drag operation completes.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Interactive Kanban Board View:** The main UI that renders columns and tasks, and implements drag-and-drop functionality for moving tasks between and within columns using a library like `react-beautiful-dnd`.
2.  **Task Creation & Details Modal:** A modal interface for creating new tasks and for viewing/editing the detailed information of an existing task when a task card is clicked.
3.  **Optimistic UI for Drag-and-Drop:** When a user drops a task in a new position, the UI must update **instantly** to show the change. After the UI updates, an API call must be sent to the backend to persist the new state.
4.  **Filtering & Search:** Provide simple client-side controls to filter the displayed tasks on the board by a text-based search query.

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
    import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
    import axios from 'axios';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for the board data (columns, tasks, columnOrder).
      
      // 2. Lifecycle Hooks: Use useEffect to fetch the initial board data.
      
      // 3. Event Handlers & API Calls: Define a handler for onDragEnd from react-beautiful-dnd. This function will handle the optimistic UI update and the subsequent API call.

      // 4. Render Logic: Render the board using DragDropContext, Droppable for columns, and Draggable for tasks.
      
      return (
        <div className="container">
          {/* Main JSX for the Kanban board goes here */}
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
* **Libraries:** Must use `react-beautiful-dnd` for drag-and-drop functionality and `axios` for API calls.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, and `react-beautiful-dnd`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the drag-and-drop is smooth and triggers the correct optimistic updates and API calls. You may now begin.