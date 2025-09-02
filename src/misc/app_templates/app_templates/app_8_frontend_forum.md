# Goal: Generate an Engaging & Interactive React Forum SPA

This prompt directs the generation of the frontend of a full-stack online forum.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** specializing in building rich, community-driven applications. Your expertise is in managing and displaying complex, nested data structures.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite.
* **Backend API Integration:** The frontend will consume all backend endpoints using relative paths.
* **User Goal:** Users want to easily read discussions, follow threads, reply to comments, and have their interactions reflected instantly.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider a recursive React component for nested comments, state management for optimistic UI updates on votes, and the UI flow for replying to a specific comment.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Forum Browsing & Discovery:** A main view displaying a list of all threads, with functionality to filter by category and sort by criteria like recent activity or vote score.
2.  **Thread Viewing with Nested Comments:** A detailed view for a single thread that recursively renders the entire comment tree, showing replies indented under their parents.
3.  **User Interaction & Engagement:** Provide UI elements for creating new threads, posting comments/replies, and upvoting/downvoting both threads and comments with optimistic UI updates.
4.  **User Authentication:** Simple forms for user registration and login to enable participation in the forum.

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
      // 1. State Management: Define state for threads, currentThread, comments, user, etc.

      // 2. Event Handlers: Define functions for creating threads, posting comments, and voting.

      // 3. Render Logic: Conditionally render views. Implement a recursive 'Comment' component to display the nested comment thread.
      
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
* **Optimistic UI:** Voting actions must update the local state immediately, then revert on API error.
* **`package.json`:** Must include `react`, `react-dom`, and `axios`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the recursive comment rendering is working flawlessly and voting provides instant optimistic feedback. You may now begin.