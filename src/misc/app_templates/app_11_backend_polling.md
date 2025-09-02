# Goal: Generate a Secure & Analytics-Driven Flask Polling API

This prompt directs the generation of the backend of a full-stack polling application. The output must be a complete, production-ready API focused on voting integrity, real-time results, and data analytics.

---

### **1. Persona (Role)**

Adopt the persona of a **Data & Security-Focused Backend Engineer**. You specialize in building systems that handle voting and user-submitted data, with an emphasis on preventing fraud, ensuring data integrity, and providing powerful analytical insights.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API whose primary purpose is to allow users to create polls and securely collect votes.
* **Security & Integrity:** Preventing duplicate votes is a critical requirement.
* **Database Schema:** Use SQLite to record individual votes for auditing while also efficiently aggregating results.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the duplicate voting prevention strategy (by user ID for authenticated polls), the SQL queries needed for the analytics endpoint, and the logic for handling time-limited polls.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Poll Creation & Management:** Full CRUD endpoints for users to create, read, update, and delete polls with various options and settings (e.g., end dates).
2.  **Secure Voting System:** A single endpoint (`POST /api/polls/<id>/vote`) to cast votes, which performs validation to ensure the poll is active and prevents duplicate voting by the same user.
3.  **Real-Time Results Aggregation:** An endpoint (`GET /api/polls/<id>/results`) to retrieve the current results for a poll, with vote counts and percentages calculated on-the-fly.
4.  **User Authentication:** A standard system for user registration and login, required for creating polls and tracking votes.

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
    # (Import necessary libraries like Flask, CORS, sqlite3, os, Bcrypt)

    # 2. App Configuration
    # (Initialize Flask app and extensions)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for auth, polls, and voting)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Logic:** The voting logic must include a database query to check if a `(poll_id, user_id)` pair already exists before inserting a new vote. All time-based logic must use the `datetime` module.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the duplicate voting check is robust and the results are calculated accurately. You may now begin.