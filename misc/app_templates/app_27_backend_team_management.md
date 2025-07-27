# Goal: Generate a Collaborative Flask API for Sports Team Management

This prompt directs the generation of the backend for a full-stack sports team management application. The output must be a complete, production-ready API for coaches and players.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Backend Engineer** specializing in sports technology and team coordination platforms. You are an expert in data modeling for rosters, schedules, and performance statistics.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that acts as a central hub for a sports team's data.
* **Core Logic:** The system must manage a player roster, track schedules for training and matches, and log basic performance and health data.
* **Database Schema:** Use SQLite with tables for `Players`, `Events` (for matches/training), `Attendance`, and `Injuries`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the data model for a player profile, the structure of an event that can be either a practice or a game, and how to link player attendance and stats to those events.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Player Roster & Profile Management:** Implement full CRUD endpoints for managing player profiles, including personal details, positions, and current status (e.g., active, injured).
2.  **Schedule & Attendance Management:** Create endpoints to schedule team events like training sessions and matches, and to log which players attended each event.
3.  **Performance & Health Logging:** Provide endpoints for coaches to log player performance statistics from matches (e.g., goals, assists) and to record and track player injuries.
4.  **Team Communication:** A simple system for coaches or managers to post announcements (`POST /api/announcements`) that can be retrieved by the team.

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
    # (Implement all required routes for auth, players, schedule, performance, etc.)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Authorization:** Routes for adding/editing players, schedules, and stats should be protected and only accessible to an authenticated user (e.g., a coach).
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure that player and event data are linked correctly and that the authorization logic protects sensitive management endpoints. You may now begin.