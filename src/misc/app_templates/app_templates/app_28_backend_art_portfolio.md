# Goal: Generate a Flask API for an Artist's Portfolio

This prompt directs the generation of the backend for a full-stack art portfolio application. The output must be a complete, production-ready API focused on high-quality image handling and gallery curation.

---

### **1. Persona (Role)**

Adopt the persona of a **Backend Engineer** with expertise in digital asset management and building platforms for creative professionals. You specialize in image processing pipelines and content management.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API designed to manage and serve a large collection of high-resolution images and their associated metadata.
* **Image Processing:** A key requirement is the on-the-fly generation of thumbnails for fast gallery loading.
* **Database Schema:** Use SQLite to store metadata for artworks, galleries, and artist profiles.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the image upload pipeline: validate, save original, generate and save thumbnail, and record metadata. Plan the relationship between artworks and galleries.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Artwork Upload & Processing:** A `POST /api/artworks/upload` endpoint that handles image uploads, validates that they are images, generates a high-quality thumbnail using `Pillow`, and stores the artwork with its metadata.
2.  **Gallery Curation:** Full CRUD endpoints for creating and managing galleries (`/api/galleries`). Include an endpoint to add/remove artworks from a specific gallery.
3.  **Portfolio & Artwork Retrieval:** Endpoints to retrieve all data needed for a public portfolio, including the artist's profile (`GET /api/artists/<id>`), a list of their galleries, and the artworks within each.
4.  **User Authentication & Ownership:** A standard user auth system to allow an artist to log in and manage their own portfolio (artworks and galleries).

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
    # (Import necessary libraries like Flask, CORS, Pillow, sqlite3, os, Bcrypt)

    # 2. App Configuration
    # (Initialize Flask app, set UPLOAD_FOLDER, etc.)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for auth, artworks, and galleries)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Libraries:** Must use `Pillow` for image processing.
* **Security:** Use `send_from_directory` for secure file serving.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, `Flask-Bcrypt`, and `Pillow`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the image upload pipeline correctly generates thumbnails and that gallery/artwork relationships are handled correctly. You may now begin.