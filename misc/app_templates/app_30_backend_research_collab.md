# Goal: Generate a Collaborative Flask API for a Research Platform

This prompt directs the generation of the backend for a full-stack research collaboration application. The output must be a complete, production-ready API focused on project management, document sharing, and academic collaboration.

---

### **1. Persona (Role)**

Adopt the persona of a **Principal Backend Engineer** specializing in collaborative software for academic and scientific research. You are an expert in managing complex data relationships, version control, and permission-based access systems.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that serves as a central workspace for research teams.
* **Core Logic:** The system revolves around "Projects." Each project contains documents, tasks, and a list of collaborators with different access levels.
* **Database Schema:** Use SQLite with tables for `Users`, `Projects`, `Documents`, `Tasks`, and a table to manage `Project_Members` and their roles.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Decompose the problem by considering:
* The data model for a "Project" and its relationship to users (collaborators), documents, and tasks.
* A role-based access control system to manage permissions (e.g., owner, editor, viewer) within each project.
* The logic for a simple task management system within each project.
* A commenting system to allow discussions on projects or documents.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Project & Document Management:** Full CRUD endpoints for creating and managing research projects. Within each project, provide endpoints to upload, list, and delete documents (e.g., PDFs, datasets).
2.  **Collaborator & Permissions Management:** Implement endpoints to invite other registered users to a project (`POST /api/projects/<id>/invite`) and to manage their roles and permissions (e.g., 'editor', 'viewer').
3.  **Task Management & Milestones:** A system to create, assign, update the status of, and delete tasks within a specific research project.
4.  **Discussion & Annotation System:** Provide endpoints to allow collaborators on a project to leave comments on the project itself or on specific documents within it to facilitate discussions.

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
    # (Implement all required routes for auth, projects, documents, tasks, and comments)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Authorization:** Every endpoint that modifies a project or its contents must verify that the authenticated user is a member of that project and has the appropriate permissions (e.g., 'editor' role to add a task).
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the permission system is robust and that a user cannot access or modify a project they are not a part of. You may now begin.