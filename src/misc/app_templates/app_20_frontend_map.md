# Goal: Generate an Interactive & Collaborative React Map Sharing SPA

This prompt directs the generation of the frontend of a full-stack map sharing application. The output must be a complete, responsive, and intuitive single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** specializing in interactive mapping applications. You have deep expertise in using mapping libraries like Leaflet within React to build dynamic and user-friendly geospatial interfaces.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite. The central component is an interactive map.
* **Backend API Integration:** The frontend will consume the Flask map sharing backend for all its data, using relative paths for API calls.
* **User Goal:** Users want to create custom maps, add points of interest, and draw routes easily.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider how to integrate a mapping library like `react-leaflet`. Plan the state management for markers and route waypoints, and how user clicks on the map will translate into creating new data.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Interactive Map Display:** The core component of the app, which renders a map using a library like `react-leaflet`. It must allow users to pan and zoom and must display markers and routes fetched from the backend.
2.  **Marker Creation & Management:** Functionality for users to click on the map to add a new marker (pin), provide a title and description, and see it displayed.
3.  **Route Planning Interface:** UI controls that allow a user to create a route by sequentially clicking points on the map. The resulting route should be drawn as a polyline on the map.
4.  **Location Search:** A search bar that allows users to look up a location. Upon selection, the map should pan and zoom to the corresponding coordinates returned by the backend.

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
    import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
    import 'leaflet/dist/leaflet.css';
    import axios from 'axios';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for markers, routes, map center, zoom level, etc.

      // 2. Event Handlers & API Calls: Define functions to handle map clicks (for adding markers), search submissions, and route creation.

      // 3. Render Logic: Render the MapContainer and dynamically map over state arrays to render Marker and Polyline components.
      
      return (
        <div className="container">
          {/* Main JSX structure including MapContainer goes here */}
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
* **Libraries:** Must use `react-leaflet` for the map interface and `axios` for API calls.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, `leaflet`, and `react-leaflet`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the map interactions are smooth and that markers and routes are displayed correctly based on the application state. You may now begin.