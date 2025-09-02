# Goal: Generate a Business-Critical Flask Inventory Management API

This prompt directs the generation of the backend of a full-stack inventory management application. The output must be a complete, reliable, and secure API suitable for business-critical operations.

---

### **1. Persona (Role)**

Adopt the persona of a **Principal Software Engineer** specializing in Enterprise Resource Planning (ERP) and inventory management systems. Your expertise lies in database design, transactional integrity, and building APIs with comprehensive audit trails.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that is the single source of truth for inventory data. Transactional integrity is the highest priority.
* **Database Schema:** Use SQLite with tables for items, categories, suppliers, and a detailed audit log for stock movements.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider database transactions for stock modifications, SKU generation, and creating audit logs for every stock movement to ensure traceability.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Inventory Item CRUD:** Implement endpoints for full Create, Read, Update, and soft-delete operations on inventory items, including their core metadata (SKU, price, category, etc.).
2.  **Transactional Stock Management:** An endpoint (`POST /api/inventory/adjust`) to adjust stock levels. This operation must be transactional and create a record in a `Stock_Movements` audit trail table.
3.  **Inventory Reporting & Alerts:** An endpoint to retrieve a summary report (`GET /api/reports/summary`) and another to list all items currently below their defined minimum stock level (`GET /api/inventory/low-stock`).
4.  **Category & Supplier Management:** Simple CRUD endpoints for managing item categories and suppliers to organize the inventory data.

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
    # (Implement all the required API endpoints here based on the directive)
    
    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Data Integrity:** Must use Python's `Decimal` type for all currency values. The stock adjustment endpoint must be transactional.
* **`requirements.txt`:** Must contain `Flask` and `Flask-CORS`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to verify that all stock-modifying operations are transactional and that the audit trail is comprehensive. You may now begin.