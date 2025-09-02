# Goal: Generate a Collaborative React SPA for Research Management

This prompt directs the generation of the frontend of a full-stack research collaboration platform. The output must be a complete, responsive, and intuitive single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** who builds productivity and collaboration tools for professional and academic users. Your focus is on clear information architecture and creating an efficient workspace.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite, designed as a central hub for research teams to manage their projects.
* **Backend API Integration:** The frontend will consume all backend endpoints for projects, documents, tasks, and collaborators using relative paths.
* **User Goal:** Researchers need a single place to organize their project files, track tasks, and communicate with their team.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the main dashboard for listing a user's projects. Plan the layout for a project-specific view, which would include a file browser, a task list, and a list of collaborators.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Project Dashboard & File Explorer:** A main view that lists all research projects a user is a member of. Clicking on a project should navigate to a file explorer view that lists all documents and folders within that project.
2.  **Collaborative Document Viewer:** An interface to view a selected document (e.g., a PDF placeholder or rendered text). This view must include a sidebar or section to display and add comments, facilitating discussion around the document.
3.  **Project Task Board:** A simple task management interface within each project view, displaying tasks as a list or on a simple Kanban-like board (To Do, In Progress, Done). Users should be able to create new tasks and update their status.
4.  **Collaboration Management:** UI elements within each project for the project owner to invite new members by email and to manage the roles (e.g., 'editor', 'viewer') of existing members.

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
      // 1. State Management: Define state for projects, currentProject, documents, tasks, user, etc.
      
      // 2. Lifecycle Hooks: Use useEffect for initial data fetching (e.g., the user's project list).
      
      // 3. Event Handlers & API Calls: Define functions to handle project selection, document uploads, task updates, and inviting collaborators.

      // 4. Render Logic: Use conditional rendering to switch between the main ProjectDashboard and the detailed ProjectView.
      
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
* **Libraries:** Must use `axios` for API communication.
* **`package.json`:** Must include `react`, `react-dom`, and `axios`. A drag-and-drop library like `react-beautiful-dnd` is recommended for the task board.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the project view correctly displays its associated documents and tasks, and that the collaboration features are intuitive. You may now begin.