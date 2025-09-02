# Goal: Generate a Robust & User-Friendly React File Upload SPA

This prompt directs the generation of the frontend of a full-stack file management application. The output must be a complete, responsive SPA with a focus on a seamless and informative upload experience.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** who has deep experience with advanced browser APIs, specifically the File API, and building complex user interfaces for managing asynchronous operations.

---

### **2. Context (Additional Information)**

* **Application Architecture:** This is a React SPA built with Vite. The most critical user interaction is the file upload process, which must be reliable, even for large files.
* **Backend API Integration:** The frontend will communicate with the Flask file-handling backend, primarily using the `/api/upload` endpoint with relative paths.
* **User Experience:** The user must have clear, real-time feedback on the status of their uploads at all times.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider how to handle file selection via both click and drag-and-drop. Plan the state management for tracking multiple simultaneous uploads and the use of `axios` with an `onUploadProgress` handler.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Advanced Upload Interface:** A component featuring a drag-and-drop zone and a traditional file input button that allows for selecting multiple files.
2.  **Real-Time Upload Progress:** A UI that displays a queue of selected files, with individual, real-time progress bars and status indicators for each file during the upload process.
3.  **File Browser & Listing:** A main view that displays a grid or list of already uploaded files, with buttons to download or delete each file.
4.  **Image Preview Modal:** A lightbox or modal component that appears when an image thumbnail is clicked, displaying a larger version of the image.

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
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for file lists (to upload, uploaded), upload progress, etc.
      
      // 2. Event Handlers & API Calls: Define functions to handle file selection (drag-drop and click), and to initiate the upload process using axios with an onUploadProgress callback.

      // 3. Render Logic: Render the main components: the dropzone/upload area, the progress list, and the gallery of uploaded files.
      
      return (
        <div className="container">
          {/* Main JSX structure goes here */}
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
* **Libraries:** Must use `axios` for file uploads to easily track progress.
* **Drag and Drop:** Must correctly implement `onDragOver`, `onDragLeave`, and `onDrop` event handlers.
* **`package.json`:** Must include `react`, `react-dom`, and `axios`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the drag-and-drop functionality is smooth and the progress bars are accurate. You may now begin.