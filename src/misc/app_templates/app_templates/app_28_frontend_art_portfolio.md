# Goal: Generate an Elegant & Performant React Art Portfolio SPA

This prompt directs the generation of the frontend of a full-stack art portfolio application. The output must be a complete, responsive, and aesthetically pleasing single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** who specializes in creating media-rich, high-performance web applications. You have a strong eye for design and expertise in optimizing image loading and creating fluid user interfaces.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite. The primary focus is on displaying a large collection of images in a beautiful and performant way.
* **Backend API Integration:** The frontend will consume the Flask gallery backend to fetch image data and display images using relative paths.
* **User Goal:** An artist needs a beautiful and fast way to showcase their work to potential clients and fans.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider how to create a responsive, masonry-style grid for the main gallery view, the implementation of "lazy loading" for images, and the user flow for a full-screen image viewer (lightbox).

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Responsive Artwork Gallery:** A main view that displays artwork thumbnails in a responsive grid layout (e.g., masonry) with lazy loading to ensure fast initial page load.
2.  **Full-Screen Artwork Viewer (Lightbox):** A modal overlay that appears when a thumbnail is clicked, displaying the full-resolution artwork with navigation controls (next/previous) and a panel for the artwork's title and description.
3.  **Artwork Upload & Management:** An interface for the authenticated artist to upload new artwork images and edit their metadata (title, description, gallery assignment).
4.  **Gallery Curation:** UI elements for the artist to create new galleries (e.g., "Oil Paintings 2024") and to view the contents of an existing gallery as a filtered collection.

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
      // 1. State Management: Define state for artworks, galleries, current view, selected artwork, etc.
      
      // 2. Lifecycle Hooks: Use useEffect for initial data fetching.
      
      // 3. Event Handlers & API Calls: Define functions for uploading, editing, and viewing artworks and galleries.

      // 4. Render Logic: Conditionally render different views (GalleryGrid, ArtworkViewer, UploadForm).
      
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
* **Lazy Loading:** Must implement image lazy loading by setting the `loading="lazy"` attribute on `<img>` tags.
* **Layout:** The gallery must use a modern CSS layout like `column-count` or CSS Grid to achieve a masonry effect.
* **`package.json`:** Must include `react`, `react-dom`, and `axios`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the masonry layout is responsive, images are lazy-loaded, and the lightbox viewer provides a smooth navigation experience. You may now begin.