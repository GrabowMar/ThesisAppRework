# Goal: Generate an Enterprise-Grade Flask E-Commerce API

This prompt directs the generation of the backend of a full-stack e-commerce application.

---

### **1. Persona (Role)**

Adopt the persona of a **Principal Backend Engineer** specializing in high-traffic e-commerce systems. You are an expert in Flask, transactional database operations, and API security.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API designed for high concurrency.
* **Database Schema:** Use SQLite with tables for `Products`, `Orders`, and `Order_Items`. The cart will be session-based.
* **Financial Calculations:** All monetary values must be handled with precision.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider transactional inventory management, accurate price calculations, and the order state machine.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Product Catalog Management:** Implement endpoints to list all available products with filtering (`GET /api/products`) and retrieve the details for a single product (`GET /api/products/<id>`).
2.  **Session-Based Shopping Cart:** Implement endpoints to manage a shopping cart stored in the user's session, including adding, updating, and viewing the cart.
3.  **Transactional Checkout Process:** Create a `POST /api/checkout` endpoint that validates cart inventory, creates an `Orders` record, and decrements product stock within a single, atomic database transaction.
4.  **Order History Retrieval:** Implement a protected endpoint (`GET /api/orders`) that allows an authenticated user to view a history of their past orders.

---

### **5. Output Specification (Answer Engineering)**

#### **Deliverables**

Generate the following two files. Do **not** generate a `Dockerfile`.

1.  `app.py`: A completed version of the skeleton provided below.
2.  `requirements.txt`: The Python dependency list.

#### **Code Quality & Technical Mandates**

* **`app.py` Skeleton:**
    ```python
    # 1. Imports
    # (Import necessary libraries like Flask, CORS, sqlite3, os, and Decimal)

    # 2. App Configuration
    # (Initialize Flask app and CORS)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for products, cart, checkout, and orders)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Data Integrity:** Must use Python's `Decimal` type for all currency values.
* **Transactional Logic:** The `/api/checkout` endpoint must wrap its database operations in a transaction.
* **`requirements.txt`:** Must contain `Flask` and `Flask-CORS`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure calculations are precise and database transactions are correctly implemented. You may now begin.