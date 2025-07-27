# Goal: Generate a High-Performance & Scalable Flask Microblog API

This prompt directs the generation of the backend of a full-stack microblogging platform, similar to Twitter. The output must be a complete, production-ready API designed for high-frequency interactions and efficient feed generation.

---

### **1. Persona (Role)**

Adopt the persona of a **Principal Engineer** from a major social media company. Your expertise is in designing highly scalable, low-latency APIs, efficient database schemas for social graphs, and complex feed generation algorithms.

---

### **2. Context (Additional Information)**

* **System Architecture:** A write-heavy, containerized API that must be optimized for fast reads, especially for the user feed.
* **Core Logic:** The most critical components are the social graph (follows/followers) and the feed generation logic.
* **Database Schema:** Use SQLite, optimized for fast lookups of user relationships and chronological posts.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider an efficient query for the main user feed, idempotent logic for likes and follows, and a method for parsing hashtags and mentions from post content.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Post & Comment Management:** Implement full CRUD endpoints for creating, reading, and deleting short text-based posts (microblogs) and their associated comments.
2.  **Social Graph & Interactions:** Create endpoints for users to follow/unfollow each other (`POST /api/users/<id>/follow`) and to like/unlike posts (`POST /api/posts/<id>/like`).
3.  **Personalized Feed Generation:** A protected endpoint (`GET /api/feed`) that generates a reverse-chronological, paginated feed of posts from only the users that the current user follows.
4.  **User Profiles & Discovery:** Provide endpoints to retrieve a user's public profile and a list of their posts (`GET /api/users/<id>`), and a search endpoint (`GET /api/search`) to find users or posts.

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
    # (Import necessary libraries like Flask, CORS, Bcrypt, sqlite3, os, re)

    # 2. App Configuration
    # (Initialize Flask app and extensions)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for auth, posts, users, feed, and interactions)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Feed Optimization:** The `/api/feed` endpoint's database query must be highly optimized, using a subquery or JOIN to efficiently fetch posts.
* **Idempotency:** The follow and like endpoints must be idempotent (e.g., a user cannot like a post twice).
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the feed generation query is performant and that social interactions are idempotent. You may now begin.