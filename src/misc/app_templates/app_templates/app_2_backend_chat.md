# Goal: Generate a Scalable & Real-Time Flask Chat API

This prompt directs the generation of the backend of a full-stack, real-time chat application. The output must be a complete, production-ready API using WebSockets.

---

### **1. Persona (Role)**

Adopt the persona of a **Backend Specialist** with deep expertise in real-time communication protocols and stateful application services. You are an expert in Flask-SocketIO, managing user sessions, and handling concurrent connections.

---

### **2. Context (Additional Information)**

* **System Architecture:** This is a real-time server using Flask and Flask-SocketIO. It must manage the state of multiple chat rooms and the users within them.
* **Database Schema:** Use SQLite to persist rooms and message history. User presence is managed in memory.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Decompose the problem by considering:
* How to manage the state of connected users and their association with different rooms. A dictionary or a similar in-memory structure is suitable.
* The sequence of events for a user joining a room.
* The logic for broadcasting events only to members of a specific room.
* Handling disconnects gracefully to ensure users are removed from all rooms they were in.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Room and Message Persistence:** Implement HTTP endpoints to manage chat rooms (`GET /api/rooms`, `POST /api/rooms`) and retrieve message history for a room (`GET /api/messages/<room_id>`).
2.  **Real-Time Connection & Room Management:** Implement WebSocket event handlers (`connect`, `disconnect`, `join_room`, `leave_room`) to manage user presence in chat rooms and broadcast join/leave notifications to the correct room members.
3.  **Live Message Broadcasting:** Create a `send_message` WebSocket event that receives a message from a client, persists it to the database for history, and then broadcasts it in real-time to all other clients in the sender's room.
4.  **User Presence Indicators:** Implement a `typing` WebSocket event that broadcasts a user's typing status to their room, allowing the UI to show "User is typing..." notifications.

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

    # 4. Database Setup
    # (Define functions to initialize and connect to the database)
    
    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all the required API endpoints here based on the directive)

    # 6. Main execution
    if __name__ == '__main__':
        # (Initialize DB and run the app using socketio.run on host '0.0.0.0' and port 5005)
        pass
    ```
* **Broadcasting:** All broadcasting events (e.g., `emit`) must use the `to=room` argument to ensure messages are sent only to the intended room members.
* **`requirements.txt`:** Must contain `Flask`, `Flask-SocketIO`, and `Flask-CORS`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure that room-based broadcasting is implemented correctly and that user state is managed properly across connect and disconnect events. You may now begin.