# Goal: Generate an Advanced & Intuitive React Notes Application SPA

This prompt directs the generation of the frontend of a full-stack note-taking application. The output must be a complete, responsive SPA that feels like a native desktop application.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** with extensive experience in building sophisticated single-page applications, particularly those involving rich text editing and complex state management for a seamless user experience.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite. The user experience should prioritize a distraction-free writing environment and ensure no work is ever lost.
* **Backend API Integration:** The frontend will consume all backend endpoints for notes, categories, tags, and search. A key feature is the frequent use of the `auto-save` endpoint.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the integration of a rich text editor, the implementation of a "debounced" auto-save mechanism, state management for the note list and editor, and the UI for displaying search results.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Note Browsing & Organization:** An interface with a sidebar for categories and a main pane listing note previews. The view must include a search bar to filter notes.
2.  **Rich Text Note Editor:** A dedicated view for creating and editing notes using a rich text editor component (e.g., `react-quill`). The editor must feature a debounced auto-save mechanism that saves changes a few seconds after the user stops typing.
3.  **Note Lifecycle Actions:** Provide UI controls to create new notes, archive existing notes (moving them from the main list), and view/restore them from a dedicated "Archived" view.
4.  **Client-Side View Management:** Use conditional rendering to seamlessly switch between the main notes list, the note editor, and the archived notes view based on the user's actions.

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
    import React, { useState, useEffect, useCallback } from 'react';
    import ReactDOM from 'react-dom/client';
    import axios from 'axios';
    import ReactQuill from 'react-quill';
    import 'react-quill/dist/quill.snow.css';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for notes, categories, currentNote, currentView, etc.
      
      // 2. Lifecycle Hooks: Use useEffect for initial data fetching.
      
      // 3. Event Handlers & API Calls: Define functions to handle creating, selecting, editing, archiving, and auto-saving notes. Implement debouncing for the auto-save handler.
      
      // 4. Render Logic: Conditionally render different views (NotesList, NoteEditor, ArchivedList) based on the application's state.

      return (
        <div className="notes-app-container">
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
* **Libraries:** Must use `react-quill` for the rich text editor and `axios` for API calls.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, and `react-quill`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the debounced auto-save is working correctly, the layout is responsive, and the rich text editor is fully integrated. You may now begin.