# Goal: Generate an Intuitive & Interactive React Reservation SPA

This prompt directs the generation of the frontend of a full-stack reservation system. The output must be a complete, responsive, and user-friendly single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **UX-focused Front-End Developer** specializing in building intuitive booking interfaces. Your goal is to create a frictionless user journey from selecting a date to completing a reservation.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite. The core of the user experience is an interactive calendar and time slot selector.
* **Backend API Integration:** The frontend will consume the Flask reservation backend using relative paths.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the user flow (select date -> see times -> select time -> confirm), the state management for this multi-step process, and the use of a calendar library.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Interactive Booking Calendar:** An interface featuring an interactive calendar where users can select a date to check for availability.
2.  **Time Slot Selection:** A UI that displays available time slots for a selected date (fetched from the API) and allows the user to select their desired time. Unavailable slots should be visually disabled.
3.  **Multi-Step Booking Form:** A guided workflow that takes the user from their selected time slot to entering their details and confirming the reservation.
4.  **Reservation Management View:** A dedicated view for authenticated users to see a list of their upcoming and past reservations, with options to cancel them.

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
    import Calendar from 'react-calendar';
    import 'react-calendar/dist/Calendar.css';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for selected date, available slots, current view, user reservations, etc.

      // 2. Event Handlers & API Calls: Define functions to handle date selection, time slot selection, and booking form submission.

      // 3. Render Logic: Conditionally render views for the calendar, time slot selection, booking form, and user's reservation list.
      
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
* **Libraries:** Must use `react-calendar` for the date picker and `axios` for API calls.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, and `react-calendar`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the calendar and time slot selection flow is logical and smooth. You may now begin.