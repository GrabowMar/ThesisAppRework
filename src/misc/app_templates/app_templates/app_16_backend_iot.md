# Goal: Generate a Scalable & Real-Time Flask IoT Controller API

This prompt directs the generation of the backend of a full-stack IoT device management application. The output must be a complete, production-ready API using WebSockets for real-time communication.

---

### **1. Persona (Role)**

Adopt the persona of a **Backend Engineer** specializing in IoT systems. Your expertise is in real-time communication, device management, and creating automation engines for connected hardware.

---

### **2. Context (Additional Information)**

* **System Architecture:** A real-time server using Flask and Flask-SocketIO to manage IoT devices, receive sensor data, and send commands.
* **Database Schema:** Use SQLite to persist device information, sensor data history, and automation rules.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the separation between standard HTTP routes for management and WebSocket events for real-time data. Plan the structure for an in-memory state to track device connectivity and the logic for the automation rule engine.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Device Management & Registration:** Implement HTTP endpoints to register new IoT devices (`POST /api/devices`), retrieve a list of all devices (`GET /api/devices`), and view the details of a specific device.
2.  **Real-Time Device Communication:** Implement WebSocket event handlers (`device_status_update`, `sensor_data_update`) for real-time monitoring and an HTTP endpoint (`POST /api/devices/<id>/commands`) to send commands to devices.
3.  **Sensor Data Collection & History:** Create an endpoint for devices to post sensor data (`POST /api/devices/<id>/data`) and another endpoint for users to retrieve historical sensor data for a device (`GET /api/devices/<id>/data`).
4.  **Automation Engine:** Provide full CRUD endpoints for managing automation rules (`GET`, `POST`, `PUT`, `DELETE /api/automation/rules`) that can trigger actions based on sensor data (e.g., "IF temperature > 30 THEN send 'turn_on_fan' command").

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
    # (Import necessary libraries like Flask, Flask-SocketIO, CORS, sqlite3, os)

    # 2. App Configuration
    # (Initialize Flask app and SocketIO extension)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes (HTTP)
    # (Implement all required HTTP endpoints for devices, commands, and automation rules)

    # 5. WebSocket Events
    # (Implement @socketio.on() handlers for real-time events)
    
    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app using socketio.run on host '0.0.0.0' and port 5005)
        pass
    ```
* **Real-Time Logic:** The backend must be able to broadcast messages to the frontend via WebSockets when specific conditions are met by the automation engine.
* **`requirements.txt`:** Must contain `Flask`, `Flask-SocketIO`, and `Flask-CORS`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the real-time events are handled correctly and the automation rule logic is sound. You may now begin.