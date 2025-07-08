import psycopg2

# PostgreSQL connection config
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'Vasala@#66118'
}

def create_connection():
    return psycopg2.connect(**DB_CONFIG)

def setup_database():
    conn = create_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(100),
            phone VARCHAR(15),
            country VARCHAR(100)
        )
    ''')

    # Create chat_history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            email VARCHAR(100),
            user_query TEXT,
            bot_response TEXT
        )
    ''')

    conn.commit()
    conn.close()

def save_user_info(email, phone, country):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (email, phone, country) VALUES (%s, %s, %s)
    """, (email, phone, country))
    conn.commit()
    conn.close()

def get_user_count():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT email) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def save_interaction(email, user_query, bot_response):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chat_history (email, user_query, bot_response)
        VALUES (%s, %s, %s)
    """, (email, user_query, bot_response))
    conn.commit()
    conn.close()

def user_exists(email, phone):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM users WHERE email = %s AND phone = %s
    """, (email, phone))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists
