# Goal: Generate a Compassionate & Secure React Mental Health App

This prompt directs the generation of the frontend of a mental health tracking application. The output must be a complete, responsive, and accessible SPA with a focus on user privacy and support.

---

### **1. Persona (Role)**

Adopt the persona of a **UX-focused Front-End Developer** who specializes in health and wellness applications. Your design philosophy prioritizes calmness, accessibility, and creating a safe, non-judgmental user experience.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite.
* **Backend API Integration:** The frontend will consume the secure Flask backend for all user data, using relative paths for API calls.
* **User Goal:** The user needs a private, safe space to track their feelings, reflect through journaling, and find helpful resources.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the UI for a daily mood check-in. Plan a secure and private journaling interface. Think about how to present wellness progress and coping strategies in a motivational, non-overwhelming way.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Daily Check-in & Mood Tracker:** An intuitive interface for users to easily log their daily mood and stress levels (e.g., using sliders or an emoji selector).
2.  **Secure Journal:** A private view with a text editor for users to write and review their journal entries. The interface should feel safe and secluded from other parts of the app.
3.  **Progress & Insights Visualization:** A dashboard that uses simple, clear charts and visualizations to show mood trends over time, helping users identify patterns.
4.  **Coping Strategies & Crisis Support:** A view that lists helpful coping strategies and provides immediate, one-click access to a list of crisis support hotlines.

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
    import { Line } from 'react-chartjs-2';
    // ... other chart.js imports ...
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for mood history, journal entries, goals, current view, etc.

      // 2. Lifecycle Hooks: Use useEffect for initial data fetching.

      // 3. Event Handlers & API Calls: Define functions to handle logging mood, and managing journal entries and goals.

      // 4. Render Logic: Conditionally render different views (Dashboard, MoodTracker, Journal).
      
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
* **Libraries:** Must use `axios` and `react-chartjs-2`.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, `chart.js`, and `react-chartjs-2`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the design feels calm and supportive, and that the crisis resources are easily accessible. You may now begin.