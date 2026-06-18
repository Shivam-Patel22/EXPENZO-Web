# EXPENZO 💰

EXPENZO is a premium, responsive personal finance and expense-sharing web application built with **Python** and **Django**. It features dynamic dark-mode analytics charts, custom recurring transaction templates, and multi-user split groups with automatic settlement calculations.

---

## ✨ Features

- **Personal Dashboard:** Log personal expenses, trace monthly trends, and track financial goals.
- **Dynamic Charts:** Circular savings progress gauges and category spending breakdown donut charts dynamically generated in HSL dark-mode using **Matplotlib** and **Seaborn**.
- **Transaction History:** Browse, search, and manage a complete historical record of personal and group expenses.
- **Recurring Transactions:** Automate recurring income and expense items with customizable templates and processing runs.
- **Group Expense Splitting:** Create groups, invite members, log shared bills (equally or custom split), and view automated balances and settlement plans (who owes what to whom).
- **Security:** Built-in Django authentication for secure user registration, log in, and session management.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, Django 6.0
- **Database:** SQLite3
- **Visualization:** Matplotlib, Seaborn
- **Styling:** Custom CSS (Premium dark mode, glassmorphism, responsive grids)

---

## 🚀 Getting Started

### 1. Prerequisites
Make sure you have **Python 3.10+** installed on your system.

### 2. Setup Directory
Open a terminal in the project root directory (`EXPENZO/`).

### 3. Create a Virtual Environment (Recommended)
Create and activate a virtual environment to manage dependencies:
```bash
# Create venv inside the backend folder
python -m venv backend/venv

# Activate on Windows (PowerShell)
.\backend\venv\Scripts\Activate.ps1

# Activate on macOS/Linux
source backend/venv/bin/activate
```

### 4. Install Dependencies
Install all required Python packages:
```bash
pip install -r backend/requirements.txt
```

### 5. Run Database Migrations
Initialize the local SQLite database schema:
```bash
python backend/manage.py migrate
```

### 6. Run the Development Server
Start the local server:
```bash
python backend/manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser. Register a new account to get started!

---

## 📂 Folder Structure

```
EXPENZO/
├── backend/
│   ├── manage.py                 # Django CLI management tool
│   ├── requirements.txt          # Python package requirements
│   ├── db.sqlite3                # SQLite database (Git ignored)
│   ├── config/                   # Root project configuration (settings, root URLs)
│   ├── apps/
│   │   └── expenzo/              # Main application source code
│   │       ├── models.py         # Relational database models
│   │       ├── views.py          # Dashboard controller logic and auth views
│   │       ├── urls.py           # App endpoints and namespaces
│   │       └── charts.py         # Matplotlib spend category chart generators
│   ├── templates/                # Reusable HTML layouts and views
│   └── static/                   # Styling resources (CSS rules)
├── designs/                      # Visual mockup references
└── README.md                     # Project documentation
```
