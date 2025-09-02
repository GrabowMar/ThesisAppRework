# Goal: Generate a Feature-Rich & Reliable Flask Notes API

This prompt directs the generation of the backend of a full-stack note-taking application. The output must be a complete, production-ready API with a focus on content management and data synchronization.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Backend Engineer** specializing in consumer-facing applications where data integrity and user content are paramount. You are an expert in Flask, text processing, and designing performant APIs for content-heavy platforms.

---

### **2. Context (Additional Information)**

* **System Architecture:** An API running in a container, designed to support a rich client-side application that will make frequent requests for auto-saving.
* **Content Handling:** Notes will contain rich text (HTML). All user-generated content must be sanitized to prevent Cross-Site Scripting (XSS).
* **Database Schema:** Use SQLite with tables for `Notes`, `Categories`, and `Tags`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Decompose the problem by considering: a lightweight auto-save endpoint, a full-text search strategy, a note archiving/lifecycle system, and secure sanitization for all rich text content.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Note Management (CRUD):** Implement endpoints for full Create, Read, Update, and Delete operations on notes. Notes contain a title and HTML content.
2.  **Content Organization:** Create endpoints to manage `Categories` and `Tags`, and to associate them with notes, allowing for robust organization.
3.  **Note Lifecycle Management:** Implement endpoints for archiving and restoring notes (`POST /api/notes/<id>/archive`, `POST /api/notes/<id>/restore`) and a separate, lightweight endpoint for auto-saving (`POST /api/notes/<id>/auto-save`).
4.  **Full-Text Search:** Provide a single endpoint (`GET /api/search`) that performs a case-insensitive, full-text search across all note titles and content.

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
    # (Import necessary libraries like Flask, CORS, sqlite3, os, and bleach)

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
* **Security:** Must use a library like `bleach` to sanitize all incoming HTML content before it is stored in the database.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `bleach`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure that content sanitization is applied to all relevant endpoints and that the search and auto-save functionalities are implemented correctly. You may now begin.