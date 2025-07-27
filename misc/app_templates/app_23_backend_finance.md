# Goal: Generate a Secure & Analytical Flask Personal Finance API

This prompt directs the generation of the backend for a full-stack personal finance application. The output must be a complete, production-ready API focused on data integrity and insightful analytics.

---

### **1. Persona (Role)**

Adopt the persona of a **FinTech Backend Engineer**. Your expertise lies in building secure systems for financial data, creating robust transaction ledgers, and implementing budgeting and goal-tracking logic.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that serves as a secure ledger for a user's financial data.
* **Core Logic:** The system must accurately track transactions, compare spending against user-defined budgets, and calculate progress towards financial goals.
* **Database Schema:** Use SQLite with tables for `Transactions`, `Categories`, `Budgets`, and `Financial_Goals`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the data model for transactions and how they link to budgets and categories. Plan the SQL queries required to aggregate spending by category and compare it against budget limits.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Transaction Management:** Implement full CRUD endpoints for logging income and expense transactions and assigning them to user-defined categories.
2.  **Budget Creation & Monitoring:** Create endpoints that allow users to set monthly or weekly budgets for specific spending categories and an endpoint to check their current spending against those budgets.
3.  **Financial Goal Setting:** Provide a system for users to set savings or debt-reduction goals and log contributions towards them.
4.  **Financial Reporting:** An endpoint that aggregates transaction data to provide a summary report, such as a monthly breakdown of spending by category or a simple income vs. expense statement.

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
    # (Import necessary libraries like Flask, CORS, sqlite3, os, Bcrypt, Decimal)

    # 2. App Configuration
    # (Initialize Flask app and extensions)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for auth, transactions, budgets, goals, and reports)
    
    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Data Integrity:** Must use Python's `Decimal` type for all monetary values to ensure accuracy.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure that budget tracking logic is correct and that financial reports accurately reflect the transaction data. You may now begin.