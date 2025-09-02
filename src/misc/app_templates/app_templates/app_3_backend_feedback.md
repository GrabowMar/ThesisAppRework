# Goal: Generate a Data-Driven Flask Feedback & Analytics API

This prompt directs the generation of the backend of a full-stack feedback collection and analysis application.

---

### **1. Persona (Role)**

Adopt the persona of a **Data-Oriented Backend Engineer**. You are an expert in building APIs that collect and validate data rigorously and provide analytical insights.

---

### **2. Context (Additional Information)**

* **System Architecture:** An API running in a container, designed to receive submissions from a public-facing form.
* **Database Schema:** Use SQLite with tables for `Feedback` submissions and `Categories`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider a modular validation strategy, the SQL queries for the analytics endpoint, and a simple rate-limiting strategy.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Feedback Submission with Validation:** Create a `POST /api/feedback` endpoint that accepts submission data. It must perform strict server-side validation on all fields (name, email, message length, etc.).
2.  **Data Persistence:** Upon successful validation, store the complete feedback submission in the SQLite database.
3.  **Feedback Retrieval:** An admin-focused `GET /api/feedback` endpoint that returns a paginated and filterable list of all feedback submissions.
4.  **Simple Analytics Endpoint:** A `GET /api/analytics` endpoint that performs data aggregation to return key metrics, such as the total number of submissions and the average rating.

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
    # (Import necessary libraries like Flask, CORS, sqlite3, os, and email_validator)

    # 2. App Configuration
    # (Initialize Flask app and CORS)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all the required API endpoints: /api/feedback (POST and GET), /api/analytics, /api/categories)
    
    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```

* **Libraries:** Must use the `email-validator` library for robust email validation.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `email-validator`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure that all validation rules are strictly enforced and the analytics queries are correct. You may now begin.