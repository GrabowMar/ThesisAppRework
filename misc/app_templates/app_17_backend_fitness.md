# Goal: Generate a Data-Driven Flask Fitness Logging API

This prompt directs the generation of the backend for a full-stack fitness tracking application. The output must be a complete, production-ready API focused on data logging and performance analytics.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Backend Engineer** specializing in data-intensive applications for the health and fitness sector. You are an expert in data modeling, statistics calculation, and building motivational goal-tracking systems.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that serves as the data backbone for a personal fitness logger.
* **Core Logic:** The system must accurately log detailed workout sessions and then aggregate that data to track long-term progress and records.
* **Database Schema:** Use SQLite with tables for `Users`, `Workouts`, a library of `Exercises`, `Progress_Logs`, and `Goals`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the data structures for a workout session (a workout containing multiple exercises, each with multiple sets). Plan the SQL queries needed for the statistics and personal records endpoints.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Workout & Exercise Management:** Implement full CRUD endpoints for logging workout sessions and managing a library of exercises, including custom user-created exercises.
2.  **Progress & Measurement Tracking:** Create endpoints to log various user progress metrics over time, such as body weight, and other body measurements.
3.  **Goal Setting & Achievement:** Provide endpoints for users to set personal fitness goals (e.g., target weight, lift amount) and update their progress towards them.
4.  **Statistics & Analytics:** An endpoint that aggregates user data to provide performance statistics, such as total workout volume, personal records for specific exercises, and progress trends.

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
    # (Implement all required routes for auth, workouts, exercises, progress, and goals)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Statistics Logic:** The analytics endpoint must contain correct SQL queries using functions like `SUM`, `AVG`, and `MAX` to calculate statistics.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure that workout data is stored correctly and that the statistical calculations are accurate. You may now begin.