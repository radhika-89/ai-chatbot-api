"""
AI Chatbot API using Claude and FastAPI
Store conversations in MySQL database
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import anthropic
import mysql.connector
from mysql.connector import Error
import os

app = FastAPI(
    title="AI Chatbot API",
    description="Intelligent chatbot powered by Claude AI",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Configuration
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "your_password",  # Change this
    "database": "chatbot_db"
}

# Pydantic Models
class Message(BaseModel):
    user_id: str
    message: str

class ChatResponse(BaseModel):
    user_id: str
    user_message: str
    bot_response: str
    timestamp: str

# Initialize Database
def init_database():
    """Create database and tables if they don't exist"""
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"]
        )
        cursor = conn.cursor()

        # Create database
        cursor.execute("CREATE DATABASE IF NOT EXISTS chatbot_db")
        cursor.execute("USE chatbot_db")

        # Create conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255),
                user_message TEXT,
                bot_response TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(255) PRIMARY KEY,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Database initialized successfully")
    except Error as e:
        print(f"❌ Database initialization error: {e}")

# Initialize Claude client
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

@app.get("/")
def read_root():
    return {
        "message": "Welcome to AI Chatbot API",
        "endpoints": {
            "POST /chat": "Send a message and get Claude's response",
            "GET /history/{user_id}": "Get chat history for a user"
        }
    }

@app.post("/chat", response_model=ChatResponse)
def chat(message: Message):
    """
    Send a message and get Claude AI response
    """
    try:
        # Get Claude's response
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[
                {"role": "user", "content": message.message}
            ]
        )

        bot_response = response.content[0].text
        timestamp = datetime.now().isoformat()

        # Store in database
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()

            # Ensure user exists
            cursor.execute("INSERT IGNORE INTO users (user_id) VALUES (%s)", (message.user_id,))

            # Store conversation
            cursor.execute(
                "INSERT INTO conversations (user_id, user_message, bot_response) VALUES (%s, %s, %s)",
                (message.user_id, message.message, bot_response)
            )

            conn.commit()
            cursor.close()
            conn.close()
        except Error as e:
            print(f"Database error: {e}")

        return ChatResponse(
            user_id=message.user_id,
            user_message=message.message,
            bot_response=bot_response,
            timestamp=timestamp
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{user_id}")
def get_history(user_id: str, limit: int = 10):
    """
    Get chat history for a specific user
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT user_message, bot_response, timestamp FROM conversations WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s",
            (user_id, limit)
        )

        history = cursor.fetchall()
        cursor.close()
        conn.close()

        return {"user_id": user_id, "conversation_count": len(history), "conversations": history}

    except Error as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
def get_stats():
    """
    Get chatbot statistics
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_messages = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return {
            "total_messages": total_messages,
            "total_users": total_users,
            "average_messages_per_user": round(total_messages / max(total_users, 1), 2)
        }

    except Error as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    init_database()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
