# Goal: Generate a Content-Rich & Secure Flask Blog API

This prompt directs the generation of the backend of a full-stack blog platform.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Software Engineer** specializing in content management systems. You are an expert in Flask, user authentication, and secure content processing.

---

### **2. Context (Additional Information)**

* **System Architecture:** An API running in a container to serve a dynamic React frontend.
* **Content Type:** The primary content is Markdown, which must be sanitized.
* **Database Schema:** Use SQLite with tables for `Users`, `Posts`, `Comments`, and `Categories`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider how to securely process Markdown, handle nested comments, implement ownership-based authorization, and structure paginated API responses.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **User Authentication & Post Management:** Implement user registration/login and full CRUD for blog posts, restricting edit/delete operations to the post owner.
2.  **Content Processing & Security:** When posts are created or updated, process the provided Markdown content into HTML and sanitize the result using `bleach` to prevent XSS attacks.
3.  **Nested Comment System:** Implement endpoints to allow authenticated users to post comments (`POST /api/posts/<id>/comments`) and retrieve them in a nested structure.
4.  **Taxonomy & Discovery:** Provide endpoints to list all blog posts with pagination and filtering (`GET /api/posts`), and an endpoint to list all available categories (`GET /api/categories`).

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
    # (Import necessary libraries like Flask, CORS, Bcrypt, sqlite3, os, markdown, bleach)

    # 2. App Configuration
    # (Initialize Flask app and extensions)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for auth, posts, comments, and categories)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Libraries:** Must use `Flask-Bcrypt`, `markdown`, and `bleach`.
* **Logic:** The comments endpoint must process a flat list of comments from the DB into a nested JSON structure before responding.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, `Flask-Bcrypt`, `markdown`, and `bleach`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure authorization checks are correct, content sanitization is applied, and the nested comments logic is sound. You may now begin.