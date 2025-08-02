CSV Dashboard API (FastAPI)
===========================

This is a secure, token-protected web dashboard for uploading, validating, analyzing, and querying CSV files. It uses FastAPI, SQLite, and a simple HTML+JS frontend. Auth is handled via a token system for added security.

Features
--------
- Token-based login (via .env)
- Upload and validate CSVs
- Query, filter, and preview data
- Delete rows or columns
- View logs

Requirements
------------
Install the requirements.txt file: pip install -r requirements.txt

Setup Instructions
------------------

1. Clone the Repo
   git clone https://github.com/slickerian/Csv_app_forIbee.git
   cd Csv_app_forIbee

2. Create a Virtual Environment
   python -m venv venv
   source venv/bin/activate   # Linux/macOS
   venv\\Scripts\\activate      # Windows

3. Install Dependencies
   pip install -r requirements.txt

   If requirements.txt doesn’t exist, use:
   pip install fastapi uvicorn python-dotenv pandas

4. Create `.env` File
   Create a file named `.env` in the root with:
   AUTH_USERNAME=admin
   AUTH_PASSWORD=yourpassword
   ACCESS_TOKEN=your_secure_token

Run the App
-----------
uvicorn main:app --reload

Then open in browser:
http://127.0.0.1:8000/

How to Login
------------
1. Go to `/` → Login page.
2. Use the username & password from your `.env` file.
3. You'll be redirected to the dashboard.
4. All requests from the dashboard include your token in headers.

Features & Usage
----------------

| Feature           | Route         | Notes                          |
|------------------|---------------|--------------------------------|
| Login            | /token        | POST with Basic Auth           |
| Upload CSV       | /upload       | Validates headers and rows     |
| View Data        | /data         | Supports filtering and paging  |
| View Columns     | /columns      | Lists column names             |
| Delete Data/Cols | /delete       | Supports selective deletes     |
| Logs             | /logs         | Shows API activity logs        |

All routes require:
Authorization: Bearer YOUR_TOKEN

Testing API with curl
---------------------
# Get token
curl -u admin:yourpassword http://127.0.0.1:8000/token

# Upload CSV
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" -F "file=@your.csv" http://127.0.0.1:8000/upload

Security Notes
--------------
- Token stored in .env
- Protected routes use Bearer token
- CSV loaded into in-memory SQLite
- Logs saved to activity.log

To-Do / Optional
----------------
- Add AI assistant
- Add CSV export
- Add file history
- Dockerize

Author
------
Built by slickerian
