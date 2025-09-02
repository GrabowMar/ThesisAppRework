# Goal: Generate a Collaborative & Version-Controlled Flask Wiki API

This prompt directs the generation of the backend for a full-stack wiki platform. The output must be a complete, production-ready API focused on content versioning and collaborative editing.

---

### **1. Persona (Role)**

Adopt the persona of a **Principal Engineer** specializing in content management and collaborative systems. You are an expert in version control, text processing, and building secure, scalable knowledge bases.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that serves as the backend for a collaborative wiki.
* **Content Handling:** The core content is Markdown, which must be sanitized. A full history of all changes must be retained.
* **Database Schema:** Use SQLite to manage pages, categories, and a full revision history for every page.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the versioning system: every update should create a new revision, not modify the existing one. Plan the logic for retrieving a specific revision and for reverting a page to an old revision.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Wiki Page Management:** Implement full CRUD endpoints for creating, reading, and updating wiki pages. Updating a page must create a new revision.
2.  **Content Versioning & History:** A system to automatically save a new revision of a page on every update, with endpoints to view the complete history of a page (`GET /api/pages/<slug>/history`) and revert to a previous revision (`POST /api/pages/<slug>/revert`).
3.  **Search & Discovery:** A full-text search endpoint (`GET /api/search`) that searches across all current page titles and content, and endpoints to manage page organization through categories.
4.  **User Authentication & Contributions:** A standard user auth system where all page edits (revisions) are associated with the user who made the change.

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
    # (Import necessary libraries like Flask, CORS, sqlite3, os, markdown, bleach)

    # 2. App Configuration
    # (Initialize Flask app and extensions)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for auth, workouts, exercises, progress, and goals)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Security:** Must use `bleach` to sanitize all HTML content rendered from Markdown.
* **Logic:** The `update` endpoint must create a new entry in a `Page_Revisions` table. The `revert` endpoint must copy content from an old revision to create a new one.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, `Flask-Bcrypt`, `markdown`, and `bleach`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the versioning system is working correctly and that reverting to an old revision functions as expected. You may now begin.