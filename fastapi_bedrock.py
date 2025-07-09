from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from db import setup_database, save_user_info, get_user_count, save_interaction, user_exists, create_connection
from bedrock_search import initialize_bedrock_index, get_answer_bedrock, add_pdf_to_bedrock_index, generate_answer_with_bedrock
from bedrock_faiss_indexer import BedrockFAISSIndexer
from datetime import datetime, timedelta
import os
import glob
import shutil
import re
import PyPDF2
import pandas as pd
from pptx import Presentation
from docx import Document
import difflib
import logging
import camelot
from psycopg2 import errors
import boto3
import json
import re
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = FastAPI()

# Allow CORS for all origins (for testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_database()

# In-memory session state (for demo; use a real session store in production)
session_state = {
    "admin_authenticated": False,
    "admin_password_attempts": 0,
    "admin_login_step": None,
    "admin_email_attempt": "",
    "admin_password_attempt": "",
    "show_admin_login": False,
    "bedrock_indexer": None,
    "role": None,
    "last_activity": None,  # Track last activity for session timeout
    "session_id": None,  # Add session ID for better tracking
}

# Session timeout configuration
SESSION_TIMEOUT_MINUTES = 20  # 20 minutes

def list_data_files():
    data_dir = "data"
    files = []
    if os.path.exists(data_dir):
        files = [f for f in os.listdir(data_dir) if f.lower().endswith((".csv", ".pdf"))]
    return files


def trim_by_chars(text, limit):
    text = text.strip()
    if len(text) <= limit:
        return text
    else:
        return text[:limit].rsplit(' ', 1)[0] + '...'

def extract_main_word(filename):
    return os.path.splitext(filename)[0].replace("_", " ").capitalize()

def list_data_files():
    data_dir = "data"
    return [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]

def save_interaction(email, user_query, bot_response):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO chat_history (email, user_query, bot_response, timestamp)
        VALUES (%s, %s, %s, NOW())
        """,
        (email, user_query, bot_response)
    )
    conn.commit()
    conn.close()



def extract_main_word(filename):
    name = os.path.splitext(filename)[0]
    main_word = name.split('_')[0].split(' ')[0]
    return main_word.capitalize()

def trim_to_tokens(text, max_tokens=100):
    tokens = re.findall(r'\b\w+\b', text)
    if len(tokens) <= max_tokens:
        return text
    count = 0
    for match in re.finditer(r'\b\w+\b', text):
        count += 1
        if count == max_tokens:
            end_pos = match.end()
            return text[:end_pos] + '...'
    return text

def is_list_like(text):
    if '\n' in text:
        return True
    if re.search(r'\d+\.', text):
        return True
    if ';' in text:
        return True
    return False

def format_points(text, max_tokens=100):
    points = re.split(r'\n|;|\d+\.', text)
    points = [p.strip() for p in points if p.strip()]
    result = []
    used_tokens = 0
    for p in points:
        p_trimmed = trim_to_tokens(p, max_tokens - used_tokens)
        p_tokens = len(re.findall(r'\b\w+\b', p_trimmed))
        if used_tokens + p_tokens > max_tokens:
            break
        result.append(f'- {p_trimmed}')
        used_tokens += p_tokens
        if used_tokens >= max_tokens:
            break
    return '\n'.join(result)

# Helper: Reprocess all files in data folder and reload index
def reprocess_and_reload_index():
    data_dir = "data"
    index_path = "bedrock_faiss_index"
    indexer = BedrockFAISSIndexer()
    files = os.listdir(data_dir)
    for file in files:
        file_path = os.path.join(data_dir, file)
        if file.lower().endswith(".csv"):
            indexer.process_csv(file_path)
        elif file.lower().endswith(".pdf"):
            indexer.process_pdf(file_path)
    indexer.save_index(index_path)
    return initialize_bedrock_index()

def is_privileged_authenticated():
    if not session_state.get("admin_authenticated"):
        return False
    if session_state.get("role", "").lower() not in ["admin", "sales"]:  # Fixed: use lowercase
        return False
    
    last = session_state.get("last_activity")
    if not last:
        # No last activity recorded, session is invalid
        session_state["admin_authenticated"] = False
        return False
    
    # Check if session has expired
    if (datetime.now() - last > timedelta(minutes=SESSION_TIMEOUT_MINUTES)):
        # Session expired
        session_state["admin_authenticated"] = False
        session_state["role"] = None
        session_state["last_activity"] = None
        session_state["session_id"] = None
        return False
    
    # Session is valid, update last activity (but not on every call to reduce overhead)
    # Only update if more than 5 minutes have passed since last update
    if (datetime.now() - last > timedelta(minutes=20)):
        session_state["last_activity"] = datetime.now()
    
    return True

# --- Admin Endpoints ---
@app.post("/admin/login")
def admin_login(email: str, password: str):
    # Query the sales_persons_data table for this email and password
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, name FROM sales_persons_data WHERE email = %s AND password = %s",
        (email, password)
    )
    result = cursor.fetchone()
    conn.close()

    if not result:
        # No such user or wrong password
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role, name = result
    session_state["admin_authenticated"] = True
    session_state["role"] = role
    session_state["name"] = name  # Store the name
    session_state["email"] = email  # Store the admin's email
    session_state["last_activity"] = datetime.now()

    if role.lower() == "admin":
        return {"success": True, "message": "Admin authenticated!", "role": "admin"}
    elif role.lower() == "sales":
        return {"success": True, "message": "Sales person authenticated!", "role": "sales"}
    else:
        return {"success": True, "message": f"{role} authenticated!", "role": role}

@app.post("/admin/logout")
def admin_logout():
    session_state["admin_authenticated"] = False
    session_state["admin_password_attempts"] = 0
    session_state["admin_login_step"] = None
    session_state["admin_email_attempt"] = ""
    session_state["admin_password_attempt"] = ""
    session_state["show_admin_login"] = False
    session_state["last_activity"] = None
    session_state["role"] = None
    session_state["email"] = None  # Clear the email
    session_state["session_id"] = None
    return {"success": True, "message": "Logged out successfully."}

@app.get("/admin/files")
def get_files():
    if not is_privileged_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"files": list_data_files()}


@app.post("/admin/upload")
def upload_file(file: UploadFile = File(...)):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":  # Fixed: use lowercase
        raise HTTPException(status_code=403, detail="Only admin can upload files.")

    allowed_exts = ('.csv', '.pdf', '.ppt', '.pptx', '.doc', '.docx')
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()

    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Only CSV, PDF, PPT, or Word files are allowed.")

    # Check file size and provide warnings for large files
    file.file.seek(0)
    file_content = file.file.read()
    file_size = len(file_content)
    file_size_mb = file_size / (1024 * 1024)
    
    # Reset file pointer for saving
    file.file.seek(0)

    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]

    if len(files) >= 20:

        raise HTTPException(status_code=400, detail="File upload limit reached. Please delete some files before uploading new ones.")

    # Save all files as-is without any conversion
    file_path = os.path.join(data_dir, filename)
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Provide appropriate message based on file size
    if file_size_mb > 100:
        message = f"File uploaded successfully! Processing may take several hours and consume significant AWS credits. Please be patient."
    elif file_size_mb > 50:
        message = f"File uploaded successfully! "
    elif file_size_mb > 10:
        message = f"File uploaded successfully!  "
    else:
        message = f"File uploaded successfully! "
    
    reprocess_and_reload_index()
    session_state["bedrock_indexer"] = None
    return {"success": True, "message": message}


@app.delete("/admin/delete/{filename}")
def delete_file(filename: str):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":  # Fixed: use lowercase
        raise HTTPException(status_code=403, detail="Only admin can delete files.")

    file_path = os.path.join("data", filename)
    if os.path.exists(file_path):
        os.remove(file_path)

        # Rebuild index ONLY from current files
        reprocess_and_reload_index()

        # Clear in-memory cached index
        session_state["bedrock_indexer"] = None

        return {"success": True, "message": "File deleted and index reloaded successfully"}
    else:
        raise HTTPException(status_code=404, detail="File not found.")



@app.get("/chatusers/list")
def get_userschat_list():
    if not is_privileged_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated.")
    
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            u.email,
            u.phone,
            latest.chat_date,
            latest.chat_time,
            u.status,
            u.description,
            u.updated_by,
            u.updated_at
        FROM users u
        LEFT JOIN (
            SELECT DISTINCT ON (email) email, chat_date, chat_time
            FROM chat_history
            ORDER BY email, chat_date DESC, chat_time DESC
        ) latest ON u.email = latest.email
        ORDER BY latest.chat_date DESC NULLS LAST, latest.chat_time DESC NULLS LAST
    ''')
    
    users = cursor.fetchall()
    conn.close()

    return {
        "users": [
            {
                "email": u[0],
                "phone": u[1],
                "chat_date": datetime.strptime(str(u[2]), "%Y-%m-%d").strftime("%d/%m/%Y") if u[2] else None,
                "chat_time": datetime.strptime(str(u[3]), "%H:%M:%S.%f").strftime("%H:%M") if u[3] else None,
                "status": u[4],
                "description": u[5],
                "updated_by": u[6],
                "updated_at": u[7].isoformat() if u[7] else None
            } for u in users
        ]
    }



@app.get("/users/list")
def get_users_list():
    if not is_privileged_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated.")
    
    conn = create_connection()
    cursor = conn.cursor()

    # Get recent users with extracted date and time (not full timestamp)
    cursor.execute('''
        SELECT DISTINCT ON (u.email)
            u.email,
            
            c.password,
            c.role,
            c.name,
            c.created_at
        FROM sales_persons_data u
        JOIN sales_persons_data c ON u.email = c.email
        ORDER BY u.email, c.id DESC
        LIMIT 100
    ''')
    users = cursor.fetchall()
    conn.close()

    return {
        "users": [
            {
                "email": u[0],
    
                "password": u[1],
                "role": u[2],
                "name": u[3],
                "created_at": u[4]
            } for u in users
        ]
    }



@app.get("/users/history")
def get_user_history(email: str = Query(...)):
    if not is_privileged_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated.")
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_query, bot_response,chat_date,chat_time FROM chat_history
        WHERE email = %s
        ORDER BY id DESC
        LIMIT 100
    """, (email,))
    history = cursor.fetchall()
    conn.close()
    # Return as list of dicts
    return {"history": [{"user_query": h[0], "bot_response": h[1], "chat_date": h[2], "chat_time": h[3]} for h in history]}

# --- User Endpoints ---
@app.post("/user/register")
def user_register(
    email: str = Form(...),
    phone: str = Form(...),
    country: str = Form('India'),
    status: str = Form('pending')
    ):
    if not user_exists(email, phone):
        save_user_info(email, phone, country,status)
    return {"success": True, "message": "User registered."}

# @app.post("/chat")
# def chat(email: str = Form(...), user_query: str = Form(...)):
    import os

    # 1. Handle greetings and small talk
    greetings = {
        "hi": "Hi! How can I assist you today?",
        "Hi there": "Hi! How can I assist you today?",
        "hello": "Hello! How can I help you?",
        "hey": "Hey there! How can I help you?",
        "good morning": "Good morning! How can I assist you today?",
        "how are you": "I'm just a bot, but I'm here to help you! How can I assist you?",
        "who are you": "I'm your assistant bot, here to help you with your queries!",
        "how you help me": "I can answer your questions from uploaded documents. How can I help you today?",
        "okay": "ok! How can I help you? ",
        "ok": "Alright! Let me know how I can help.",
        "hmmha": "Got it! Feel free to ask anything.",
        "thank you": "You're welcome! Let me know if there's anything else I can assist you with.",
        "thankyou": "You're very welcome! Happy to help.",
        "thanks": "You're most welcome! I'm here if you need anything else.",
        "thank u": "You're welcome! Let me know if you need anything more.",
        "thx": "You're welcome!",
        "ty": "You're welcome!"
    }

    normalized_query = user_query.strip().lower()
    if normalized_query in greetings:
        polite_reply = greetings[normalized_query]
        save_interaction(email, user_query, polite_reply)
        return {
            "short_desc": polite_reply,
            "long_desc": None,
            "more_available": False
        }

    # 2. Check if any files exist in the data folder
    data_dir = "data"
    all_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    if not all_files:
        msg = "No files uploaded yet. Please upload documents so I can assist you."
        save_interaction(email, user_query, msg)
        return {
            "short_desc": msg,
            "long_desc": None,
            "more_available": False
        }

    # 3. Rebuild bedrock indexer from current files
    bedrock_indexer = initialize_bedrock_index()
    results = bedrock_indexer.search(user_query, k=3, threshold=0.15)

    if results:
        best_doc, _ = results[0]
        short_ans = best_doc.get('answer') or best_doc.get('text') or ""
        long_ans = best_doc.get('details') or best_doc.get('text') or ""

        # Trim short and long answer
        trimmed_short = format_points(short_ans, 60) if is_list_like(short_ans) else trim_to_tokens(short_ans, 60)
        trimmed_long = trim_to_tokens(long_ans, 200)

        # If long is too similar or empty, regenerate it
        if not trimmed_long or trimmed_long.lower() == trimmed_short.lower():
            context = "\n\n".join([
                doc.get('details') or doc.get('answer') or doc.get('text') or ""
                for doc, _ in results
            ]) or trimmed_short
            try:
                generated_long = generate_answer_with_bedrock(user_query, context)
                trimmed_long = trim_to_tokens(generated_long, 300)
            except:
                trimmed_long = None

        save_interaction(email, user_query, trimmed_short)

        return {
            "short_desc": trimmed_short,
            "long_desc": trimmed_long,
            "more_available": bool(trimmed_long)
        }

    else:
        topics_str = ", ".join([extract_main_word(f) for f in all_files])
        msg = f"Sorry, I couldn't find an answer to that. I have data only on: {topics_str}"
        save_interaction(email, user_query, msg)
        return {
            "short_desc": msg,
            "long_desc": msg,
            "more_available": False
        }


# MAJOR_CITIES = [
#     "bangalore", "chennai", "mumbai", "delhi", "hyderabad", "pune", "kolkata", "ahmedabad", "coimbatore"
# ]
# NIBAV_MAIN_URL = "https://www.nibavlifts.com/contact-us/"

def extract_location_from_query(query):
    """Enhanced location extraction with multiple patterns"""
    query_lower = query.lower()
    
    # Multiple patterns for location extraction
    patterns = [
        r'branches? (in|at|near|around) ([\w\s]+)',
        r'(\w+) (branch|location|office|center|centre)',
        r'(?:in|at|near|around) ([\w\s]+)',
        r'(\w+) (?:branch|location|office|center|centre)',
        r'how many branches? (?:in|at|near|around) ([\w\s]+)',
        r'(\w+) (?:has|have) (?:branch|location|office)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query_lower, re.IGNORECASE)
        if match:
            # Get the location from the appropriate group
            if len(match.groups()) == 2:
                location = match.group(2).strip()
            else:
                location = match.group(1).strip()
            
            # Clean up the location
            location = re.sub(r'\b(branch|location|office|center|centre|in|at|near|around|has|have)\b', '', location, flags=re.IGNORECASE)
            location = location.strip()
            
            if location and len(location) > 1:
                return location
    
    return None

def search_branch_in_data(location, query):
    """
    Search for branch information in uploaded CSV data
    """
    try:
        data_dir = "data"
        if not os.path.exists(data_dir):
            print("Data directory not found")
            return None
            
        csv_files = [f for f in os.listdir(data_dir) if f.lower().endswith('.csv')]
        if not csv_files:
            print("No CSV files found")
            return None
            
        print(f"Found CSV files: {csv_files}")
        
        # Load all branch data
        all_branches = []
        for csv_file in csv_files:
            csv_path = os.path.join(data_dir, csv_file)
            try:
                print(f"Reading CSV: {csv_file}")
                df = pd.read_csv(csv_path)
                print(f"Columns: {df.columns.tolist()}")
                print(f"First row: {df.iloc[0].tolist()}")
                
                if 'city' in df.columns:
                    for _, row in df.iterrows():
                        city = str(row['city']).strip()
                        state = str(row.get('state', '')).strip()
                        address = str(row.get('address', '')).strip()
                        phone = str(row.get('phone', '')).strip()
                        email = str(row.get('email', '')).strip()
                        country = str(row.get('country', '')).strip()
                        
                        if city and city != 'nan':
                            all_branches.append({
                                'country': country,
                                'city': city,
                                'state': state,
                                'address': address,
                                'phone': phone,
                                'email': email
                            })
                else:
                    print(f"No 'city' column found in {csv_file}")
            except Exception as e:
                print(f"Error reading CSV {csv_file}: {e}")
                continue
        
        print(f"Total branches loaded: {len(all_branches)}")
        if all_branches:
            print(f"Sample branch: {all_branches[0]}")
        
        if not all_branches:
            return None
            
        # Search logic
        if location:
            # Search for specific location
            location_lower = location.lower()
            matching_branches = []
            
            for branch in all_branches:
                city_lower = branch['city'].lower()
                state_lower = branch['state'].lower()
                country_lower = branch.get('country', '').lower()
                
                if (
                    (city_lower and location_lower in city_lower) or
                    (state_lower and location_lower in state_lower) or
                    (country_lower and location_lower in country_lower)
                ):
                    matching_branches.append(branch)
            
            if matching_branches:
                if len(matching_branches) == 1:
                    branch = matching_branches[0]
                    return f"Nibav Lifts has a branch in {branch['city']}, {branch['state']}. Address: {branch['address']}. Phone: {branch['phone']}. Email: {branch['email']}."
                else:
                    result = f"Nibav Lifts has {len(matching_branches)} branches in {location.title()}:\n"
                    for i, branch in enumerate(matching_branches, 1):
                        result += f"{i}. {branch['city']}, {branch['state']} - {branch['address']}. Phone: {branch['phone']}\n"
                    return result
            else:
                return (
                    f"It appears there are no Nibav lift branches currently in {location.title()}. "
                    f"The company’s official India website lists Chennai as the primary office and regional hub, with no mention of {location.title()} "
                    f"You can check the official Nibav Lifts website for the latest branch details: https://www.nibavlifts.com"
                )
        else:
            # General branch query - return summary
            states = {}
            for branch in all_branches:
                state = branch['state']
                if state not in states:
                    states[state] = []
                states[state].append(branch['city'])
            
            result = f"Nibav Lifts has branches in {len(states)} states across India:\n"
            for state, cities in states.items():
                result += f"• {state}: {', '.join(cities)}\n"
            result += f"\nTotal: {len(all_branches)} branches"
            return result
            
    except Exception as e:
        print(f"Error searching branch data: {e}")
        return None



@app.post("/chat")
def chat(email: str = Form(...), user_query: str = Form(...)):
    user_query_lower = user_query.lower()

    # Define greetings
    greetings = {
        "hi": "Hi! How can I assist you today?",
        "hello": "Hello! How can I help you?",
        "hey": "Hey there! How can I help you?",
        "good morning": "Good morning! How can I assist you today?",
        "how are you": "I'm just a bot, but I'm here to help you! How can I assist you?",
        "who are you": "I'm your assistant bot, here to help you with your queries!",
        "how you help me": "I can answer your questions from uploaded documents. How can I help you today?",
        "ok": "Ok, how can I help you today?",
        "okay": "Ok, how can I help you today?",
        "thanks": "You're welcome! How can I help you today?",
        "thank you": "You're welcome! Let me know if there's anything else I can assist you with.",
        "thank u": "You're welcome!",
        "thx": "You're welcome!",
        "ty": "You're welcome!"
    }

    normalized_query = user_query.strip().lower()
    if normalized_query in greetings:
        polite_reply = greetings[normalized_query]
        save_interaction(email, user_query, polite_reply)
        return {
            "long_desc": polite_reply,
            "more_available": False
        }

    # --- Handle branch queries ---
    if any(keyword in user_query_lower for keyword in ["branch", "branches", "location", "locations", "office", "offices"]):
        location = extract_location_from_query(user_query)
        branch_info = search_branch_in_data(location, user_query) if location else search_branch_in_data(None, user_query)
        if branch_info:
            save_interaction(email, user_query, branch_info)
            # ✅ Check and trigger summary
            update_summary_if_needed(email)
            return {"long_desc": branch_info, "more_available": False}

    # --- Check if files exist ---
    data_dir = "data"
    all_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    if not all_files:
        msg = "No files available. Please upload documents for me to assist you."
        save_interaction(email, user_query, msg)
        update_summary_if_needed(email)
        return {"short_desc": msg, "long_desc": None, "more_available": False}

    # --- Initialize search index ---
    bedrock_indexer = initialize_bedrock_index()
    results = bedrock_indexer.search(user_query, k=3, threshold=0.15)

    if results:
        best_doc, _ = results[0]
        source_type = best_doc.get('source')

        if source_type == 'csv':
            short_ans = best_doc.get('answer') or best_doc.get('text') or ""
            long_ans = best_doc.get('details') or best_doc.get('text') or ""
            trimmed_short = format_points(short_ans, 60) if is_list_like(short_ans) else trim_to_tokens(short_ans, 60)
            trimmed_long = trim_to_tokens(long_ans, 200)
            if not trimmed_long or trimmed_long.lower() == trimmed_short.lower():
                context = "\n\n".join([
                    doc.get('details') or doc.get('answer') or doc.get('text') or ""
                    for doc, _ in results
                ]) or trimmed_short
                try:
                    generated_long = generate_answer_with_bedrock(user_query, context)
                    trimmed_long = trim_to_tokens(generated_long, 300)
                except:
                    trimmed_long = None
            save_interaction(email, user_query, trimmed_short)
            update_summary_if_needed(email)
            return {"long_desc": trimmed_short + trimmed_long, "more_available": bool(trimmed_long)}

        else:
            seen = set()
            context_chunks = []
            for doc, _ in results:
                txt = doc.get('text', '')
                if txt not in seen and len(context_chunks) < 3:
                    context_chunks.append(txt)
                    seen.add(txt)
            context = "\n\n".join(context_chunks)
            short_ans = context_chunks[0] if context_chunks else ""
            trimmed_short = format_points(short_ans, 60) if is_list_like(short_ans) else trim_to_tokens(short_ans, 60)
            trimmed_long = trim_to_tokens(context, 200)
            if not trimmed_long or trimmed_long.lower() == trimmed_short.lower():
                try:
                    generated_long = generate_answer_with_bedrock(user_query, context)
                    trimmed_long = trim_to_tokens(generated_long, 300)
                except:
                    trimmed_long = None
            save_interaction(email, user_query, trimmed_short)
            update_summary_if_needed(email)
            return {"long_desc": trimmed_long, "more_available": bool(trimmed_long)}

    else:
        msg = "Sorry, I couldn't find an answer to that."
        save_interaction(email, user_query, msg)
        update_summary_if_needed(email)
        return {"long_desc": msg, "more_available": False}





def update_summary_if_needed(email):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chat_history WHERE email = %s", (email,))
        count = cursor.fetchone()[0]
        conn.close()

        if count >= 2:
            print(f"Triggering summary for {email}...")
            generate_summary_internal(email)
    except Exception as e:
        print(f"Summary update error: {e}")



@app.get("/user/count")
def user_count():
    return {"count": get_user_count()} 




# New API: Chat analytics (total chats per day, week, month)
@app.get("/analytics/chat_counts")
def chat_counts():
    try:
        conn = create_connection()
        cursor = conn.cursor()

        # Total chats per day
        cursor.execute("""
            SELECT chat_date, COUNT(*) as total_chats
            FROM chat_history
            GROUP BY chat_date
            ORDER BY chat_date DESC
            LIMIT 30
        """)
        daily = cursor.fetchall()

        # Last 7 days aggregation (rolling week)
        today = datetime.now().date()
        seven_days_ago = today - timedelta(days=6)
        
        # Get chats for each day in the last 7 days
        cursor.execute("""
            SELECT chat_date, COUNT(*) as total_chats
            FROM chat_history
            WHERE chat_date >= %s AND chat_date <= %s
            GROUP BY chat_date
            ORDER BY chat_date DESC
        """, (seven_days_ago, today))
        
        daily_chats = cursor.fetchall()
        
        # Create a complete 7-day list with 0 for days with no chats
        total_chats_7_days = 0
        for i in range(7):
            current_date = today - timedelta(days=i)
            current_date_str = current_date.strftime('%Y-%m-%d')
            # Find if this date has chat data
            chat_count = 0
            for row in daily_chats:
                if str(row[0]) == current_date_str:
                    chat_count = row[1]
                    break
            total_chats_7_days += chat_count
        # Format date range as dd/mm/yyyy-dd/mm/yyyy
        date_range = f"{seven_days_ago.strftime('%d/%m/%Y')}-{today.strftime('%d/%m/%Y')}"
        weekly = {
            "date_range": date_range,
            "total_chats": total_chats_7_days
        }

        # Monthly aggregation
        try:
            cursor.execute("""
                SELECT DATE_TRUNC('month', chat_date) as month_start, COUNT(*) as total_chats
                FROM chat_history
                GROUP BY month_start
                ORDER BY month_start DESC
                LIMIT 12
            """)
            monthly_raw = cursor.fetchall()
            monthly = []
            for row in monthly_raw:
                month_start = row[0]
                if isinstance(month_start, str):
                    month_start_dt = datetime.strptime(month_start, "%Y-%m-%d")
                else:
                    month_start_dt = month_start
                # Calculate last day of the month
                if month_start_dt.month == 12:
                    next_month = month_start_dt.replace(year=month_start_dt.year+1, month=1, day=1)
                else:
                    next_month = month_start_dt.replace(month=month_start_dt.month+1, day=1)
                month_end_dt = next_month - timedelta(days=1)
                month_range = f"{month_start_dt.strftime('%d-%m-%Y')} -- {month_end_dt.strftime('%d-%m-%Y')}"
                monthly.append({"month_range": month_range, "total_chats": row[1]})
        except Exception:
            # Fallback for SQLite
            cursor.execute("""
                SELECT strftime('%Y-%m', chat_date) as month_start, COUNT(*) as total_chats
                FROM chat_history
                GROUP BY month_start
                ORDER BY month_start DESC
                LIMIT 12
            """)
            monthly_raw = cursor.fetchall()
            monthly = []
            for row in monthly_raw:
                year, month = row[0].split('-')
                month_start_dt = datetime.strptime(f'{year}-{month}-01', "%Y-%m-%d")
                if int(month) == 12:
                    next_month = month_start_dt.replace(year=month_start_dt.year+1, month=1, day=1)
                else:
                    next_month = month_start_dt.replace(month=month_start_dt.month+1, day=1)
                month_end_dt = next_month - timedelta(days=1)
                month_range = f"{month_start_dt.strftime('%d-%m-%Y')} -- {month_end_dt.strftime('%d-%m-%Y')}"
                monthly.append({"month_range": month_range, "total_chats": row[1]})

        conn.close()

        return {
            "daily": [{"date": str(row[0]), "total_chats": row[1]} for row in daily],
            "weekly": weekly,
            "monthly": monthly,
        }
    except Exception as e:
        print("Analytics error:", e)
        return {"error": str(e)} 

@app.post("/user/create")
def create_sales_person(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...)
):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() not in ["admin", "sales"]:
        raise HTTPException(status_code=403, detail="Only admin or sales can create sales persons.")
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO sales_persons_data (name, email, password, role) VALUES (%s, %s, %s, %s)",
            (name, email, password, role)
        )
        conn.commit()
        return {"success": True, "message": f"Sales person '{email}' created successfully."}
    except Exception as e:
        conn.rollback()
        if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
            return {"success": False, "message": "Email already exists. Please use a different email."}
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        conn.close()
@app.put("/user/update")
def update_sales_person(
    name: str = Form(None),
    email: str = Form(...),
    password: str = Form(None),
    role: str = Form(None)
):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() not in ["admin", "sales"]:
        raise HTTPException(status_code=403, detail="Only admin or sales can update sales persons.")
    conn = create_connection()
    cursor = conn.cursor()
    try:
        # Build dynamic update query
        fields = []
        values = []
        if name is not None:
            fields.append("name = %s")
            values.append(name)
        if password is not None:
            fields.append("password = %s")
            values.append(password)
        if role is not None:
            fields.append("role = %s")
            values.append(role)
        if not fields:
            return {"success": False, "message": "No fields to update."}
        values.append(email)
        query = f"UPDATE sales_persons_data SET {', '.join(fields)} WHERE email = %s"
        cursor.execute(query, tuple(values))
        if cursor.rowcount == 0:
            return {"success": False, "message": f"No sales person found with email '{email}'."}
        conn.commit()
        return {"success": True, "message": f"Sales person '{email}' updated successfully."}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        conn.close()

@app.delete("/user/delete")
def delete_sales_person(email: str = Form(...)):
    if not is_privileged_authenticated() or session_state.get("role", "").lower() not in ["admin", "sales"]:
        raise HTTPException(status_code=403, detail="Only admin or sales can delete sales persons.")
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM sales_persons_data WHERE email = %s",
            (email,)
        )
        if cursor.rowcount == 0:
            return {"success": False, "message": f"No sales person found with email '{email}'."}
        conn.commit()
        return {"success": True, "message": f"Sales person '{email}' deleted successfully."}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        conn.close() 
@app.get("/admin/top-questions")
def get_top_questions():
    if not is_privileged_authenticated():  # Allow both admin and sales to view
        raise HTTPException(status_code=401, detail="Not authenticated.")
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT user_query, COUNT(*) as count
            FROM chat_history
            GROUP BY user_query
            ORDER BY count DESC
            LIMIT 15
        """)
        results = cursor.fetchall()
        return {
            "top_questions": [
                {"question": row[0], "count": row[1]}
                for row in results
            ]
        }
    finally:
        conn.close()

@app.get("/admin/session-status")
def get_session_status():
    """Check current session status for debugging"""
    if not session_state.get("admin_authenticated"):
        return {
            "authenticated": False,
            "message": "Not authenticated",
            "last_activity": None,
            "session_id": None
        }
    
    last_activity = session_state.get("last_activity")
    if last_activity:
        time_remaining = SESSION_TIMEOUT_MINUTES - ((datetime.now() - last_activity).total_seconds() / 60)
        return {
            "authenticated": True,
            "role": session_state.get("role"),
            "email": session_state.get("email"),  # Include email in session status
            "session_id": session_state.get("session_id"),
            "last_activity": last_activity.isoformat(),
            "time_remaining_minutes": round(max(0, time_remaining), 1),
            "session_timeout_minutes": SESSION_TIMEOUT_MINUTES
        }
    else:
        return {
            "authenticated": False,
            "message": "Session has no last activity",
            "last_activity": None,
            "session_id": None
        }
@app.post("/admin/estimate-memory")
def estimate_pdf_memory(file: UploadFile = File(...)):
    """Estimate memory usage for processing a PDF file"""
    if not is_privileged_authenticated() or session_state.get("role", "").lower() != "admin":  # Fixed: use lowercase
        raise HTTPException(status_code=403, detail="Only admin can estimate memory usage.")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for memory estimation.")

    try:
        # Save file temporarily
        temp_path = f"temp_{file.filename}"
        file.file.seek(0)
        with open(temp_path, "wb") as f:
            f.write(file.file.read())
        
        # Estimate memory usage
        indexer = BedrockFAISSIndexer()
        estimate = indexer.estimate_memory_usage(temp_path)
        
        # Clean up temp file
        os.remove(temp_path)
        
        return estimate
    except Exception as e:
        # Clean up temp file if it exists
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Error estimating memory: {str(e)}")


@app.put("/Chatuser/update")
def update_user_and_get_history(
    email: str = Form(...),
    status: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    # Extract user identity from session
    name = session_state.get("name", "unknown")
    role = session_state.get("role", "unknown").lower()
    updated_by = f"{role} ({name})"

    # Authorization check (only allow admin or sales to update)
    if not is_privileged_authenticated() or role not in ["admin", "sales"]:
        raise HTTPException(status_code=403, detail="Only admin or sales can update user status and description.")
    
    # Perform update and track
    from db import update_user_with_tracking, get_user_update_history
    update_result = update_user_with_tracking(
        email=email,
        status=status,
        description=description,
        updated_by_email=updated_by
    )

    # Get update history
    update_history = get_user_update_history(email)

    # Response
    return {
        "success": True,
        "message": "User updated successfully",
        "updated_by": updated_by,
        "email": email,
        "update_result": update_result,
        "update_history": update_history
    }

def generate_summary_internal(email):
    # Step 1: Fetch user's chat history
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_query FROM chat_history WHERE email = %s", (email,))
    chat_rows = cursor.fetchall()
    conn.close()

    if not chat_rows:
        return None

    # Step 2: Combine chat queries into a single text blob
    chat_text = " ".join([row[0] for row in chat_rows]).lower()

    # Step 3: Simple rule-based tagging (can replace with LLM later)
    if any(word in chat_text for word in ["price", "cost", "buy", "purchase", "quotation", "quote"]):
        summary = "User appears to be interested in purchasing a lift."
    elif any(word in chat_text for word in ["problem", "issue", "repair", "not working", "support"]):
        summary = "User is mostly making support-related queries."
    elif any(word in chat_text for word in ["branch", "location", "city", "state", "office"]):
        summary = "User is enquiring about branches and locations."
    else:
        summary = "User is asking general questions."

    # Step 4: Update the users table
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET summary = %s WHERE email = %s", (summary, email))
    conn.commit()
    conn.close()

    return {"email": email, "summary": summary}

