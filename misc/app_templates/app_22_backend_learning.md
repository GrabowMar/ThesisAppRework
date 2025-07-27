# Goal: Generate an Adaptive Flask Language Learning API

This prompt directs the generation of the backend of a full-stack language learning application. The output must be a complete, production-ready API featuring adaptive learning logic.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Backend Engineer** specializing in educational technology. Your expertise is in designing systems that support personalized learning paths, spaced repetition, and progress tracking.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that serves structured educational content.
* **Core Logic:** The system's intelligence lies in its Spaced Repetition System (SRS) for vocabulary review. It must calculate the next review date for a vocabulary item based on user performance.
* **Database Schema:** Use SQLite with tables for `Users`, `Courses`, `Lessons`, `Vocabulary`, and a `User_Vocabulary` table to track SRS data per user.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Decompose the task by considering:
* The structure of lessons and how they relate to courses.
* The Spaced Repetition System (SRS) algorithm: when a user practices a word, update its `familiarity_level` and calculate the `next_review` date.
* The logic for quizzes, which should test the user on the content of a specific lesson.
* A basic authentication system to track progress for individual users.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Course & Lesson Management:** Implement endpoints to list available language courses and to retrieve the individual lessons (containing text and audio references) for a specific course.
2.  **Vocabulary Training with Spaced Repetition:** An endpoint to retrieve vocabulary words due for review based on a Spaced Repetition System (SRS) algorithm. Also, an endpoint to record the result of a user's practice session on a word, which updates its review schedule.
3.  **Grammar Exercises & Quizzes:** Provide endpoints to retrieve grammar exercises and a system to submit answers for a lesson-specific quiz, which are then scored by the backend.
4.  **User Progress Tracking:** A standard user authentication system and an endpoint to retrieve a user's progress, including completed lessons and vocabulary mastery levels.

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
    # (Import necessary libraries like Flask, CORS, sqlite3, os, Bcrypt, datetime)

    # 2. App Configuration
    # (Initialize Flask app and extensions)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for auth, courses, lessons, vocabulary, and quizzes)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Spaced Repetition Logic:** The logic for updating the `next_review` date should be based on the user's answer (correct/incorrect) and the current familiarity level of the word. A simple algorithm is sufficient (e.g., doubling the interval for a correct answer).
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the Spaced Repetition System logic correctly updates review dates and that lesson progress is tracked accurately. You may now begin.