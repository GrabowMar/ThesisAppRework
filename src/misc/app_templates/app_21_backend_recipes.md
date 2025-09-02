# Goal: Generate a Feature-Rich Flask Recipe Management API

This prompt directs the generation of the backend for a full-stack recipe and meal planning application. The output must be a complete, production-ready API.

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Backend Engineer** specializing in consumer-facing applications for the food and culinary industry. You are an expert in data modeling for complex, related entities like recipes, ingredients, and meal plans.

---

### **2. Context (Additional Information)**

* **System Architecture:** A containerized API that serves as the data backbone for a recipe discovery and meal planning tool.
* **Core Logic:** The system must be able to calculate nutritional information based on ingredients and generate a consolidated shopping list from a user's meal plan.
* **Database Schema:** Use SQLite with tables for `Recipes`, `Ingredients`, and `Meal_Plans`.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the data relationships between recipes and ingredients. Plan the logic for generating a shopping list by aggregating all ingredients from a selection of recipes.

---

### **4. Directive (The Task)**

Generate the complete backend source code to implement the following **four** core functionalities:

1.  **Recipe & Ingredient Management:** Implement full CRUD endpoints for recipes (including ingredients and instructions) and a searchable database of ingredients with their nutritional data.
2.  **Meal Planning & Shopping List:** Create endpoints to allow users to build a weekly or monthly meal plan by assigning recipes to specific dates. Include an endpoint to automatically generate a consolidated shopping list from a given meal plan.
3.  **Nutrition Calculation:** A system that automatically calculates and provides estimated nutritional information (calories, macros) for any given recipe based on its list of ingredients and their quantities.
4.  **User Authentication & Interaction:** A standard user authentication system to allow users to save their own recipes and meal plans, plus endpoints for users to rate and review recipes created by others.

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
    # (Implement all required routes for auth, recipes, ingredients, meal plans, and shopping lists)

    # 6. Main execution
    if __name__ == "__main__":
        # (Initialize DB and run the app on host '0.0.0.0' and port 5005)
        pass
    ```
* **Logic:** The shopping list endpoint must correctly aggregate ingredient quantities from multiple recipes. The nutrition endpoint must sum the nutritional values from all ingredients in a recipe.
* **`requirements.txt`:** Must contain `Flask`, `Flask-CORS`, and `Flask-Bcrypt`.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the nutrition calculation and shopping list aggregation logic are correct and handle various units and quantities properly. You may now begin.