# Goal: Generate a Secure Flask Crypto Wallet API (Mock)

This prompt directs the generation of the backend for a cryptocurrency wallet application. The output must be a complete, production-ready API that **simulates** wallet functionality without connecting to a real blockchain.

---

### **1. Persona (Role)**

Adopt the persona of a **FinTech Backend Engineer** specializing in secure financial applications. Your top priorities are security, data integrity, and creating a logical API for managing financial transactions.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that serves as the backend for a personal crypto wallet.
* **Core Logic:** This is a **simulation**. No real cryptographic keys or blockchain interactions are required. The system should mimic the behavior of a real wallet.
* **Database Schema:** Use SQLite to store users, wallets, addresses, and a ledger of transactions.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider how to simulate transactions: a "send" action should debit one user's balance and credit another's in the database. Plan the generation of fake addresses and the structure for tracking balances for multiple currencies.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Secure Wallet & Address Management:** Endpoints to create wallets for users, and to generate new, unique (but fake) receiving addresses for different cryptocurrencies (e.g., BTC, ETH).
2.  **Balance & Transaction History:** An endpoint to fetch the current balance for each currency in a wallet and a separate endpoint to retrieve a paginated history of all simulated transactions.
3.  **Transaction Processing (Mocked):** A `POST /api/transactions/send` endpoint that simulates sending cryptocurrency. It must validate that the sender has a sufficient balance and then create transaction records for both the sender (debit) and receiver (credit).
4.  **User Authentication & Security:** A standard user login system, with a mock "PIN" check for authorizing sensitive actions like sending transactions.

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
    # (Import necessary libraries like Flask, CORS, sqlite3, os, Bcrypt, Decimal)

    # 2. App Configuration
    # (Initialize Flask app and extensions)

    # 3. Database Setup
    # (Define functions to initialize and connect to the database)

    # 4. Utility and helper functions
    # (Implement necessary code)

    # 5. API Routes
    # (Implement all required routes for auth, wallet, transactions, etc.)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Data Integrity:** Must use Python's `Decimal` type for all currency balances and transaction amounts to avoid floating-point errors.
* **Simulation:** All cryptographic and blockchain operations should be mocked. For example, generating an address can be done by creating a unique random string.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the transaction simulation logic correctly updates balances and that the mock security checks are in place. You may now begin.