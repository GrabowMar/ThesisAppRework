# Goal: Generate a Data-Driven Flask API for Environmental Tracking

This prompt directs the generation of the backend for a full-stack environmental impact tracking application. The output must be a complete, production-ready API focused on data logging and analytics.

---

### **1. Persona (Role)**

Adopt the persona of a **Data-Oriented Backend Engineer** specializing in sustainability applications. Your expertise is in creating systems that accurately calculate environmental metrics and motivate positive user action.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that serves as the data backbone for a personal environmental impact logger.
* **Core Logic:** The system must calculate a user's carbon footprint based on their logged activities and track their participation in sustainability challenges.
* **Database Schema:** Use SQLite with tables for `Users`, `Carbon_Activities`, and `Challenges`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Decompose the task by considering:
* The logic for calculating carbon emissions from various activities (e.g., travel, energy).
* The structure for defining and tracking user progress in sustainability challenges.
* Endpoints for logging data and others for retrieving aggregated analytics.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Carbon Footprint Logging:** Create endpoints for users to log their daily activities that contribute to their carbon footprint, such as transportation, energy usage, and diet choices.
2.  **Resource Consumption Tracking:** Implement endpoints to allow users to log their consumption of resources like water and electricity, and to track their waste and recycling efforts.
3.  **Sustainability Challenges & Goals:** Provide a system with endpoints for users to join pre-defined environmental challenges (e.g., "No single-use plastic for a week") and to set personal sustainability goals.
4.  **Personalized Recommendations & Community:** Implement an endpoint to provide users with personalized, evidence-based eco-friendly tips, and another to show an anonymized community leaderboard or collective impact score.

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
    # (Implement all required routes for auth, carbon tracking, challenges, etc.)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Calculations:** The carbon calculation logic can use simplified, standardized emission factors for this simulation.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the carbon footprint calculations are logical and that the challenge tracking system correctly monitors user progress. You may now begin.