# Goal: Generate a Real-Time & Interactive React Chat Application SPA

This prompt directs the generation of the frontend of a full-stack, real-time chat application. The output must be a complete, responsive, and highly interactive single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Frontend Developer** specializing in real-time applications using React and WebSockets. Your expertise lies in managing WebSocket connections, handling real-time data flow, and building fluid, responsive user interfaces.

---

### **2. Context (Additional Information)**

* **Application Architecture:** This is a React SPA built with Vite. Its core functionality is powered by a continuous WebSocket connection to the Flask-SocketIO backend.
* **Backend API Integration:** The frontend will use standard HTTP requests to fetch initial data (like room lists) and a `socket.io-client` connection for all real-time events. All API calls must be made to relative paths (e.g., `/api/rooms`) to leverage the Vite proxy.
* **Real-Time Events:** The UI must react instantly to WebSocket events such as `message`, `user_joined`, `user_left`, and `typing`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider how to manage the Socket.IO connection lifecycle within React's `useEffect` hook, including setup and cleanup. Plan the state management for messages and user lists, and the auto-scrolling logic for the message display.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Connection & Room Selection:** An initial view where a user can enter a username and select from a list of available chat rooms (fetched via HTTP) to join.
2.  **Real-Time Message Display:** A main chat view that displays a list of messages for the current room. This list must update in real-time as new messages are received via the WebSocket `message` event, and it must auto-scroll to the bottom.
3.  **Message Sending:** An input form that allows the user to type and send messages. Sending a message should emit a `send_message` event over the WebSocket.
4.  **Live User Presence:** A sidebar that displays a list of users currently in the room. This list must update in real-time based on `user_joined` and `user_left` events. The UI must also display a "User is typing..." indicator when a `typing` event is received.

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
    import React, { useState, useEffect, useRef } from 'react';
    import ReactDOM from 'react-dom/client';
    import io from 'socket.io-client';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for user, room, messages, online users, etc.
      
      // 2. Refs: Define a ref for the message container to handle auto-scrolling.

      // 3. Lifecycle Hooks: Use useEffect to initialize the socket connection, register all event handlers (e.g., socket.on('message', ...)), and handle cleanup (socket.disconnect()).
      
      // 4. Event Handlers: Define functions for joining a room, sending a message, and emitting typing events.

      // 5. Render Logic: Conditionally render a 'Join' view or the main 'Chat' view.
      
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
* **Libraries:** Must use `socket.io-client` for WebSocket communication and `axios` for initial data fetching.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, and `socket.io-client`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the WebSocket connection is managed correctly, real-time events are handled smoothly, and the UI provides a fluid chat experience. You may now begin.