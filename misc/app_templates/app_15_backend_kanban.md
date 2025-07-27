# Goal: Generate a Collaborative & Real-Time Flask Kanban API

This prompt directs the generation of the backend of a full-stack Kanban board application. The output must be a complete, production-ready API designed for real-time team collaboration and project management.

---

### **1. Persona (Role)**

Adopt the persona of a **Principal Engineer** for a leading agile project management software company. Your expertise is in building real-time collaborative systems, managing complex state changes, and ensuring data consistency.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that must accurately reflect the state of a Kanban board, including the precise order of tasks within each column.
* **Core Logic:** The system must handle drag-and-drop operations atomically.
* **Database Schema:** Use SQLite to support boards, columns, tasks, and an immutable activity log.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the transactional logic for moving a task, which involves updating positions in both source and destination columns. Plan for an immutable activity log and how to represent column order.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Board, Column, & Task Management:** Implement full CRUD endpoints for managing the core entities: boards, columns (lists), and tasks (cards).
2.  **Atomic Task Movement:** A critical endpoint (`POST /api/tasks/<id>/move`) that transactionally updates a task's column and its position within that column, re-ordering other tasks as necessary to maintain data integrity.
3.  **Activity Logging:** A system to automatically create an immutable log entry in a dedicated `Task_Activities` table for every significant action (e.g., task creation, movement).
4.  **User Authentication & Collaboration:** A standard user authentication system, with endpoints to invite users to a board.

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
    # (Implement all required routes for auth, boards, columns, and tasks)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Data Structure:** The response for `GET /api/boards/<id>` should return the full board object, with a nested list of columns, and each column should contain a nested list of its tasks, pre-sorted by `position`.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the task movement logic is fully transactional and correctly maintains the positional integrity of all tasks on the board. You may now begin.