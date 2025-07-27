# Goal: Generate an Intuitive & Validated React Feedback Form SPA

This prompt directs the generation of the frontend of a full-stack feedback collection application.

---

### **1. Persona (Role)**

Adopt the persona of a **UX-Focused Front-End Developer**. You excel at creating forms that are easy to use, provide clear feedback, and encourage completion.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite, focused on a single feedback form.
* **Backend API Integration:** The frontend will communicate with the Flask backend to submit form data and fetch categories. All API calls must use relative paths.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider real-time validation feedback, state management for form data and submission status, and the user flow after a successful submission.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Dynamic Feedback Form:** Create a multi-field form for feedback submission. The "Category" field must be a dropdown dynamically populated with data fetched from the `GET /api/categories` endpoint.
2.  **Real-Time Client-Side Validation:** As a user interacts with a form field, validate the input in real-time. Display clear, specific error messages next to any invalid fields.
3.  **Submission Handling & State:** Manage the submission process. When the user clicks "Submit," disable the form, show a loading state, and make the API call to `POST /api/feedback`.
4.  **Submission Confirmation View:** Upon a successful API response, use conditional rendering to show a "Success" view that displays a confirmation message to the user.

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
      // 1. State Management: Define state for form data, categories, validation errors, and submission status.
      
      // 2. Lifecycle Hooks: Use useEffect to fetch categories when the component mounts.

      // 3. Event Handlers: Define functions to handle form input changes and the form submission process.

      // 4. Render Logic: Use conditional rendering to show either the feedback form or the success message.
      
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

* **`package.json`:** Must include `react`, `react-dom`, and `axios`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure that form validation is comprehensive and the application state is managed correctly. You may now begin.