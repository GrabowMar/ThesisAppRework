# Goal: Generate a Visually Appealing & Performant React Gallery SPA

This prompt directs the generation of the frontend of a full-stack image gallery application. The output must be a complete, responsive, and aesthetically pleasing single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** who specializes in creating media-rich, high-performance web applications. You have a strong eye for design and expertise in optimizing image loading and creating fluid user interfaces.

---

### **2. Context (Additional Information)**

* **Application Architecture:** This is a React SPA built with Vite. The primary focus is on displaying a large collection of images in a beautiful and performant way.
* **Backend API Integration:** The frontend will consume the Flask gallery backend to fetch image data and display images. Image URLs will point directly to the backend's serving endpoints using relative paths.
* **User Goal:** The user wants a beautiful and fast way to browse, view, and organize their photos.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider how to create a responsive, masonry-style grid for the main gallery view. Plan the implementation of "lazy loading" for images and the user flow for a full-screen image viewer (lightbox).

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Responsive Image Gallery:** A main view that displays image thumbnails in a responsive grid layout (e.g., masonry) with lazy loading for performance. It should include basic filtering or search capabilities.
2.  **Full-Screen Image Viewer (Lightbox):** A modal overlay that appears when a thumbnail is clicked, displaying the full-resolution image with navigation controls (next/previous) and a view for image metadata.
3.  **Image Upload Interface:** A component that allows users to upload new images, preferably via a drag-and-drop zone, with real-time progress indicators.
4.  **Album Management:** UI elements for users to create new albums and to view the contents of an existing album as a distinct gallery view.

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
      // 1. State Management: Define state for images, albums, currentView, selectedImage, etc.
      
      // 2. Lifecycle Hooks: Use useEffect for initial data fetching of images and albums.
      
      // 3. Event Handlers & API Calls: Define functions to handle uploading images, creating albums, and selecting an image to view.

      // 4. Render Logic: Conditionally render different views (GalleryGrid, ImageViewer, UploadArea).
      
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
* **Lazy Loading:** Must implement image lazy loading by setting the `loading="lazy"` attribute on the `<img>` tags.
* **Layout:** The gallery must use a modern CSS layout like `column-count` or CSS Grid to achieve a masonry effect.
* **`package.json`:** Must include `react`, `react-dom`, and `axios`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the masonry layout is responsive, images are lazy-loaded, and the lightbox viewer provides a smooth navigation experience. You may now begin.