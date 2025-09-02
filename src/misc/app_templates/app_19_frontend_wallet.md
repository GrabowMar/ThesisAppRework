# Goal: Generate an Intuitive & Secure React Crypto Wallet UI

This prompt directs the generation of the frontend of a cryptocurrency wallet application.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** specializing in FinTech and cryptocurrency applications. Your focus is on creating a secure, intuitive, and trustworthy user interface for managing digital assets.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite.
* **Backend API Integration:** The frontend will consume the mocked Flask wallet backend using relative paths for all API calls.
* **User Goal:** The user needs a clear and secure interface to view their balances, send and receive funds, and track their transaction history.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the main dashboard for displaying balances, the separate interfaces for sending and receiving, how to display transaction history clearly, and the UX for security confirmations like a PIN modal.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Wallet Dashboard:** A main view that displays the user's total portfolio value and a breakdown of balances for each cryptocurrency they hold.
2.  **Send & Receive Interface:** Two distinct views: one for sending crypto (with fields for recipient address and amount) and one for receiving, which displays the user's wallet address and a corresponding QR code.
3.  **Transaction History:** A view that displays a list of all past transactions (sent and received) with details like date, amount, and status.
4.  **Security Confirmation:** A modal or confirmation step that requires the user to re-authenticate or enter a PIN before finalizing a "send" transaction, simulating a key security feature.

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
    import QRCode from 'qrcode.react';
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for wallet balances, transactions, current view, etc.

      // 2. Event Handlers & API Calls: Define functions to handle sending transactions, fetching balances, and viewing history.

      // 3. Render Logic: Conditionally render different views (Dashboard, Send, Receive, History). The Send flow should include a confirmation modal.
      
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
* **Libraries:** Must use `axios` for API calls and a library like `qrcode.react` for generating QR codes.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, and `qrcode.react`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the transaction flow is clear, the security confirmation step is present, and balances are displayed correctly. You may now begin.