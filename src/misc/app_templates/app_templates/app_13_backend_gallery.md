# Goal: Generate a High-Performance & Secure Flask Image Gallery API

This prompt directs the generation of the backend of a full-stack image gallery application. The output must be a complete, production-ready API focused on efficient image processing, storage, and retrieval.

---

### **1. Persona (Role)**

Adopt the persona of a **Backend Engineer** with expertise in digital asset management and media processing pipelines. You specialize in building systems that handle image uploads, extract metadata, and serve optimized content efficiently.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API designed to handle a large volume of image files and their associated metadata.
* **Image Processing:** A key requirement is the on-the-fly generation of thumbnails and the extraction of EXIF metadata from uploaded images.
* **Storage Strategy:** Original images and their generated thumbnails will be stored on the server's filesystem. The database will only store metadata, including file paths.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Decompose the problem by considering:
* The image upload pipeline: receive image -> validate type/size -> save original -> extract EXIF data -> generate and save thumbnail -> record all metadata in the database.
* A clear folder structure for storing originals and thumbnails.
* The logic for extracting key EXIF tags from the raw EXIF data.
* How to manage albums as a separate entity that links to multiple images.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Secure Image Upload & Processing:** A `POST /api/upload` endpoint that handles image uploads, validates file types (MIME type) and size, generates thumbnails using `Pillow`, and extracts key EXIF metadata.
2.  **Image & Album Organization:** Endpoints for creating albums (`POST /api/albums`), listing images and albums (`GET /api/images`, `GET /api/albums`), and associating images with a specific album (`POST /api/albums/<id>/images`).
3.  **Image Retrieval & Serving:** Separate, secure endpoints to serve the full-resolution original image (`GET /api/images/<id>/download`) and its generated thumbnail (`GET /api/images/<id>/thumbnail`).
4.  **User Authentication & Ownership:** A standard system for user registration and login, ensuring that all images and albums are associated with a user and that actions like deletion are restricted to the owner.

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
    # (Import necessary libraries like Flask, CORS, Pillow, python-magic, os, sqlite3, etc.)

    # 2. App Configuration
    # (Initialize Flask app, set UPLOAD_FOLDER and other configurations)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all the required API endpoints here based on the directive for auth, images, and albums)
    
    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Libraries:** Must use `Pillow` for image processing and `python-magic` for MIME type validation.
* **Security:** Must use `werkzeug.utils.secure_filename` to sanitize original filenames. Must save files with a `uuid` to prevent filename conflicts. Use `send_from_directory` for secure file serving.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, `Pillow`, `python-magic`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the image upload pipeline is complete, EXIF data is correctly extracted, and images are served securely. You may now begin.