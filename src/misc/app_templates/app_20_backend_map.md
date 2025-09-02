# Goal: Generate a Collaborative & Location-Aware Flask Map API

This prompt directs the generation of the backend for a full-stack map sharing application. The output must be a complete, production-ready API focused on managing geographic data.

---

### **1. Persona (Role)**

Adopt the persona of a **Geospatial Backend Engineer**. You specialize in building systems that manage location data, process spatial queries, and handle collaborative mapping features.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that serves as the backend for a collaborative map sharing platform.
* **Core Logic:** The system must manage user-created maps, which can contain custom markers and routes.
* **Database Schema:** Use SQLite to store maps, markers, routes, and user data.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the data structures for maps, markers, and routes (a sequence of coordinates). Plan how users will be associated with their created content and how to handle basic location searches (mock geocoding).

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Map & Marker Management:** Implement full CRUD endpoints for creating custom maps, and for adding, updating, and deleting location markers (pins) on a specific map.
2.  **Route Planning:** Provide endpoints to create a route by saving an ordered sequence of waypoints (coordinates) and to retrieve the waypoints for a given route.
3.  **Location Search & Geocoding (Mocked):** Create a search endpoint (`GET /api/search`) that accepts a text address and returns mock latitude/longitude coordinates.
4.  **User Authentication & Ownership:** A standard user authentication system to ensure that maps, markers, and routes are associated with a user and can only be modified by their owner.

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
    # (Implement all required routes for auth, maps, markers, routes, and search)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Logic:** The `search` endpoint can return a fixed coordinate for any query to simulate geocoding.
* **Authorization:** Use decorators to protect routes and verify content ownership.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the relationship between maps, markers, and routes is correctly implemented and that ownership is enforced. You may now begin.