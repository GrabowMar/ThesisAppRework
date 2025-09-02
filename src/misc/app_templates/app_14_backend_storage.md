# Goal: Generate a Secure & High-Performance Flask File-Handling API

This prompt directs the generation of the backend of a full-stack file uploading and management application. The output must be a complete, secure, and efficient API for handling file storage.

---

### **1. Persona (Role)**

Adopt the persona of a **Backend Engineer specializing in Cloud Storage and Media Processing**. Your expertise is in creating secure, high-throughput pipelines for file uploads, ensuring data integrity, and managing storage efficiently.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API designed to handle large files and multiple concurrent uploads.
* **Security:** All uploaded files must be treated as untrusted. Validation of file type and size is a critical security requirement.
* **Storage Strategy:** Files will be stored on the server's filesystem in a dedicated, non-web-accessible directory. The database will only store file metadata.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Decompose the problem by considering: the file upload pipeline (receive, validate, generate secure name, save, record metadata), a strategy for generating file checksums, how to securely serve files for download, and thumbnail generation logic.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Secure File Upload & Processing:** A `POST /api/upload` endpoint that handles file uploads, performs security validation (MIME type using `python-magic`, file size), generates a unique stored filename, and creates image thumbnails using `Pillow`.
2.  **File & Folder Management:** Endpoints to list files and folders (`GET /api/files`) and to create new folders (`POST /api/folders`), establishing a basic organizational hierarchy.
3.  **File Retrieval & Previewing:** Two separate endpoints to securely download the original file (`GET /api/files/<id>/download`) and to serve its generated preview/thumbnail (`GET /api/files/<id>/preview`).
4.  **File Deletion:** An endpoint (`DELETE /api/files/<id>`) to securely delete a file from storage and its associated metadata from the database.

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
    # (Initialize Flask app, set UPLOAD_FOLDER and MAX_CONTENT_LENGTH)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all the required API endpoints here based on the directive)
    
    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Libraries:** Must use `Pillow` for image processing and `python-magic` for MIME type validation.
* **Security:** Must use `werkzeug.utils.secure_filename` to sanitize original filenames. Must save files with a `uuid` to prevent filename conflicts. Use `send_from_directory` for secure file serving.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, `Pillow`, and `python-magic`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure all security measures are correctly implemented and that the file upload pipeline is robust. You may now begin.