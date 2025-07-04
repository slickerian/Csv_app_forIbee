from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status, Query, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from dotenv import load_dotenv
import os, csv, io, base64, sqlite3, logging, secrets
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request

templates = Jinja2Templates(directory="templates")

load_dotenv()

app = FastAPI()
security = HTTPBasic()
USERNAME = os.getenv("AUTH_USERNAME")
PASSWORD = os.getenv("AUTH_PASSWORD")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
if not ACCESS_TOKEN:
    raise RuntimeError("ACCESS_TOKEN not found in .env")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database setup
conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

# Logging
logging.basicConfig(filename="activity.log", level=logging.INFO)

def log_request(path: str):
    logging.info(f"Endpoint accessed: {path}")

def get_token(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username == USERNAME and credentials.password == PASSWORD:
        return {"access_token": ACCESS_TOKEN}
    raise HTTPException(status_code=401, detail="Invalid credentials")

def verify_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = auth_header.split(" ")[1]
    if token != ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/", include_in_schema=False)
def root():
    return FileResponse("static/login.html")

@app.post("/token")
def issue_token(credentials: HTTPBasicCredentials = Depends(security)):
    return get_token(credentials)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, _: None = Depends(verify_token)):
    log_request("/dashboard")
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/upload")
def upload_csv(file: UploadFile = File(...), _: None = Depends(verify_token)):
    log_request("/upload")
    content = file.file.read().decode("utf-8")
    reader = csv.reader(io.StringIO(content))

    try:
        headers = next(reader)
    except StopIteration:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    if not headers or any(h.strip() == "" for h in headers):
        raise HTTPException(status_code=400, detail="CSV must contain valid headers")

    rows = []
    for i, row in enumerate(reader, start=2):
        if len(row) != len(headers):
            raise HTTPException(
                status_code=400,
                detail=f"Row {i} has {len(row)} columns, expected {len(headers)}"
            )
        if any(cell.strip() == "" for cell in row):
            raise HTTPException(
                status_code=400,
                detail=f"Row {i} contains missing or empty values"
            )
        rows.append(row)

    cursor.execute("DROP TABLE IF EXISTS data")
    cursor.execute(f"CREATE TABLE data ({', '.join(f'{col} TEXT' for col in headers)})")
    for row in rows:
        cursor.execute(f"INSERT INTO data VALUES ({','.join('?' for _ in row)})", row)
    conn.commit()

    return {"status": "CSV validated and stored successfully"}

@app.get("/data")
def get_data(
    contains: str = Query(None),
    column: str = Query(None),
    value: str = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    _: None = Depends(verify_token)
):
    log_request("/data")
    query = "SELECT * FROM data"
    filters = []
    params = []

    if contains:
        cursor.execute("PRAGMA table_info(data)")
        columns = [col[1] for col in cursor.fetchall()]
        filters = [f"{col} LIKE ?" for col in columns]
        query += f" WHERE {' OR '.join(filters)}"
        params = [f"%{contains}%"] * len(columns)
    elif column and value:
        query += f" WHERE {column} = ?"
        params = [value]

    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    data = cursor.fetchall()
    return {"data": data}

@app.get("/columns")
def get_columns(
    as_string: bool = Query(False),
    contains: str = Query(None),
    _: None = Depends(verify_token)
):
    log_request("/columns")
    cursor.execute("PRAGMA table_info(data)")
    cols = [col[1] for col in cursor.fetchall()]

    if contains:
        cols = [col for col in cols if contains.lower() in col.lower()]

    return {"columns": ", ".join(cols) if as_string else cols}

@app.get("/logs")
def get_logs(tail: int = Query(None), _: None = Depends(verify_token)):
    log_request("/logs")
    if not os.path.exists("activity.log"):
        return {"logs": []}
    with open("activity.log", "r") as f:
        lines = f.readlines()
    if tail:
        lines = lines[-tail:]
    return {"logs": lines}

@app.delete("/delete")
def delete_data(
    columns: str = Query(None),
    column: str = Query(None),
    value: str = Query(None),
    drop_table: bool = Query(False),
    _: None = Depends(verify_token)
):
    log_request("/delete")

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='data'")
    if not cursor.fetchone() and not drop_table:
        raise HTTPException(status_code=404, detail="No data table exists")

    if drop_table:
        cursor.execute("DROP TABLE IF EXISTS data")
        conn.commit()
        return {"status": "Table dropped successfully"}

    if columns:
        column_list = [col.strip() for col in columns.split(",")]
        cursor.execute("PRAGMA table_info(data)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        invalid_columns = [col for col in column_list if col not in existing_columns]
        if invalid_columns:
            raise HTTPException(status_code=400, detail=f"Invalid columns: {', '.join(invalid_columns)}")
        if len(existing_columns) == len(column_list):
            raise HTTPException(status_code=400, detail="Cannot delete all columns")

        remaining_columns = [col for col in existing_columns if col not in column_list]
        cursor.execute(f"CREATE TABLE temp_data ({', '.join(f'{col} TEXT' for col in remaining_columns)})")
        cursor.execute(f"INSERT INTO temp_data SELECT {', '.join(remaining_columns)} FROM data")
        cursor.execute("DROP TABLE data")
        cursor.execute("ALTER TABLE temp_data RENAME TO data")
        conn.commit()
        return {"status": f"Columns {', '.join(column_list)} deleted successfully"}

    if column and value:
        cursor.execute("PRAGMA table_info(data)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        if column not in existing_columns:
            raise HTTPException(status_code=400, detail=f"Invalid column: {column}")

        cursor.execute(f"DELETE FROM data WHERE {column} = ?", (value,))
        conn.commit()
        return {"status": f"Rows where {column} = {value} deleted successfully"}

    raise HTTPException(status_code=400, detail="Must specify columns, column/value pair, or drop_table=True")
