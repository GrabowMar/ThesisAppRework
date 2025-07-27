# Goal: Generate a Secure & Compassionate Flask Mental Health API

This prompt directs the generation of the backend for a mental health and wellness tracking application. The output must be a complete, production-ready API that prioritizes user privacy and data security.

---

### **1. Persona (Role)**

Adopt the persona of a **HealthTech Backend Engineer** with a specialization in mental wellness applications. You are an expert in data encryption, privacy compliance (like HIPAA), and building systems that handle sensitive personal data.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that provides a secure space for users to log and reflect on their mental state.
* **Security Model:** Data privacy is the absolute highest priority. All personally identifiable and sensitive data (like journal entries) must be encrypted in the database.
* **Database Schema:** Use SQLite with tables for `Users`, `Mood_Entries`, and `Journal_Entries`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider a simple but effective encryption strategy for journal entries (e.g., using the `cryptography` library). Plan the endpoints for mood tracking and how they might correlate with journal entries. Design a non-authenticated endpoint for crisis resources.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Mood & Stress Tracking:** Implement endpoints for users to log their daily mood and stress levels, including associated emotions or triggers.
2.  **Secure Journaling:** Provide full CRUD endpoints for creating and retrieving journal entries. The content of the entries must be encrypted before being stored in the database and decrypted only when requested by the authenticated user.
3.  **Wellness & Goal Management:** Create endpoints to manage a library of evidence-based coping strategies and allow users to set and track their personal wellness goals.
4.  **Crisis Support & Resources:** A dedicated, non-protected endpoint (`GET /api/resources/crisis`) to retrieve a static list of immediate crisis support resources (e.g., emergency hotlines).

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
    # (Import necessary libraries like Flask, CORS, sqlite3, os, Bcrypt, and Fernet from cryptography)

    # 2. App Configuration
    # (Initialize Flask app and extensions)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for auth, mood, journal, goals, and crisis resources)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Encryption:** Must use the `cryptography` library (specifically `Fernet`) to encrypt and decrypt journal entry content. The encryption key should be handled securely.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, `Flask-Bcrypt`, and `cryptography`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure journal entries are properly encrypted and decrypted, and that the crisis support endpoint is publicly accessible. You may now begin.