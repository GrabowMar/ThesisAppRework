# Goal: Generate a Fluid & Highly Interactive React Microblog SPA

This prompt directs the generation of the frontend of a full-stack microblogging platform. The output must be a complete, responsive, and engaging single-page application (SPA) that feels like a modern social media app.

---

### **1. Persona (Role)**

Adopt the persona of a **Lead Front-End Engineer** at a major social media company. Your core competency is building incredibly fast, fluid, and scalable user interfaces that handle real-time data and infinite content streams.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite. The central feature is the "infinite scroll" timeline feed.
* **Backend API Integration:** The frontend must heavily utilize the Flask microblog backend, especially the `/api/feed` endpoint. All API calls must use relative paths.
* **User Experience:** The experience must be seamless. Loading should be masked by techniques like infinite scroll, and interactions should feel instantaneous through optimistic updates.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider using the Intersection Observer API for infinite scroll, optimistic UI updates for likes and follows, and a reusable `Post` component.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Infinite Scroll Timeline Feed:** A main view displaying a personalized feed of posts that automatically loads more content as the user scrolls down, using the Intersection Observer API.
2.  **Post Creation & Interaction:** A component to compose and submit new posts, and interactive buttons on each post for liking and commenting with optimistic UI updates.
3.  **User Profile & Following:** A profile view displaying a user's information and their posts, with a button to follow or unfollow them that provides immediate visual feedback.
4.  **Dynamic Content Rendering:** Logic within the post component to parse post content and render `@mentions` and `#hashtags` as clickable links.

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
    import React, { useState, useEffect, useRef, useCallback } from 'react';
    import ReactDOM from 'react-dom/client';
    import axios from 'axios';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for the feed posts, current user, current view, etc.
      
      // 2. Refs: Define a ref for the Intersection Observer to attach to a sentinel element.
      
      // 3. Lifecycle Hooks: Use useEffect to fetch the initial feed and set up the Intersection Observer.

      // 4. Event Handlers & API Calls: Define functions for posting, liking, following, and fetching more data for the feed.

      // 5. Render Logic: Conditionally render different views. The main feed should map over the posts state and include the sentinel element at the end for the observer.
      
      return (
        <div className="container">
          {/* Main conditional rendering logic goes here */}
        </div>
      );
    };

    // 6. Mounting Logic
    const container = document.getElementById('root');
    if (container) {
      const root = ReactDOM.createRoot(container);
      root.render(<App />);
    }

    export default App;
    ```
* **Infinite Scroll:** Must use the `Intersection Observer API` to trigger loading more posts.
* **`package.json`:** Must include `react`, `react-dom`, and `axios`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the infinite scroll is smooth, optimistic updates are correctly implemented, and hashtags/mentions are rendered as active links. You may now begin.