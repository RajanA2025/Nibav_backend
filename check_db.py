import sqlite3

def check_database():
    conn = sqlite3.connect('chatbot.db')
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables in database:", tables)
    
    # Check users table
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    print(f"Users count: {user_count}")
    
    # Check chat_history table
    cursor.execute("SELECT COUNT(*) FROM chat_history")
    chat_count = cursor.fetchone()[0]
    print(f"Chat history count: {chat_count}")
    
    # Show sample data
    if user_count > 0:
        cursor.execute("SELECT * FROM users LIMIT 3")
        users = cursor.fetchall()
        print(f"Sample users: {users}")
    
    if chat_count > 0:
        cursor.execute("SELECT * FROM chat_history LIMIT 3")
        chats = cursor.fetchall()
        print(f"Sample chat history: {chats}")
    
    conn.close()

if __name__ == "__main__":
    check_database() 