# Goal: Generate a Feature-Rich & Performant React E-Commerce SPA

This prompt directs the generation of the frontend of a full-stack e-commerce application.

---

### **1. Persona (Role)**

Adopt the persona of a **Lead Front-End Engineer** specializing in building high-performance, conversion-optimized e-commerce experiences with React.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite.
* **Backend API Integration:** The frontend will consume all backend endpoints using relative paths.
* **User Experience:** The primary goal is a fast, intuitive, and reliable shopping experience.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider global state management for the cart (using React Context), a multi-step checkout wizard, and optimistic UI updates for cart operations.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Product Discovery & Browse:** A main view that displays a grid of all products, with client-side controls for filtering and searching.
2.  **Shopping Cart Management:** A dedicated cart view to modify item quantities and see totals, plus a global cart icon in the header that always shows the correct item count.
3.  **Multi-Step Checkout Form:** A checkout "wizard" that guides the user through distinct steps for entering shipping and payment information.
4.  **Order Confirmation & History:** A success page displayed after checkout and a separate view for users to see their past orders.

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
    import React, { useState, useEffect, createContext, useContext } from 'react';
    import ReactDOM from 'react-dom/client';
    import axios from 'axios';
    import './App.css';

    // 2. Context
    // (Define and export a CartContext)

    // 3. Main App Component
    const App = () => {
      // 1. State Management: Define state for products, cart, current view, etc.
      
      // 2. Render Logic: Use conditional rendering to switch between different views (ProductList, Cart, Checkout, etc.).
      
      return (
        <CartContext.Provider value={/* cart state and functions */}>
          <div className="container">
            {/* Header with global cart icon */}
            {/* Main conditional rendering logic goes here */}
          </div>
        </CartContext.Provider>
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
* **State Management:** Must use `React.Context` to manage the global shopping cart state.
* **`package.json`:** Must include `react`, `react-dom`, and `axios`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the user journey is seamless and global cart state is managed correctly. You may now begin.