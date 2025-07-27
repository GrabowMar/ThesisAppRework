# Goal: Generate a Conflict-Free & Reliable Flask Reservation API

This prompt directs the generation of the backend of a full-stack reservation and booking system. The output must be a complete, production-ready API focused on preventing booking conflicts and managing availability.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Backend Engineer** specializing in high-availability scheduling and booking systems. Your primary expertise is in database transactions, conflict resolution, and designing APIs that guarantee booking integrity.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that manages bookable time slots for various resources and prevents any double-bookings.
* **Core Logic:** The system must check for availability in a transactionally safe manner before confirming any reservation.
* **Database Schema:** Use SQLite to store resources (e.g., rooms, tables), their availability rules, and the reservations themselves.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the core conflict detection query, ensuring the booking process is an atomic transaction, and how to represent a resource's general availability.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Resource & Availability Management:** Implement endpoints to manage bookable resources (`GET /api/resources`) and to check their availability for a given date and time (`GET /api/availability`).
2.  **Transactional Reservation Creation:** A `POST /api/reservations` endpoint that uses a database transaction to perform a final availability check (preventing overlaps) and insert the new booking atomically.
3.  **Reservation Lifecycle Management:** Provide endpoints for an authenticated user to view their own reservations (`GET /api/reservations/my`) and to cancel an existing reservation (`DELETE /api/reservations/<id>`).
4.  **User Authentication:** A standard system for user registration and login, which is required to create and manage reservations.

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
    # (Import necessary libraries like Flask, CORS, sqlite3, os, datetime, Bcrypt)

    # 2. App Configuration
    # (Initialize Flask app and extensions)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for auth, resources, availability, and reservations)
    
    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Transactional Booking:** The reservation creation endpoint must wrap its database logic in a transaction.
* **Conflict Detection:** The logic must include a robust SQL query to check for overlapping time ranges.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the reservation creation process is fully transactional and that the time-overlap conflict detection logic is correct. You may now begin.