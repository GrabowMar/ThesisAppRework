# Goal: Generate a Professional & Interactive React Networking SPA

This prompt directs the generation of the frontend of a career networking application. The output must be a complete, responsive, and professional single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** specializing in building social networking platforms. You focus on creating intuitive interfaces for profile management, networking, and job searching.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite.
* **Backend API Integration:** The frontend will consume all backend endpoints for profiles, connections, jobs, and messaging using relative paths.
* **User Goal:** Users want to build their professional network, showcase their experience, and find career opportunities.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the UI for displaying a professional profile, managing connection requests, searching for jobs, and a basic chat interface for messaging.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Professional Profile View:** A view to display a user's professional profile, including their work experience and education. The view should also contain a form to allow the owner to edit their own profile.
2.  **Network Management:** An interface to view a user's current connections, manage pending connection requests (accept/decline), and search for other professionals on the platform to connect with.
3.  **Job Board & Search:** A view for searching and filtering available job postings, with an interface to view the details of a specific job.
4.  **Private Messaging Interface:** A simple real-time chat interface for users to communicate with their established connections, using Socket.IO.

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
    import io from 'socket.io-client';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for user profile, connections, jobs, messages, current view, etc.
      
      // 2. Lifecycle Hooks: Use useEffect for initial data fetching and for managing the WebSocket connection.

      // 3. Event Handlers & API Calls: Define functions to handle profile updates, connection requests, job searches, and sending messages.

      // 4. Render Logic: Conditionally render different views (Profile, Network, Jobs, Messaging).
      
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
* **Libraries:** Must use `axios` for HTTP requests and `socket.io-client` for real-time messaging.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, and `socket.io-client`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the profile editing and connection management flows are intuitive and functional. You may now begin.