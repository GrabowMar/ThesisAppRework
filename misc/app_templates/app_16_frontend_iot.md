# Goal: Generate a Real-Time React IoT Controller Dashboard

This prompt directs the generation of the frontend of a full-stack IoT device management application. The output must be a complete, responsive, and highly interactive single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Frontend Developer** specializing in real-time dashboards and data visualization for IoT applications. Your focus is on creating a clear, responsive, and highly interactive interface for monitoring and controlling devices.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite, using WebSockets for real-time data updates.
* **Backend API Integration:** The frontend will consume both the HTTP API for device management and the WebSocket connection for live data streams. All calls must use relative paths.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider how to manage the WebSocket connection lifecycle. Plan the state management for a list of devices whose properties (like temperature) update in real-time. Think about how to present historical data using charts.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Real-Time Device Dashboard:** A main dashboard view that displays a grid of all registered IoT devices, showing their live status (e.g., online/offline, key sensor readings) updated in real-time via WebSockets.
2.  **Interactive Device Control Interface:** A detailed view for a single device, showing its complete data and providing interactive controls (e.g., switches, sliders) to send commands to the device via the API.
3.  **Historical Data Visualization:** A view that displays historical sensor data for a device using charts (e.g., a line chart from `react-chartjs-2`) with options to select time ranges.
4.  **Automation Rule Management:** A UI for creating, viewing, and deleting automation rules (e.g., "IF temperature > 30 THEN turn on fan").

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
    import { Line } from 'react-chartjs-2';
    // ... other chart.js imports
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for devices, sensor data, automation rules, etc.
      
      // 2. Lifecycle Hooks: Use useEffect to fetch initial data and to set up/tear down the WebSocket connection and its event listeners.

      // 3. Event Handlers & API Calls: Define functions to handle sending commands and managing automation rules.

      // 4. Render Logic: Conditionally render different views (Dashboard, DeviceDetails, etc.).
      
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
* **Libraries:** Must use `axios`, `socket.io-client`, and `react-chartjs-2`.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, `socket.io-client`, `chart.js`, and `react-chartjs-2`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the WebSocket is handled correctly, real-time updates are reflected in the UI, and charts display historical data properly. You may now begin.