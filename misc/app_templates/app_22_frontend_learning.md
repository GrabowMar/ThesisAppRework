# Goal: Generate an Interactive & Gamified React Language Learning SPA

This prompt directs the generation of the frontend of a full-stack language learning application. The output must be a complete, responsive, and engaging single-page application (SPA).

---

### **1. Persona (Role)**

Adopt the persona of a **Senior Front-End Developer** who excels at building engaging and interactive educational applications. Your focus is on gamification, clear progress visualization, and creating a motivating user experience.

---

### **2. Context (Additional Information)**

* **Application Architecture:** A React SPA built with Vite, designed to make language learning feel like a game.
* **Backend API Integration:** The frontend will consume all backend endpoints for lessons, vocabulary, quizzes, and progress using relative paths.

---

### **3. Thought Generation & Planning (Internal Monologue)**

Before writing code, plan the implementation. Consider the UI for an interactive lesson, a flashcard system for vocabulary, a multiple-choice quiz interface, and a dashboard to visualize user progress with charts and streaks.

---

### **4. Directive (The Task)**

Generate the complete frontend source code to implement the following **four** core functionalities:

1.  **Interactive Lesson View:** A component that displays lesson content, including text and playing audio files for pronunciation, with a button to mark the lesson as complete.
2.  **Vocabulary Flashcard Trainer:** A flashcard-style interface for practicing vocabulary words retrieved from the Spaced Repetition System. Users can flip cards to see translations and mark if they knew the word or not.
3.  **Quiz & Assessment Interface:** A view that presents a multiple-choice quiz for a lesson, allowing the user to submit their answers and receive an immediate score and feedback.
4.  **Personalized Dashboard:** A main dashboard that shows the user's learning streak, overall progress through their current course, and a chart visualizing their vocabulary mastery over time.

---

### **5. Output Specification (Answer Engineering)**

#### **Deliverables**

Generate the following four files. Do **not** generate a `Dockerfile` or `vite.config.js`.

1.  `package.json`
2.  `index.html`
3.  `src/App.jsx`: A completed version of the skeleton provided below.
4.  `src/App.css`

#### **Code Quality & UX Mandates**

* **`App.jsx` Skeleton:**
    ```javascript
    // 1. Imports
    import React, { useState, useEffect } from 'react';
    import ReactDOM from 'react-dom/client';
    import axios from 'axios';
    import { Line } from 'react-chartjs-2';
    // ... other chart.js imports
    import './App.css';

    // 2. Main App Component
    const App = () => {
      // 1. State Management: Define state for courses, lessons, vocabulary, quiz, progress, etc.
      
      // 2. Lifecycle Hooks: Use useEffect for initial data fetching.
      
      // 3. Event Handlers & API Calls: Define functions for completing lessons, practicing vocabulary, and submitting quizzes.

      // 4. Render Logic: Conditionally render different views (Dashboard, LessonView, VocabularyTrainer, QuizView).
      
      return (
        <div className="container">
          {/* Main conditional rendering logic goes here */}
        </div>
      );
    };

    // 5. Mounting Logic
    const container = document.getElementById('root');
    if (container) {
      const root = ReactDOM.createRoot(container);
      root.render(<App />);
    }

    export default App;
    ```
* **Libraries:** Must use `axios` for API calls and `react-chartjs-2` for progress visualization.
* **`package.json`:** Must include `react`, `react-dom`, `axios`, `chart.js`, and `react-chartjs-2`.
* **Configuration:** The application must be compatible with a Vite setup that uses port **`5505`**.

#### **Final Review (Self-Correction)**

After generating the code, perform a final internal review to ensure the flashcard trainer correctly sends practice results to the backend and that the progress dashboard visualizes data accurately. You may now begin.