# Goal: Generate a Collaborative Flask API for Event Planning

This prompt directs the generation of the backend of a full-stack event planning application. The output must be a complete, production-ready API for managing events, guests, budgets, and tasks.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Backend Engineer** who builds collaborative productivity tools. You are an expert in designing systems for project management, guest coordination, and budget tracking.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that serves as the central coordination hub for planning an event.
* **Core Logic:** The system revolves around a central `Event` object, which has associated guests, budget items, and tasks.
* **Database Schema:** Use SQLite with tables for `Events`, `Guests`, `Budget_Items`, and `Tasks`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the relationships between events, guests, and budgets. Plan the logic for tracking RSVPs and calculating remaining budget funds.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Event Creation & Management:** Implement full CRUD endpoints for creating and managing the core details of an event (name, date, location, description).
2.  **Guest & RSVP Tracking:** Provide endpoints to manage a guest list for an event, send mock invitations, and track guest RSVP statuses (Attending, Declined, Maybe).
3.  **Budget & Expense Management:** A system to set an overall budget for an event and endpoints to log individual expenses against different categories (e.g., Venue, Catering), which are then subtracted from the total budget.
4.  **Task & Timeline Management:** Endpoints to create a checklist of tasks or a timeline of milestones associated with an event, with due dates and a boolean completion status.

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
    # (Implement all required routes for auth, events, guests, budget, and tasks)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Authorization:** Ensure that all event-related data can only be accessed or modified by the user who created the event.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the RSVP and budget tracking calculations are correct and that event data is properly scoped to the owner. You may now begin.