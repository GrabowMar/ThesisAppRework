# Goal: Generate a Scalable Flask API for a Professional Network

This prompt directs the generation of the backend for a career networking application. The output must be a complete, production-ready API for managing professional profiles, connections, and job listings.

---

### **1. Persona (Role)**

Adopt the persona of a **Principal Engineer** for a professional networking platform. Your expertise is in designing systems for social graphs, messaging, and career marketplaces.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that is the backbone of a professional social network.
* **Core Logic:** The system must manage user profiles, the connection graph between users (pending, accepted), and a job board.
* **Database Schema:** Use SQLite with tables for `Users`, `Experience`, `Education`, `Connections`, and `Jobs`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the data model for a connection request (requester, recipient, status). Plan the logic for a job board where users can post and others can apply.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Professional Profile Management:** Full CRUD endpoints for users to create and manage their professional profiles, including sections for work experience and education.
2.  **Connection Management:** Endpoints to handle the connection lifecycle: sending a connection request (`POST /api/connections/request`), accepting a request (`PUT /api/connections/<id>/accept`), and viewing one's list of connections (`GET /api/connections`).
3.  **Job Marketplace:** Full CRUD endpoints for users to post new job listings and for other users to search/filter and view those listings.
4.  **User-to-User Messaging:** A simple, real-time messaging system (using WebSockets with Flask-SocketIO) that allows connected users to send and receive private messages.

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
    # (Import necessary libraries like Flask, Flask-SocketIO, CORS, sqlite3, os, Bcrypt)

    # 2. App Configuration
    # (Initialize Flask app and SocketIO extension)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes (HTTP)
    # (Implement all required HTTP endpoints for auth, profiles, connections, and jobs)
    
    # 5. WebSocket Events
    # (Implement @socketio.on() handlers for sending/receiving messages)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app using socketio.run on host '0.0.0.0' and port 5005)
        pass
    ```
* **Authorization:** Ensure that profile updates can only be made by the profile owner.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, `Flask-Bcrypt`, and `Flask-SocketIO`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the connection management logic is correct and that the messaging system only allows communication between connected users. You may now begin.