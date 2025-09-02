# Goal: Generate a Full-Featured & Modern React Blog Platform SPA

This prompt directs the generation of the frontend of a full-stack blog platform.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** who excels at building dynamic, content-driven applications with React.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite.
* **Backend API Integration:** The frontend must consume all backend endpoints using relative paths.
* **Content Focus:** The core is displaying and creating rich, Markdown-formatted content.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider integrating a Markdown editor, managing state for nested comments, client-side routing, and fetching paginated posts.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Content Browse & Discovery:** A home page that displays a paginated list of all blog posts, with UI controls for filtering by category.
2.  **Post Viewing with Nested Comments:** A detailed post view that safely renders the post's HTML content and displays its comment section as a threaded/nested structure.
3.  **Rich Text Markdown Editor:** A dedicated view for creating and editing posts that features a rich text editor for writing in Markdown and a live preview pane.
4.  **User Authentication & Interaction:** Provide forms for registration and login. Authenticated users must be able to create posts and comments.

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
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for the current view, posts, current post, user, etc.
      
      // 2. Event Handlers: Define functions to handle login, post creation, commenting, etc.
      
      // 3. Render Logic: Use conditional rendering to switch between different views (HomePage, PostView, EditorView, AuthView).
      //    A recursive component should be used to render nested comments.
      
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
* **`package.json`:** Must include `react`, `react-dom`, `axios`, and `react-markdown`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure Markdown is rendered safely and the nested comment logic is flawless. You may now begin.