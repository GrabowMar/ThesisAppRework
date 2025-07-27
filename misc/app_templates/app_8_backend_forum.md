# Goal: Generate a Community-Driven & Moderated Flask Forum API

This prompt directs the generation of the backend of a full-stack online forum. The output must be a complete, production-ready API designed to foster and manage community discussions.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Backend Engineer** specializing in building large-scale community platforms. Your expertise lies in designing systems for user-generated content, moderation, reputation, and complex, threaded discussions.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that acts as the central hub for all forum activity.
* **Core Logic:** The system must manage nested comments, voting, and moderation.
* **Database Schema:** Use SQLite, designed to efficiently handle nested comments and votes.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider an efficient way to query and represent nested comments, a voting system that prevents duplicates, and an authorization layer for content ownership and moderation.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Thread & Content Management:** Implement full CRUD endpoints for authenticated users to create, read, update, and delete forum threads.
2.  **Nested Comment System:** Create endpoints to allow users to post comments on threads (`POST /api/threads/<id>/comments`) and reply to other comments, forming a nested structure. The retrieval endpoint must return comments in this threaded format.
3.  **Voting Mechanism:** Provide endpoints for authenticated users to upvote or downvote both threads and comments. The system must prevent a user from voting on the same item more than once.
4.  **User Authentication & Authorization:** A secure user registration and login system. The authorization logic must ensure users can only edit or delete their own content.

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
    # (Initialize Flask app and extensions)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for auth, threads, comments, and voting)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Logic:** The comments retrieval endpoint must process a flat list of comments from the database into a nested JSON structure before sending the response.
* **Authorization:** Use decorators to protect routes and verify content ownership.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the nested comment structuring is correct, the voting logic prevents duplicates, and the authorization is correctly implemented. You may now begin.