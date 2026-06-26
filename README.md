# EXPENZO 💰

EXPENZO is a premium, responsive personal finance and expense-sharing web application built with **Python**, **Django**, and **Vanilla JS**. It features dynamic dark-mode analytics charts, custom recurring transaction templates, and multi-user split groups with automatic settlement calculations.

---

## ✨ Features

- **Personal Dashboard:** Log personal expenses, trace monthly trends, and track financial goals.
- **Dynamic Charts:** Circular savings progress gauges and category spending breakdown donut charts dynamically generated in HSL dark-mode using **Matplotlib** and **Seaborn**.
- **Transaction History:** Browse, search, and manage a complete historical record of personal and group expenses.
- **Recurring Transactions:** Automate recurring income and expense items with customizable templates and processing runs.
- **Group Expense Splitting:** Create groups, invite members, log shared bills (equally or custom split), and view automated balances and settlement plans (who owes what to whom).
- **Custom Group Icons:** Upload and crop custom group cover photos directly from the UI, compressed via client-side Canvas APIs into Base64 format.
- **Premium Custom UI:** Fully custom dark glassmorphism UI, including a bespoke Vanilla JS date picker built from scratch without any external Javascript libraries.
- **Security & Deployment:** Built-in Django authentication, optimized static file delivery via **Whitenoise**, and production-ready database configuration using `dj-database-url` (PostgreSQL supported).

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, Django 6.0
- **Database:** SQLite3 (Local) / PostgreSQL (Production)
- **Visualization:** Matplotlib, Seaborn
- **Static Assets:** Whitenoise (`CompressedManifestStaticFilesStorage`)
- **Frontend/Styling:** Custom CSS (Premium dark mode, glassmorphism), Vanilla ES6 JavaScript (No external UI libraries)

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
Install all required Python packages (including `gunicorn`, `whitenoise`, and `dj-database-url` for deployment):
```bash
pip install -r backend/requirements.txt
```

### 5. Collect Static Files & Run Migrations
Package the static assets and initialize the local SQLite database schema:
```bash
python backend/manage.py collectstatic --noinput
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
│   ├── config/                   # Root project configuration (settings, root URLs, whitenoise config)
│   ├── apps/
│   │   └── expenzo/              # Main application source code
│   │       ├── models.py         # Relational database models
│   │       ├── views.py          # Dashboard controller logic and auth views
│   │       ├── urls.py           # App endpoints and namespaces
│   │       └── charts.py         # Matplotlib spend category chart generators
│   ├── templates/                # Reusable HTML layouts and views
│   ├── static/                   # Styling resources (CSS rules)
│   │   ├── css/                  # Global styles, glassmorphism UI
│   │   └── js/                   # Vanilla JS components (Custom Calendar, Image Crop)
│   └── staticfiles/              # Collected static files for production delivery
├── designs/                      # Visual mockup references
└── README.md                     # Project documentation
```
Built with ❤️ by Shivam
