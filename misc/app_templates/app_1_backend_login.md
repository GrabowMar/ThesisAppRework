# Goal: Generate a Secure & Production-Ready Flask Authentication API

This prompt directs the generation of the backend for a complete user authentication system.

---

### **1. Persona (Role)**

Adopt the persona of a **Security-Focused Backend Engineer**. Your expertise is in building secure authentication systems, managing user sessions, and protecting against common vulnerabilities.

---

### **2. Context (Additional Information)**

* **System Architecture:** This API is the central authentication service for a web application, running in a container.
* **Database Schema:** The system will use a SQLite database with a `Users` table (`id`, `username`, `email`, `password_hash`, `created_at`).

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Decompose the task by considering the user registration flow, the login flow, session management, and the structure for protected routes.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Secure User Registration:** Create a `POST /api/register` endpoint that validates user input, checks for uniqueness, and stores the user with a securely hashed password.
2.  **Stateful User Login:** Create a `POST /api/login` endpoint that authenticates a user by verifying their credentials and establishes a persistent user session upon success.
3.  **Session Management:** Implement session-based logic with a `POST /api/logout` endpoint to destroy the session and a `GET /api/user` endpoint to retrieve the current user's data if a session exists.
4.  **Protected Content Endpoint:** Create a `GET /api/dashboard` endpoint that is strictly protected and only returns data if the user is authenticated with a valid session.

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
    # (Import necessary libraries like Flask, CORS, Bcrypt, sqlite3, os)

    # 2. App Configuration
    # (Initialize Flask app and extensions like CORS and Bcrypt)

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

* **Libraries:** Must use `Flask-Bcrypt` for password hashing.
* **Security:** Use a decorator (e.g., `@login_required`) to protect sensitive routes.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure all endpoints handle authentication correctly and protected routes are inaccessible without a session. You may now begin.