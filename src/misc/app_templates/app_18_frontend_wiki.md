# Goal: Generate an Intuitive & Collaborative React Wiki SPA

This prompt directs the generation of the frontend of a full-stack wiki platform. The output must be a complete, responsive, and user-friendly single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** who specializes in building rich content editing experiences and applications for knowledge management.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite.
* **Backend API Integration:** The frontend will consume all backend endpoints for pages, revisions, and search using relative paths.
* **User Goal:** Users need to be able to easily find, read, and contribute to a shared knowledge base.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider a rich Markdown editor with live preview, a view to display the differences between two versions of a page, client-side routing, and search functionality.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Wiki Page Viewer:** A view that fetches and safely renders the HTML content of a wiki page, including a table of contents and internal wiki-links.
2.  **Markdown Editor with Live Preview:** A dedicated editing view that provides a rich text or raw markdown editor alongside a live preview of the rendered HTML.
3.  **Version History & Diff Viewer:** An interface to view the list of revisions for a page. It should allow a user to select two versions and see a visual "diff" of the changes between them.
4.  **Content Discovery:** A global search bar that allows users to find pages, and a navigation system (e.g., sidebar) for Browse pages by category.

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
    import ReactMarkdown from 'react-markdown';
    // ... other imports ...
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for pages, currentPage, revisions, currentView, etc.

      // 2. Event Handlers & API Calls: Define functions for fetching pages, saving edits, and viewing history.

      // 3. Render Logic: Conditionally render different views (PageView, EditorView, HistoryView).
      
      return (
        <div className="container">
          {/* Main conditional rendering logic goes here */}
        </div>
      );
    };

    // 4. Mounting Logic
    const container = document.getElementById('root');
    if (container) {
      const root = ReactDOM.createRoot(container);
      root.render(<App />);
    }

    export default App;
    ```
* **Libraries:** Must use `react-markdown` for rendering content and `diff` or a similar library for visualizing version changes.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, `react-markdown`, and `diff`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the diff viewer correctly highlights changes and that the markdown editor works as expected. You may now begin.