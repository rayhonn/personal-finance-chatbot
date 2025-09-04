import streamlit as st
import hashlib
import json
import re
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sqlite3
import os
from datetime import datetime, timedelta
import random
import difflib  

# Set page configuration
st.set_page_config(page_title="Personal Finance Chatbot", page_icon="📊")

# Add custom CSS for better button styling
st.markdown("""
<style>
    .stButton > button {
        height: 60px;
        font-size: 16px;
        font-weight: bold;
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        border-color: #4CAF50;
        color: #4CAF50;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------- Create folders to store data -------------------------------
DATA_DIR = Path("finance_data")  # Create a folder path
DATA_DIR.mkdir(exist_ok=True)    # Make the folder if it doesn't exist
USER_DB_FILE = DATA_DIR / "users.json"  # This is where we'll store user info
DB_PATH = DATA_DIR / "finance.db"  # SQLite database for expenses

# Initialize user database if it doesn't exist
if not USER_DB_FILE.exists():
    with open(USER_DB_FILE, 'w') as f:
        json.dump({}, f, indent=4)

# -------------------------- NLTK Imports --------------------------
# Try to import NLTK components
try:
    import nltk
    from nltk.stem import WordNetLemmatizer
    nltk_available = True
except ImportError:
    nltk_available = False

# Initialize NLTK resources if available
if nltk_available:
    @st.cache_resource
    def download_nltk_resources():
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            with st.spinner("Downloading word tokenizer..."):
                nltk.download('punkt', quiet=True)
        
        try:
            nltk.data.find('corpora/wordnet')
        except LookupError:
            with st.spinner("Downloading word database..."):
                nltk.download('wordnet', quiet=True)
        
        return True

    # Download resources if needed
    if 'nltk_resources_downloaded' not in st.session_state:
        download_nltk_resources()
        st.session_state.nltk_resources_downloaded = True

    # Initialize the lemmatizer
    lemmatizer = WordNetLemmatizer()
else:
    lemmatizer = None

# Function to lemmatize words with fallback
def lemmatize_word(word):
    if nltk_available and lemmatizer:
        try:
            return lemmatizer.lemmatize(word.lower())
        except:
            return word.lower()
    else:
        return word.lower()

# Function to tokenize with fallback
def tokenize_text(text):
    if nltk_available and nltk:
        try:
            return nltk.word_tokenize(text)
        except:
            return text.split()
    else:
        return text.split()
    
# Clean up sentence using available tools
def clean_up_sentence(sentence):
    # Tokenize the pattern - split words into array
    sentence_words = tokenize_text(sentence)
    # Lemmatize each word - create short form for word
    sentence_words = [lemmatize_word(word) for word in sentence_words]
    return sentence_words

# Initialize session state variables (do this early in the code)
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_daily_prompt" not in st.session_state:
    st.session_state.last_daily_prompt = None
if "show_password_error" not in st.session_state:
    st.session_state.show_password_error = None
if "signup_success" not in st.session_state:
    st.session_state.signup_success = False
if "signup_email" not in st.session_state:
    st.session_state.signup_email = ""
if "pending_expense" not in st.session_state:
    st.session_state.pending_expense = None
if "correction_stage" not in st.session_state:
    st.session_state.correction_stage = None
if "custom_categories" not in st.session_state:
    st.session_state.custom_categories = []
if "debug_info" not in st.session_state:
    st.session_state.debug_info = ""
if "pending_multiple_expenses" not in st.session_state:
    st.session_state.pending_multiple_expenses = None

# ---------------------------- Database Functions ----------------------------
# Initialize SQLite database
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create expenses table
    c.execute('''
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY,
        user_email TEXT,
        amount REAL,
        description TEXT,
        category TEXT,
        date TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS user_profiles (
        id INTEGER PRIMARY KEY,
        user_email TEXT UNIQUE,
        monthly_income REAL DEFAULT 0,
        created_date TEXT,
        updated_date TEXT
    )
    ''')
    
    # Create budget table
    c.execute('''
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY,
        user_email TEXT,
        category TEXT,
        amount REAL,
        month TEXT,
        year INTEGER
    )
    ''')

        # Create goals table
    c.execute('''
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY,
        user_email TEXT,
        goal_name TEXT,
        goal_type TEXT,
        target_amount REAL,
        current_amount REAL DEFAULT 0,
        target_date TEXT,
        monthly_contribution REAL DEFAULT 0,
        created_date TEXT,
        status TEXT DEFAULT 'active',
        goal_details TEXT DEFAULT '{}'
    )
    ''')
    
    # Create goal_contributions table
    c.execute('''
    CREATE TABLE IF NOT EXISTS goal_contributions (
        id INTEGER PRIMARY KEY,
        goal_id INTEGER,
        user_email TEXT,
        amount REAL,
        contribution_date TEXT,
        note TEXT,
        FOREIGN KEY (goal_id) REFERENCES goals (id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Call init_db to ensure tables exist
init_db()

def update_database_schema():
    """Update existing database to include goal_details column"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if goal_details column exists
        c.execute("PRAGMA table_info(goals)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'goal_details' not in columns:
            # Add the new column
            c.execute("ALTER TABLE goals ADD COLUMN goal_details TEXT DEFAULT '{}'")
            conn.commit()
            print("Database updated with goal_details column")
        
        conn.close()
    except Exception as e:
        print(f"Error updating database: {e}")

# Call this function after init_db()
update_database_schema()  # Add this line right after init_db()

def set_user_income(user_email, monthly_income):
    """Set or update user's monthly income"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Check if user profile exists
        c.execute("SELECT id FROM user_profiles WHERE user_email = ?", (user_email,))
        existing = c.fetchone()
        
        if existing:
            c.execute("UPDATE user_profiles SET monthly_income = ?, updated_date = ? WHERE user_email = ?",
                     (monthly_income, current_date, user_email))
        else:
            c.execute("INSERT INTO user_profiles (user_email, monthly_income, created_date, updated_date) VALUES (?, ?, ?, ?)",
                     (user_email, monthly_income, current_date, current_date))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error setting income: {str(e)}")
        return False

def get_user_income(user_email):
    """Get user's monthly income"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT monthly_income FROM user_profiles WHERE user_email = ?", (user_email,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        return 0

def has_income_set(user_email):
    """Check if user has set their income"""
    income = get_user_income(user_email)
    return income > 0

def add_multiple_expenses(user_email, expenses_list):
    """Add multiple expenses to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        date = datetime.now().strftime("%Y-%m-%d")
        expense_ids = []
        
        for expense in expenses_list:
            c.execute("INSERT INTO expenses (user_email, amount, description, category, date) VALUES (?, ?, ?, ?, ?)",
                     (user_email, expense["amount"], expense["description"], expense["category"], date))
            expense_ids.append(c.lastrowid)
        
        conn.commit()
        conn.close()
        return True, expense_ids
    except Exception as e:
        st.error(f"Error adding expenses: {str(e)}")
        return False, []

# ---------------------------- Login/SignUp Functions ----------------------------
# Function to validate email format
def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

# Function to validate password strength
def is_valid_password(password):
    # Check if password is at least 8 characters long and contains at least 1 letter and 1 number
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    
    if not any(char.isalpha() for char in password):
        return False, "Password must contain at least one letter."
    
    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one number."
    
    return True, "Password is valid."

# Function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Function to load users
def load_users():
    with open(USER_DB_FILE, 'r') as f:
        return json.load(f)

# Function to save users with proper indentation
def save_users(users):
    with open(USER_DB_FILE, 'w') as f:
        json.dump(users, f, indent=4)

# ------------------------------- Daily Spending Logging Functions -------------------------------
# Function to add expense 
def add_expense(user_email, amount, description, category):
    """
    Add expense to database - FIXED VERSION
    """
    try:
        conn = sqlite3.connect(DB_PATH)  # ✅ Use DB_PATH
        c = conn.cursor()
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        print(f"DEBUG: Saving expense - User: {user_email}, Amount: {amount}, Description: {description}, Category: {category}")
        
        # ✅ Remove datetime column, use only the columns that exist
        c.execute("""
            INSERT INTO expenses (user_email, amount, description, category, date) 
            VALUES (?, ?, ?, ?, ?)
        """, (user_email, amount, description, category, current_date))
        
        expense_id = c.lastrowid
        conn.commit()
        conn.close()
        
        print(f"DEBUG: Expense saved with ID: {expense_id}")
        return True, expense_id  # ✅ Return TWO values
        
    except Exception as e:
        print(f"DEBUG: Error saving expense: {e}")
        return False, None  # ✅ Return TWO values

# Function to update expense category
def update_expense_category(expense_id, new_category):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE expenses SET category = ? WHERE id = ?", (new_category, expense_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error updating category: {str(e)}")
        return False

# Function to update expense amount
def update_expense_amount(expense_id, new_amount):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE expenses SET amount = ? WHERE id = ?", (new_amount, expense_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error updating amount: {str(e)}")
        return False

# Function to categorize an expense description
def categorize_expense(description):
    description = description.lower()
    print(f"DEBUG: Categorizing '{description}'")  
    
    # Standard categories with their keywords (ENHANCED WITH MALAYSIAN FOOD)
    categories = {
        "food": [
            # Western/International food
            "grocery", "groceries", "restaurant", "lunch", "dinner", "breakfast", "food", "meal", "coffee", 
            "snack", "eat", "eating", "dining", "dine", "cafe", "cafeteria", "fastfood", "fast food", "drinks",
            "takeout", "take-out", "takeaway", "take-away", "pizza", "burger", "sushi", "dessert", "desert", 
            "ice cream", "cake", "pastry", "bakery",
            
            # MALAYSIAN FOOD ADDITIONS
            "nasi lemak", "nasi", "lemak", "roti", "roti kosong", "roti canai", "mee", "mee goreng", 
            "char kuey teow", "kuey teow", "laksa", "rendang", "satay", "rojak", "cendol", "ais kacang",
            "teh tarik", "kopi", "mamak", "economy rice", "mixed rice", "wan tan mee", "bak kut teh",
            "dim sum", "yam cha", "zi char", "hokkien mee", "prawn mee", "curry", "tom yam",
            "padthai", "fried rice", "nasi goreng", "mee hoon", "bee hoon", "kuih", "onde onde",
            "durian", "mangosteen", "rambutan", "longan", "lychee", "coconut", "kelapa",
            "ayam", "chicken rice", "duck rice", "roast", "bbq", "steamboat", "hotpot",
            "banana leaf", "thosai", "tosai", "appam", "chapati", "briyani", "naan",
            "wonton", "dumpling", "pau", "bao", "fishball", "fish ball", "meat ball"
        ],
        
        "transport": ["gas", "fuel", "bus", "train", "taxi", "grab", "uber", "lyft", "fare", "ticket", "transport",
                      "transportation", "commute", "travel", "subway", "mrt", "lrt", "petrol", "diesel", "car", 
                      "ride", "toll", "parking", "touch n go", "touchngo", "rapidkl", "ktm", "monorail"],
        
        "entertainment": ["movie", "cinema", "ktv", "karaoke", "game", "concert", "show", "entertainment", "fun", 
                         "leisure", "theater", "theatre", "park", "ticket", "streaming", "subscription", "netflix", 
                         "spotify", "disney", "astro", "unifi tv"],
        
        "shopping": ["clothes", "clothing", "shoes", "shirt", "dress", "pants", "fashion", "mall", "shop", 
                    "shopping", "boutique", "store", "retail", "buy", "purchase", "merchandise", "apparel", 
                    "accessories", "jewelry", "gift", "lipstick", "cosmetics", "makeup", "pavilion", "klcc",
                    "mid valley", "sunway pyramid", "1utama", "aeon", "jusco"],
        
        "utilities": ["electricity", "electric", "water", "bill", "utility", "phone", "internet", "wifi", "service",
                     "broadband", "gas", "subscription", "cable", "tv", "television", "streaming", "tnb", "telekom",
                     "maxis", "celcom", "digi", "unifi", "streamyx"],
        
        "housing": ["rent", "mortgage", "housing", "apartment", "house", "accommodation", "condo", "condominium", 
                   "room", "deposit", "lease", "property", "maintenance", "repair", "renovation"],
        
        "healthcare": ["doctor", "clinic", "hospital", "medicine", "medical", "health", "healthcare", "prescription", 
                      "pharmacy", "dental", "dentist", "vitamin", "supplement", "drug", "treatment", "therapy", 
                      "checkup", "insurance", "guardian", "watson", "caring"],
        
        "education": ["book", "textbook", "course", "class", "tuition", "education", "school", "college", "university", 
                     "study", "training", "tutorial", "lesson", "workshop", "seminar", "fee", "tutor", "teacher"]
    }
    
    # Try to match description to category
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in description:
                return category
    
    # Check if the description contains any custom categories
    if "custom_categories" in st.session_state:
        for category in st.session_state.custom_categories:
            if category in description:
                return category
    
    # If no match found, return "other"
    return "other"

# Function to extract expense information from text
def extract_entities(text):
    text = text.lower().strip()
    entities = {}
    
    if len(text) <= 2 or not any(char.isalpha() for char in text):
        return entities
    
    # Check for minimum viable expense pattern
    if not any(keyword in text for keyword in ["rm", "spent", "paid", "buy", "bought", "cost"]) and not re.search(r'\d+', text):
        return entities
    
    # Expense patterns to extract amount and description
    expense_patterns = [
        r"spent (\$?[\d,.]+)\s*(?:rm)?\s*on (.+)",
        r"spent (\$?[\d,.]+)\s*(?:rm)?\s*for (.+)",
        r"i spent (\$?[\d,.]+)\s*(?:rm)?\s*on (.+)",
        r"i spent (\$?[\d,.]+)\s*(?:rm)?\s*for (.+)",
        r"i paid (\$?[\d,.]+)\s*(?:rm)?\s*for (.+)",
        r"paid (\$?[\d,.]+)\s*(?:rm)?\s*for (.+)",
        r"bought (.+) for (\$?[\d,.]+)\s*(?:rm)?",
        r"purchased (.+) for (\$?[\d,.]+)\s*(?:rm)?",
        r"(\$?[\d,.]+)\s*(?:rm)?\s*for (.+)",
        r"rm\s*(\d+\.?\d*) for (.+)",
        r"rm\s*(\d+\.?\d*) on (.+)",
        r"rm(\d+\.?\d*) for (.+)",
        r"rm(\d+\.?\d*) on (.+)",
        r"rm ?(\d+\.?\d*) (.+)",  
        r"rm(\d+) (.+)",          
        r"(\d+) (?:rm|$) (.+)",   
        r"(\d+) for (.+)",        
        r"(\d+) on (.+)"        
    ]
    
    for pattern in expense_patterns:
        match = re.search(pattern, text)
        if match:
            # Extract amount and item from the match
            groups = match.groups()
            
            if "bought" in pattern or "purchased" in pattern:
                entities["description"] = groups[0].strip()
                amount_str = groups[1].strip().replace('$', '').replace('RM', '').replace('rm', '')
            else:
                amount_str = groups[0].strip().replace('$', '').replace('RM', '').replace('rm', '')
                entities["description"] = groups[1].strip()
            
            try:
                entities["amount"] = float(amount_str.replace(',', ''))
            except ValueError:
                st.error(f"Could not convert '{amount_str}' to a number")
                pass
            
            # Auto-categorize the expense
            if "description" in entities:
                category = categorize_expense(entities["description"])
                entities["category"] = category
            
            break
    
    return entities

def extract_multiple_expenses(text):
    """🆕 ENHANCED: Better multiple expense extraction with Malaysian context"""
    text = text.lower().strip()
    expenses = []
    
    print(f"DEBUG: Enhanced processing for: '{text}'")
    
    # Enhanced splitting - handle more natural language
    segments = []
    
    # Split by commas first, then handle 'and' within segments
    comma_parts = text.split(',')
    for part in comma_parts:
        part = part.strip()
        # If a part has multiple 'rm' mentions, split by 'and'
        if part.count('rm') > 1 or ' and rm' in part:
            and_parts = re.split(r'\s+and\s+', part)
            segments.extend([p.strip() for p in and_parts if p.strip()])
        else:
            segments.append(part)
    
    # If no commas but has 'and', split by 'and'
    if len(segments) == 1 and ' and ' in text:
        segments = [p.strip() for p in re.split(r'\s+and\s+', text) if p.strip()]
    
    print(f"DEBUG: Split into {len(segments)} segments: {segments}")
    
    # Enhanced patterns - more natural Malaysian expressions
    expense_patterns = [
        # Direct RM patterns
        r"rm\s*(\d+(?:\.\d+)?)\s+(?:for\s+|on\s+|at\s+)?(.+)",
        r"rm(\d+(?:\.\d+)?)\s+(.+)",
        
        # Amount then RM patterns  
        r"(\d+(?:\.\d+)?)\s*rm\s*(?:for\s+|on\s+|at\s+)?(.+)",
        r"(\d+(?:\.\d+)?)\s+rm\s+(.+)",
        
        # Natural spending expressions
        r"spent\s*(?:rm)?\s*(\d+(?:\.\d+)?)\s*(?:rm)?\s*(?:on|for|at)\s*(.+)",
        r"paid\s*(?:rm)?\s*(\d+(?:\.\d+)?)\s*(?:rm)?\s*(?:for|on|at)\s*(.+)",
        r"bought\s*(.+?)\s*(?:for|cost|costs)\s*(?:rm)?\s*(\d+(?:\.\d+)?)",
        
        # Simple patterns
        r"(\d+(?:\.\d+)?)\s*(?:for|on|at)\s*(.+)",
        r"(\d+(?:\.\d+)?)\s+(.+)"
    ]
    
    for i, segment in enumerate(segments):
        if not segment:
            continue
            
        print(f"DEBUG: Processing segment {i+1}: '{segment}'")
        
        found_expense = False
        
        for pattern_idx, pattern in enumerate(expense_patterns):
            match = re.search(pattern, segment)
            if match:
                try:
                    groups = match.groups()
                    
                    # Handle different pattern structures
                    if "bought" in pattern:
                        description = groups[0].strip()
                        amount = float(groups[1])
                    else:
                        amount = float(groups[0])
                        description = groups[1].strip()
                    
                    print(f"DEBUG: Pattern {pattern_idx} matched - Amount: {amount}, Raw description: '{description}'")
                    
                    # Clean up description intelligently
                    description = clean_expense_description(description)
                    
                    print(f"DEBUG: Cleaned description: '{description}'")
                    
                    if description and amount > 0:
                        category = categorize_expense_enhanced(description)
                        expense_obj = {
                            "amount": amount,
                            "description": description,
                            "category": category
                        }
                        expenses.append(expense_obj)
                        print(f"DEBUG: ✅ Added expense: {expense_obj}")
                        found_expense = True
                        break
                        
                except (ValueError, IndexError) as e:
                    print(f"DEBUG: Error with pattern {pattern_idx}: {e}")
                    continue
        
        if not found_expense:
            print(f"DEBUG: ❌ No expense found in segment: '{segment}'")
    
    print(f"DEBUG: Final result: {len(expenses)} expenses found")
    return expenses

def clean_expense_description(description):
    """🆕 NEW: Smart description cleaning for Malaysian context"""
    # Remove RM mentions
    description = re.sub(r'\b(?:rm|RM)\s*\d+(?:\.\d+)?', '', description)
    
    # Remove common spending prefixes
    description = re.sub(r'^(?:for|on|at|buying|getting|purchasing)\s+', '', description)
    
    # Remove extra whitespace
    description = ' '.join(description.split())
    
    # Handle Malaysian food context
    malaysian_food_fixes = {
        'nasi': 'nasi lemak' if 'lemak' not in description else description,
        'roti': 'roti canai' if 'canai' not in description and 'kosong' not in description else description,
        'mee': 'mee goreng' if 'goreng' not in description and 'soup' not in description else description
    }
    
    for key, replacement in malaysian_food_fixes.items():
        if description.strip() == key:
            description = replacement
    
    return description.strip()

def categorize_expense_enhanced(description):
    """🆕 ENHANCED: Better categorization with Malaysian context"""
    description = description.lower()
    
    # Enhanced Malaysian food categories
    malaysian_food_terms = [
        "nasi lemak", "nasi", "roti canai", "roti kosong", "roti", "mee goreng", "mee", 
        "char kuey teow", "laksa", "rendang", "satay", "rojak", "cendol", "ais kacang",
        "teh tarik", "kopi", "mamak", "economy rice", "mixed rice", "chicken rice",
        "wan tan mee", "bak kut teh", "dim sum", "hokkien mee", "prawn mee",
        "curry", "ayam", "duck rice", "banana leaf", "briyani", "thosai", "appam"
    ]
    
    # Enhanced categories
    categories = {
        "food": malaysian_food_terms + [
            "food", "lunch", "dinner", "breakfast", "meal", "eat", "restaurant", "cafe",
            "grocery", "groceries", "snack", "drink", "coffee", "tea", "dessert",
            "burger", "pizza", "sandwich", "salad", "soup", "rice", "noodles"
        ],
        
        "transport": [
            "transport", "bus", "train", "taxi", "grab", "uber", "fuel", "petrol",
            "gas", "parking", "toll", "mrt", "lrt", "rapidkl", "ktm", "touch n go",
            "touchngo", "car", "motorcycle", "flight", "plane", "airport"
        ],
        
        "entertainment": [
            "movie", "cinema", "film", "game", "gaming", "concert", "show", "entertainment", 
            "netflix", "spotify", "youtube", "ktv", "karaoke", "astro", "streaming",
            "book", "magazine", "music", "sports", "gym", "fitness"
        ],
        
        "shopping": [
            "shopping", "clothes", "clothing", "shirt", "shoes", "dress", "pants", "mall", 
            "store", "pavilion", "klcc", "mid valley", "aeon", "jusco", "gift", 
            "online shopping", "shopee", "lazada", "fashion", "accessories"
        ],
        
        "utilities": [
            "electric", "electricity", "water", "internet", "phone", "bill", "wifi",
            "tnb", "telekom", "maxis", "digi", "celcom", "unifi", "streamyx", "astro",
            "utility", "broadband", "mobile", "postpaid", "prepaid"
        ],
        
        "housing": [
            "rent", "rental", "mortgage", "housing", "apartment", "house", "room", 
            "maintenance", "repair", "condo", "condominium", "property"
        ],
        
        "healthcare": [
            "doctor", "clinic", "hospital", "medicine", "medical", "pharmacy",
            "dental", "dentist", "health", "guardian", "watson", "caring",
            "checkup", "treatment", "vitamin", "supplement"
        ],
        
        "education": [
            "book", "textbook", "course", "education", "school", "university", "college",
            "tuition", "class", "training", "workshop", "seminar", "learning"
        ]
    }
    
    # Find best matching category
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in description:
                print(f"DEBUG: Matched '{keyword}' -> '{category}'")
                return category
    
    print(f"DEBUG: No category match found for '{description}' -> 'other'")
    return "other"

# Function to add a custom category
def add_custom_category(category):
    # Initialize if needed
    if "custom_categories" not in st.session_state:
        st.session_state.custom_categories = []
    
    # Add if not already in list
    category = category.lower().strip()
    if category and category not in st.session_state.custom_categories:
        st.session_state.custom_categories.append(category)
        return True
    return False

# Function to get user's expenses by date range
def get_expenses(user_email, limit=None, start_date=None, end_date=None, category=None):
    """
    Get user's expenses with flexible filtering options.
    
    Parameters:
    - user_email: User's email for identification
    - limit: Maximum number of expenses to return
    - start_date: Filter expenses on or after this date (YYYY-MM-DD format)
    - end_date: Filter expenses before this date (YYYY-MM-DD format)
    - category: Filter expenses by category
    
    Returns:
    - List of expense dictionaries with id, amount, description, category, date
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    query = "SELECT * FROM expenses WHERE user_email = ?"
    params = [user_email]
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND date < ?"
        params.append(end_date)
    
    if category:
        query += " AND category = ?"
        params.append(category.lower())
    
    query += " ORDER BY date DESC"
    
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    
    c.execute(query, params)
    expenses = c.fetchall()
    conn.close()
    
    # Convert to list of dicts for easier handling
    expense_list = []
    for exp in expenses:
        expense_list.append({
            "id": exp[0],
            "amount": exp[2],
            "description": exp[3],
            "category": exp[4],
            "date": exp[5]
        })
    
    return expense_list

# Function to get spending summary by category
def get_spending_by_category(user_email, month=None, year=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if month and year:
        # Convert month name to month number for filtering
        if isinstance(month, str):
            try:
                month_num = datetime.strptime(month, "%B").month
            except ValueError:
                month_num = datetime.now().month
        else:
            month_num = month
            
        # Create date range for filtering
        start_date = f"{year}-{month_num:02d}-01"
        if month_num == 12:
            end_date = f"{year+1}-01-01"
        else:
            end_date = f"{year}-{month_num+1:02d}-01"
        
        c.execute("""
            SELECT category, SUM(amount) 
            FROM expenses 
            WHERE user_email = ? AND date >= ? AND date < ? 
            GROUP BY category
        """, (user_email, start_date, end_date))
    else:
        # Current month by default
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1).strftime("%Y-%m-%d")
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1).strftime("%Y-%m-%d")
        else:
            next_month = datetime(now.year, now.month + 1, 1).strftime("%Y-%m-%d")
        
        c.execute("""
            SELECT category, SUM(amount) 
            FROM expenses 
            WHERE user_email = ? AND date >= ? AND date < ? 
            GROUP BY category
        """, (user_email, month_start, next_month))
    
    categories = c.fetchall()
    conn.close()
    
    return dict(categories)

# -------------------------------- Budget Tracking Functions -------------------------------
def get_budget_status(user_email, category=None, month=None, year=None):
    """
    Get budget status for a specific category or all categories
    Returns formatted text with budget information
    """
    if not month:
        month = datetime.now().strftime("%B")
    if not year:
        year = datetime.now().year
    
    budgets = get_budgets(user_email, month, year)
    spending = get_spending_by_category(user_email, month, year)
    
    if not budgets:
        return "No budgets set up yet."
    
    budget_text = ""
    
    if category:
        # Show specific category only
        for budget in budgets:
            if budget["category"] == category.lower():
                budget_amount = budget["amount"]
                spent = spending.get(category.lower(), 0)
                remaining = budget_amount - spent
                percent_used = (spent / budget_amount) * 100 if budget_amount > 0 else 0
                
                status = "🟢 Good" if percent_used < 80 else "🟠 Watch" if percent_used < 100 else "🔴 Over"
                
                budget_text = f"**{category.title()} Budget for {month} {year}:**\n\n"
                budget_text += f"• Budget: RM{budget_amount:.2f}\n"
                budget_text += f"• Spent: RM{spent:.2f}\n"
                budget_text += f"• Remaining: RM{remaining:.2f}\n"
                budget_text += f"• Used: {percent_used:.1f}%\n"
                budget_text += f"• Status: {status}\n"
                break
        else:
            budget_text = f"No budget set for {category.title()} yet."
def get_smart_goal_suggestions():
    """Provide smart goal templates with realistic amounts for Malaysian context"""
    templates = {
        "emergency_fund": {
            "name": "Emergency Fund",
            "suggested_amounts": [3000, 5000, 10000, 15000],
            "description": "3-6 months of expenses for peace of mind",
            "timeline_months": [6, 12, 18, 24],
            "priority": "high",
            "tips": "Start with RM3,000 and build up gradually",
            "icon": "💰"
        },
        "vacation": {
            "name": "Dream Vacation",
            "suggested_amounts": [2000, 5000, 8000, 15000],
            "description": "Create unforgettable memories",
            "timeline_months": [6, 12, 18, 24],
            "priority": "medium",
            "tips": "Budget based on destination and travel style",
            "icon": "🏖️"
        },
        "car": {
            "name": "New Car",
            "suggested_amounts": [20000, 50000, 80000, 120000],
            "description": "Reliable transportation for your future",
            "timeline_months": [12, 24, 36, 48],
            "priority": "medium",
            "tips": "Consider down payment vs full purchase",
            "icon": "🚗"
        },
        "house": {
            "name": "Dream Home Down Payment",
            "suggested_amounts": [50000, 100000, 200000, 300000],
            "description": "Your key to homeownership",
            "timeline_months": [24, 36, 48, 60],
            "priority": "high",
            "tips": "Aim for 10-20% of property value",
            "icon": "🏠"
        },
        "wedding": {
            "name": "Perfect Wedding",
            "suggested_amounts": [15000, 30000, 50000, 80000],
            "description": "Your special day deserves everything",
            "timeline_months": [12, 18, 24, 36],
            "priority": "high",
            "tips": "Budget for all wedding expenses",
            "icon": "💍"
        },
        "education": {
            "name": "Education Investment",
            "suggested_amounts": [5000, 15000, 30000, 50000],
            "description": "Invest in your future success",
            "timeline_months": [6, 12, 24, 36],
            "priority": "high",
            "tips": "Include tuition, books, and living expenses",
            "icon": "🎓"
        }
    }
    return templates

def get_enhanced_goal_progress(goal):
    """Enhanced progress calculation with motivational insights"""
    target_amount = goal["target_amount"]
    current_amount = goal["current_amount"]
    target_date = datetime.strptime(goal["target_date"], "%Y-%m-%d")
    today = datetime.now()
    
    # Basic calculations
    progress_percent = min(100, (current_amount / target_amount) * 100 if target_amount > 0 else 0)
    remaining_amount = max(0, target_amount - current_amount)
    days_remaining = (target_date - today).days
    months_remaining = max(0.1, days_remaining / 30.44)
    
    # Enhanced milestone tracking
    milestones = {
        25: {"icon": "🎯", "message": "Great start! You're building momentum!"},
        50: {"icon": "🔥", "message": "Halfway there! You're doing amazing!"},
        75: {"icon": "🚀", "message": "So close! The finish line is in sight!"},
        90: {"icon": "💎", "message": "Almost there! You're absolutely crushing it!"},
        100: {"icon": "🏆", "message": "GOAL ACHIEVED! You're a financial superstar!"}
    }
    
    # Find current milestone
    current_milestone = None
    for milestone_percent in sorted(milestones.keys()):
        if progress_percent >= milestone_percent:
            current_milestone = milestones[milestone_percent]
    
    # Smart status determination
    if progress_percent >= 100:
        status = "🎉 ACHIEVED!"
        status_msg = "Congratulations! You did it! Time to celebrate and set a new goal!"
        status_color = "success"
        next_action = "Consider setting a new goal or increasing this one!"
    elif days_remaining < 0:
        status = "⏰ Past Due"
        status_msg = "Don't worry! You can still reach this goal. Want to adjust the date?"
        status_color = "error"
        next_action = "Consider extending the deadline or making a big contribution!"
    elif progress_percent >= 90:
        status = "🔥 SO CLOSE!"
        status_msg = f"Just RM{remaining_amount:.2f} left! You're almost there!"
        status_color = "success"
        next_action = f"One more push of RM{remaining_amount:.2f} and you're done!"
    elif progress_percent >= 75:
        status = "🚀 EXCELLENT!"
        status_msg = "You're in the final stretch! Keep up this amazing momentum!"
        status_color = "success"
        next_action = f"Save RM{remaining_amount/2:.2f} this month and next to finish strong!"
    elif progress_percent >= 50:
        status = "💪 STRONG PROGRESS"
        status_msg = "You're over halfway! This is where champions are made!"
        status_color = "warning"
        next_action = f"Stay consistent with RM{remaining_amount/months_remaining:.2f}/month!"
    elif progress_percent >= 25:
        status = "🎯 BUILDING MOMENTUM"
        status_msg = "Great foundation! Every contribution counts towards your dream!"
        status_color = "warning"
        next_action = f"Aim for RM{remaining_amount/months_remaining:.2f}/month to stay on track!"
    else:
        status = "🌟 GETTING STARTED"
        status_msg = "Every great achievement starts with a first step! You've got this!"
        status_color = "info"
        next_action = f"Start with RM{remaining_amount/months_remaining:.2f}/month - totally doable!"
    
    # Calculate weekly and daily targets
    weeks_remaining = max(1, days_remaining / 7)
    weekly_target = remaining_amount / weeks_remaining if weeks_remaining > 0 else 0
    daily_target = remaining_amount / days_remaining if days_remaining > 0 else 0
    
    # Progress velocity
    created_date = datetime.strptime(goal.get("created_date", today.strftime("%Y-%m-%d")), "%Y-%m-%d")
    days_since_creation = max(1, (today - created_date).days)
    current_velocity = current_amount / days_since_creation if days_since_creation > 0 else 0
    projected_completion = current_amount + (current_velocity * days_remaining) if current_velocity > 0 else current_amount
    velocity_status = "ahead" if projected_completion >= target_amount else "behind"
    
    return {
        "progress_percent": progress_percent,
        "remaining_amount": remaining_amount,
        "days_remaining": days_remaining,
        "months_remaining": months_remaining,
        "weeks_remaining": weeks_remaining,
        "status": status,
        "status_msg": status_msg,
        "status_color": status_color,
        "next_action": next_action,
        "current_milestone": current_milestone,
        "weekly_target": weekly_target,
        "daily_target": daily_target,
        "velocity_status": velocity_status,
        "projected_completion": projected_completion,
        "current_velocity": current_velocity,
        "days_since_creation": days_since_creation
    }

def get_smart_contribution_suggestions(goal, user_email):
    """Generate intelligent contribution suggestions"""
    progress = get_enhanced_goal_progress(goal)
    spending = get_spending_by_category(user_email)
    monthly_spending = sum(spending.values()) if spending else 1000
    
    suggestions = []
    
    # Percentage-based suggestions
    for percent in [5, 10, 15, 20]:
        amount = (percent / 100) * monthly_spending
        if amount >= 10:  # Only suggest if >= RM10
            suggestions.append({
                "type": "percentage",
                "amount": amount,
                "description": f"{percent}% of monthly spending",
                "frequency": "monthly"
            })
    
    # Round number suggestions
    round_amounts = [50, 100, 200, 500, 1000]
    for amount in round_amounts:
        if amount <= monthly_spending * 0.3:  # Don't suggest more than 30% of spending
            suggestions.append({
                "type": "round",
                "amount": amount,
                "description": f"RM{amount} - nice round number!",
                "frequency": "one-time"
            })
    
    # Goal-specific suggestions
    remaining = progress["remaining_amount"]
    months_left = progress["months_remaining"]
    
    if months_left > 0 and remaining > 0:
        monthly_needed = remaining / months_left
        suggestions.append({
            "type": "target",
            "amount": monthly_needed,
            "description": f"Monthly target to reach goal on time",
            "frequency": "monthly"
        })
    
    # Filter and sort by practicality
    practical_suggestions = [s for s in suggestions if 10 <= s["amount"] <= monthly_spending * 0.5]
    return sorted(practical_suggestions, key=lambda x: x["amount"])[:4]

def calculate_goal_feasibility(target_amount, target_date, user_email):
    """Calculate if goal is realistic based on user's spending patterns"""
    spending = get_spending_by_category(user_email)
    monthly_spending = sum(spending.values()) if spending else 1000
    
    days_until = (target_date - datetime.now().date()).days
    months_until = max(1, days_until / 30.44)
    required_monthly = target_amount / months_until
    
    # Calculate feasibility score
    spending_ratio = required_monthly / monthly_spending if monthly_spending > 0 else 1
    
    if spending_ratio <= 0.1:
        return {
            "feasibility": "🟢 Very Achievable",
            "message": "This goal is totally doable! You've got this!",
            "difficulty": "easy"
        }
    elif spending_ratio <= 0.2:
        return {
            "feasibility": "🟡 Achievable with Focus",
            "message": "This will require some discipline, but it's definitely achievable!",
            "difficulty": "medium"
        }
    elif spending_ratio <= 0.3:
        return {
            "feasibility": "🟠 Challenging but Possible",
            "message": "This is ambitious! Consider extending the timeline or reducing the amount.",
            "difficulty": "hard"
        }
    else:
        return {
            "feasibility": "🔴 Very Challenging",
            "message": "This might be too aggressive. Let's adjust the timeline or amount!",
            "difficulty": "very_hard"
        }

def get_goal_priority_suggestion(user_email, goal_type):
    """Suggest goal priority based on user's financial situation"""
    goals = get_user_goals(user_email)
    spending = get_spending_by_category(user_email)
    
    # Smart priority logic
    if goal_type == "emergency_fund" and not any(g["goal_type"] == "emergency_fund" for g in goals):
        return "🔥 HIGH PRIORITY - Everyone needs an emergency fund first!"
    elif goal_type == "house" and sum(spending.values()) > 3000:
        return "💡 SMART CHOICE - You have good income, perfect time for property!"
    elif goal_type == "vacation" and len(goals) > 2:
        return "🌟 REWARD YOURSELF - You're doing great with other goals!"
    else:
        return "👍 GREAT GOAL - This fits well with your financial journey!"
    
def add_goal(user_email, goal_name, goal_type, target_amount, target_date, monthly_contribution=0, goal_details=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        created_date = datetime.now().strftime("%Y-%m-%d")
        
        # Convert goal_details to JSON string
        details_json = json.dumps(goal_details or {})
        
        c.execute("""
            INSERT INTO goals (user_email, goal_name, goal_type, target_amount, 
                             target_date, monthly_contribution, created_date, goal_details) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_email, goal_name, goal_type, target_amount, target_date, monthly_contribution, created_date, details_json))
        goal_id = c.lastrowid
        conn.commit()
        conn.close()
        return True, goal_id
    except Exception as e:
        st.error(f"Error adding goal: {str(e)}")
        return False, None

def get_user_goals(user_email):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM goals WHERE user_email = ? AND status = 'active' ORDER BY created_date DESC", (user_email,))
    goals = c.fetchall()
    conn.close()
    
    goal_list = []
    for goal in goals:
        # Handle both old goals (without goal_details) and new goals (with goal_details)
        goal_details = "{}"
        if len(goal) > 10:  # New format with goal_details
            goal_details = goal[10] or "{}"
        
        try:
            parsed_details = json.loads(goal_details)
        except:
            parsed_details = {}
        
        goal_list.append({
            "id": goal[0],
            "goal_name": goal[2],
            "goal_type": goal[3],
            "target_amount": goal[4],
            "current_amount": goal[5],
            "target_date": goal[6],
            "monthly_contribution": goal[7],
            "created_date": goal[8],
            "status": goal[9],
            "goal_details": parsed_details
        })
    
    return goal_list

def get_goal_details_form(goal_type):
    """Generate form fields based on goal type"""
    details = {}
    
    if goal_type == "car":
        st.subheader("🚗 Car Details")
        col1, col2 = st.columns(2)
        
        with col1:
            details["brand"] = st.selectbox("Car Brand", [
                "Toyota", "Honda", "Mercedes-Benz", "BMW", "Audi", "Volkswagen", 
                "Nissan", "Hyundai", "Kia", "Mazda", "Subaru", "Mitsubishi",
                "Lexus", "Infiniti", "Acura", "Genesis", "Volvo", "Jaguar",
                "Land Rover", "Porsche", "Ferrari", "Lamborghini", "Bentley",
                "Rolls-Royce", "McLaren", "Aston Martin", "Maserati", "Bugatti",
                "Tesla", "Ford", "Chevrolet", "Dodge", "Jeep", "Cadillac",
                "Lincoln", "Buick", "GMC", "Ram", "Chrysler", "Other"
            ])
            
            if details["brand"] == "Toyota":
                details["model"] = st.selectbox("Model", [
                    "Camry", "Corolla", "RAV4", "Highlander", "Prius", "Sienna",
                    "Tacoma", "Tundra", "4Runner", "Sequoia", "Land Cruiser",
                    "Avalon", "Yaris", "C-HR", "Venza", "Mirai", "Supra", "Other"
                ])
            elif details["brand"] == "Honda":
                details["model"] = st.selectbox("Model", [
                    "Civic", "Accord", "CR-V", "Pilot", "Odyssey", "HR-V",
                    "Passport", "Ridgeline", "Insight", "Clarity", "Fit",
                    "CR-V Hybrid", "Accord Hybrid", "Other"
                ])
            elif details["brand"] == "Mercedes-Benz":
                details["model"] = st.selectbox("Model", [
                    "C-Class", "E-Class", "S-Class", "GLC", "GLE", "GLS",
                    "A-Class", "CLA", "CLS", "G-Class", "GLA", "GLB",
                    "AMG GT", "SL", "SLC", "Maybach", "Other"
                ])
            elif details["brand"] == "BMW":
                details["model"] = st.selectbox("Model", [
                    "3 Series", "5 Series", "7 Series", "X3", "X5", "X7",
                    "1 Series", "2 Series", "4 Series", "6 Series", "8 Series",
                    "X1", "X2", "X4", "X6", "Z4", "i3", "i4", "iX", "Other"
                ])
            else:
                details["model"] = st.text_input("Model", placeholder="Enter car model")
        
        with col2:
            details["year"] = st.selectbox("Year", list(range(2024, 2010, -1)) + ["Used (Older)", "New (Latest)"])
            details["condition"] = st.selectbox("Condition", ["Brand New", "Used - Excellent", "Used - Good", "Used - Fair", "Certified Pre-Owned"])
            details["transmission"] = st.selectbox("Transmission", ["Automatic", "Manual", "CVT", "No Preference"])
            details["fuel_type"] = st.selectbox("Fuel Type", ["Gasoline", "Hybrid", "Electric", "Diesel", "Plug-in Hybrid"])
            details["color_preference"] = st.text_input("Preferred Color", placeholder="e.g., White, Black, Silver")
    
    elif goal_type == "house":
        st.subheader("🏠 House Details")
        col1, col2 = st.columns(2)
        
        with col1:
            details["property_type"] = st.selectbox("Property Type", [
                "Single Family Home", "Condominium", "Townhouse", "Apartment",
                "Duplex", "Villa", "Penthouse", "Studio", "Loft", "Other"
            ])
            details["bedrooms"] = st.selectbox("Bedrooms", ["1", "2", "3", "4", "5", "6+", "No Preference"])
            details["bathrooms"] = st.selectbox("Bathrooms", ["1", "1.5", "2", "2.5", "3", "3.5", "4+", "No Preference"])
            details["square_feet"] = st.text_input("Square Feet", placeholder="e.g., 1200, 2000")
        
        with col2:
            details["location"] = st.text_input("Preferred Location", placeholder="e.g., Kuala Lumpur, Selangor")
            details["parking"] = st.selectbox("Parking", ["No Parking", "1 Car", "2 Cars", "3+ Cars", "No Preference"])
            details["amenities"] = st.multiselect("Desired Amenities", [
                "Swimming Pool", "Gym", "Security", "Playground", "Garden",
                "Balcony", "Elevator", "Air Conditioning", "Furnished"
            ])
            details["budget_type"] = st.selectbox("Budget Type", ["Down Payment Only", "Full Purchase Price"])
    
    elif goal_type == "vacation":
        st.subheader("🏖️ Vacation Details")
        col1, col2 = st.columns(2)
        
        with col1:
            details["destination"] = st.text_input("Destination", placeholder="e.g., Japan, Europe, Bali")
            details["duration"] = st.selectbox("Duration", [
                "Weekend (2-3 days)", "Short Trip (4-7 days)", "Week Long (8-14 days)",
                "Extended (15-30 days)", "Month+ (30+ days)"
            ])
            details["travel_style"] = st.selectbox("Travel Style", [
                "Budget Backpacking", "Mid-range Comfort", "Luxury Travel",
                "Business Travel", "Family Vacation", "Adventure Travel"
            ])
        
        with col2:
            details["travelers"] = st.selectbox("Number of Travelers", ["Solo", "Couple", "Family (3-4)", "Group (5+)"])
            details["accommodation"] = st.selectbox("Accommodation Type", [
                "Hostel", "Budget Hotel", "Mid-range Hotel", "Luxury Hotel",
                "Resort", "Airbnb", "Vacation Rental", "Mix of Options"
            ])
            details["activities"] = st.multiselect("Planned Activities", [
                "Sightseeing", "Food Tours", "Adventure Sports", "Beach Activities",
                "Cultural Experiences", "Shopping", "Nightlife", "Photography",
                "Museums", "Nature/Hiking", "Water Sports", "Local Tours"
            ])
    
    elif goal_type == "electronics":
        st.subheader("💻 Electronics Details")
        col1, col2 = st.columns(2)
        
        with col1:
            details["device_type"] = st.selectbox("Device Type", [
                "Laptop", "Desktop Computer", "Smartphone", "Tablet",
                "Gaming Console", "Smart TV", "Camera", "Headphones",
                "Smartwatch", "Home Theater", "Other Electronics"
            ])
            
            if details["device_type"] == "Laptop":
                details["brand"] = st.selectbox("Brand", [
                    "Apple MacBook", "Dell", "HP", "Lenovo", "ASUS", "Acer",
                    "MSI", "Razer", "Microsoft Surface", "Samsung", "Other"
                ])
                details["usage"] = st.selectbox("Primary Use", [
                    "General Use", "Gaming", "Professional Work", "Creative Work",
                    "Programming", "Business", "Student Use"
                ])
            elif details["device_type"] == "Smartphone":
                details["brand"] = st.selectbox("Brand", [
                    "iPhone", "Samsung Galaxy", "Google Pixel", "OnePlus",
                    "Xiaomi", "Huawei", "Oppo", "Vivo", "Nothing", "Other"
                ])
                details["storage"] = st.selectbox("Storage", ["64GB", "128GB", "256GB", "512GB", "1TB"])
            elif details["device_type"] == "Gaming Console":
                details["brand"] = st.selectbox("Console", [
                    "PlayStation 5", "Xbox Series X", "Xbox Series S", "Nintendo Switch",
                    "Steam Deck", "Gaming PC", "VR Headset", "Other"
                ])
        
        with col2:
            details["budget_range"] = st.selectbox("Budget Range", [
                "Under RM1,000", "RM1,000 - RM3,000", "RM3,000 - RM5,000",
                "RM5,000 - RM10,000", "Over RM10,000"
            ])
            details["priority_features"] = st.multiselect("Priority Features", [
                "Performance", "Battery Life", "Display Quality", "Camera Quality",
                "Storage Space", "Build Quality", "Brand Reputation", "Latest Model"
            ])
            details["purchase_timing"] = st.selectbox("Purchase Timing", [
                "As soon as possible", "Wait for sale/discount", "When new model releases",
                "Specific date", "When goal is reached"
            ])
    
    elif goal_type == "wedding":
        st.subheader("💍 Wedding Details")
        col1, col2 = st.columns(2)
        
        with col1:
            details["wedding_style"] = st.selectbox("Wedding Style", [
                "Traditional", "Modern", "Destination Wedding", "Garden Wedding",
                "Beach Wedding", "Church Wedding", "Intimate Ceremony",
                "Grand Celebration", "Cultural/Religious", "Themed Wedding"
            ])
            details["guest_count"] = st.selectbox("Expected Guests", [
                "Small (20-50)", "Medium (51-100)", "Large (101-200)",
                "Very Large (201-300)", "Grand (300+)"
            ])
            details["venue_type"] = st.selectbox("Venue Type", [
                "Hotel Ballroom", "Outdoor Garden", "Beach Resort", "Church/Temple",
                "Restaurant", "Country Club", "Banquet Hall", "Home/Private Property",
                "Destination Venue", "Other"
            ])
        
        with col2:
            details["budget_includes"] = st.multiselect("Budget Includes", [
                "Venue Rental", "Catering", "Photography/Videography", "Decorations",
                "Wedding Dress/Suit", "Rings", "Entertainment/Music", "Flowers",
                "Transportation", "Honeymoon", "Gifts/Favors", "Other Expenses"
            ])
            details["wedding_date"] = st.selectbox("Planned Timeline", [
                "Within 6 months", "6-12 months", "1-2 years", "2+ years", "Not decided yet"
            ])
            details["priority_elements"] = st.multiselect("Most Important Elements", [
                "Venue", "Food & Catering", "Photography", "Entertainment",
                "Decorations", "Wedding Dress", "Guest Experience", "Honeymoon"
            ])
    
    elif goal_type == "education":
        st.subheader("🎓 Education Details")
        col1, col2 = st.columns(2)
        
        with col1:
            details["education_type"] = st.selectbox("Education Type", [
                "University Degree", "Master's Degree", "PhD", "Professional Certification",
                "Online Course", "Bootcamp", "Trade School", "Language Course",
                "Professional Development", "Skill Training", "Other"
            ])
            details["field_of_study"] = st.text_input("Field of Study", placeholder="e.g., Computer Science, MBA, Data Science")
            details["institution_type"] = st.selectbox("Institution Preference", [
                "Local University", "International University", "Online Platform",
                "Private Institution", "Government Institution", "No Preference"
            ])
        
        with col2:
            details["duration"] = st.selectbox("Program Duration", [
                "Short Course (1-6 months)", "Certificate (6-12 months)",
                "Diploma (1-2 years)", "Degree (3-4 years)", "Master's (1-2 years)",
                "PhD (3-5 years)", "Ongoing/Flexible"
            ])
            details["study_mode"] = st.selectbox("Study Mode", [
                "Full-time", "Part-time", "Online", "Hybrid", "Weekend Classes", "Evening Classes"
            ])
            details["budget_covers"] = st.multiselect("Budget Covers", [
                "Tuition Fees", "Books & Materials", "Living Expenses",
                "Transportation", "Technology/Equipment", "Exam Fees", "Other Costs"
            ])
    
    elif goal_type == "emergency_fund":
        st.subheader("💰 Emergency Fund Details")
        col1, col2 = st.columns(2)
        
        with col1:
            details["target_months"] = st.selectbox("Target Coverage", [
                "3 months expenses", "6 months expenses", "9 months expenses",
                "12 months expenses", "18 months expenses", "24+ months expenses"
            ])
            details["monthly_expenses"] = st.number_input("Current Monthly Expenses (RM)", min_value=0.0, format="%.2f")
            details["fund_purpose"] = st.multiselect("Emergency Fund For", [
                "Job Loss", "Medical Emergencies", "Car Repairs", "Home Repairs",
                "Family Emergencies", "Economic Uncertainty", "General Security"
            ])
        
        with col2:
            details["storage_preference"] = st.selectbox("Storage Preference", [
                "High-yield Savings Account", "Money Market Account", "Fixed Deposit",
                "Mix of Accounts", "Accessible Investment", "Not Sure Yet"
            ])
            details["access_priority"] = st.selectbox("Access Priority", [
                "Immediate Access", "24-48 hour access", "Weekly access", "Not concerned"
            ])
    
    return details

def format_goal_details_display(goal):
    """Format goal details for display"""
    if not goal.get("goal_details"):
        return ""
    
    details = goal["goal_details"]
    goal_type = goal["goal_type"]
    
    if goal_type == "car" and details:
        display = f"🚗 **Car Details:**\n"
        if details.get("brand"): display += f"• Brand: {details['brand']}\n"
        if details.get("model"): display += f"• Model: {details['model']}\n"
        if details.get("year"): display += f"• Year: {details['year']}\n"
        if details.get("condition"): display += f"• Condition: {details['condition']}\n"
        if details.get("color_preference"): display += f"• Preferred Color: {details['color_preference']}\n"
        return display
    
    elif goal_type == "house" and details:
        display = f"🏠 **House Details:**\n"
        if details.get("property_type"): display += f"• Type: {details['property_type']}\n"
        if details.get("bedrooms"): display += f"• Bedrooms: {details['bedrooms']}\n"
        if details.get("bathrooms"): display += f"• Bathrooms: {details['bathrooms']}\n"
        if details.get("location"): display += f"• Location: {details['location']}\n"
        if details.get("amenities"): display += f"• Amenities: {', '.join(details['amenities'])}\n"
        return display
    
    elif goal_type == "vacation" and details:
        display = f"🏖️ **Vacation Details:**\n"
        if details.get("destination"): display += f"• Destination: {details['destination']}\n"
        if details.get("duration"): display += f"• Duration: {details['duration']}\n"
        if details.get("travelers"): display += f"• Travelers: {details['travelers']}\n"
        if details.get("travel_style"): display += f"• Style: {details['travel_style']}\n"
        if details.get("activities"): display += f"• Activities: {', '.join(details['activities'][:3])}{'...' if len(details['activities']) > 3 else ''}\n"
        return display
    
    elif goal_type == "electronics" and details:
        display = f"💻 **Electronics Details:**\n"
        if details.get("device_type"): display += f"• Device: {details['device_type']}\n"
        if details.get("brand"): display += f"• Brand: {details['brand']}\n"
        if details.get("usage"): display += f"• Primary Use: {details['usage']}\n"
        if details.get("budget_range"): display += f"• Budget Range: {details['budget_range']}\n"
        return display
    
    elif goal_type == "wedding" and details:
        display = f"💍 **Wedding Details:**\n"
        if details.get("wedding_style"): display += f"• Style: {details['wedding_style']}\n"
        if details.get("guest_count"): display += f"• Guests: {details['guest_count']}\n"
        if details.get("venue_type"): display += f"• Venue: {details['venue_type']}\n"
        if details.get("wedding_date"): display += f"• Timeline: {details['wedding_date']}\n"
        return display
    
    elif goal_type == "education" and details:
        display = f"🎓 **Education Details:**\n"
        if details.get("education_type"): display += f"• Type: {details['education_type']}\n"
        if details.get("field_of_study"): display += f"• Field: {details['field_of_study']}\n"
        if details.get("duration"): display += f"• Duration: {details['duration']}\n"
        if details.get("study_mode"): display += f"• Mode: {details['study_mode']}\n"
        return display
    
    elif goal_type == "emergency_fund" and details:
        display = f"💰 **Emergency Fund Details:**\n"
        if details.get("target_months"): display += f"• Coverage: {details['target_months']}\n"
        if details.get("monthly_expenses"): display += f"• Monthly Expenses: RM{details['monthly_expenses']:.2f}\n"
        if details.get("storage_preference"): display += f"• Storage: {details['storage_preference']}\n"
        return display
    
    return ""

def add_goal_contribution(goal_id, user_email, amount, note=""):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        contribution_date = datetime.now().strftime("%Y-%m-%d")
        
        # Add contribution record
        c.execute("""
            INSERT INTO goal_contributions (goal_id, user_email, amount, contribution_date, note) 
            VALUES (?, ?, ?, ?, ?)
        """, (goal_id, user_email, amount, contribution_date, note))
        
        # Update goal current amount
        c.execute("UPDATE goals SET current_amount = current_amount + ? WHERE id = ?", (amount, goal_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error adding contribution: {str(e)}")
        return False

def get_goal_progress(goal):
    """Calculate goal progress with friendly status messages"""
    target_amount = goal["target_amount"]
    current_amount = goal["current_amount"]
    target_date = datetime.strptime(goal["target_date"], "%Y-%m-%d")
    today = datetime.now()
    
    # Calculate progress percentage
    progress_percent = (current_amount / target_amount) * 100 if target_amount > 0 else 0
    
    # Calculate remaining amount and days
    remaining_amount = target_amount - current_amount
    days_remaining = (target_date - today).days
    
    # Calculate required monthly savings
    months_remaining = max(1, days_remaining / 30.44)  # Average days per month
    required_monthly = remaining_amount / months_remaining if months_remaining > 0 else remaining_amount
    
    # Determine friendly status messages
    if progress_percent >= 100:
        status = "🎉 Goal Achieved!"
        status_msg = "Congratulations! You did it! 🏆"
        status_color = "success"
    elif days_remaining < 0:
        status = "⏰ Past Due Date"
        status_msg = "Don't worry! You can still reach this goal - maybe adjust the date? 💪"
        status_color = "error"
    elif progress_percent >= 90:
        status = "🔥 Almost There!"
        status_msg = "You're so close! Keep pushing - you've got this! 🌟"
        status_color = "success"
    elif progress_percent >= 75:
        status = "🟢 Excellent Progress!"
        status_msg = "You're doing fantastic! Stay consistent and you'll nail this! 👏"
        status_color = "success"
    elif progress_percent >= 50:
        status = "🟡 Good Progress"
        status_msg = "You're halfway there! Keep up the momentum! 📈"
        status_color = "warning"
    elif progress_percent >= 25:
        status = "🟠 Getting Started"
        status_msg = "Nice start! Every step counts towards your goal! 🚀"
        status_color = "warning"
    else:
        status = "🔴 Just Beginning"
        status_msg = "No worries! Every journey starts with a first step! Let's build momentum! 💫"
        status_color = "error"
    
    return {
        "progress_percent": min(100, progress_percent),
        "remaining_amount": max(0, remaining_amount),
        "days_remaining": days_remaining,
        "months_remaining": months_remaining,
        "required_monthly": required_monthly,
        "status": status,
        "status_msg": status_msg,
        "status_color": status_color
    }

def show_goals_status(user_email):
    """
    Show user's goals status, one by one, with advanced breakdowns.
    Only shows the three main goals:
      - Buy New Car
      - Buy New House
      - Go To Travel
    """
    # Get user's goals
    all_goals = get_user_goals(user_email)

    print("DEBUG: All goals loaded from DB:")
    for i, goal in enumerate(all_goals):
        print(f"{i+1}. goal_type: {repr(goal.get('goal_type'))}, goal_name: {repr(goal.get('goal_name'))}")
        print("   FULL GOAL DICT:", goal)

    # Only keep the three main goals (case-insensitive match)
    main_goal_types = [
    "buy new car", "buy car", "car",
    "buy new house", "buy house", "house",
    "go to travel", "travel", "vacation", "trip"
    ]
    goals = [
    goal for goal in all_goals
    if any(main_type in goal["goal_type"].lower() for main_type in main_goal_types)
    or any(main_type in goal["goal_name"].lower() for main_type in main_goal_types)
    ]

    # If none, prompt to set one
    if not goals:
        return (
            "🚗🏠✈️ **No major goals found!**\n\n"
            "You haven't set any of the main goals yet: Buy New Car, Buy New House, Go To Travel.\n\n"
            "Ready to plan your dreams? Just say 'set a goal for car', 'set a goal for house', or 'set a goal for travel'!"
        )

    # Sort by goal_type (car, house, travel)
    def goal_sorter(goal):
        # Put car, house, travel in this order
        for i, typ in enumerate(main_goal_types):
            if goal["goal_type"].lower() == typ or typ in goal["goal_name"].lower():
                return i
        return 99
    goals = sorted(goals, key=goal_sorter)

    # Build response: status for each goal, one by one
    response = "🎯 **Your Main Goals Status**\n\n"
    emoji_map = {
        "buy new car": "🚗",
        "buy new house": "🏠",
        "go to travel": "✈️"
    }
    for goal in goals:
        # Progress details
        progress = get_enhanced_goal_progress(goal)
        emoji = None
        # Use emoji from map, fallback to 🎯
        for typ, em in emoji_map.items():
            if typ in goal["goal_type"].lower() or typ in goal["goal_name"].lower():
                emoji = em
                break
        if not emoji:
            emoji = "🎯"

        response += f"{emoji} **{goal['goal_name']}**\n"
        response += f"├ Target: RM{goal['target_amount']:.2f}\n"
        response += f"├ Saved: RM{goal['current_amount']:.2f} ({progress['progress_percent']:.1f}%)\n"
        response += f"├ Remaining: RM{progress['remaining_amount']:.2f}\n"
        response += f"├ Status: {progress['status']}\n"
        response += f"├ Days left: {progress['days_remaining']}\n"
        response += f"├ Monthly needed: RM{progress['weekly_target']*4:.2f} (weekly: RM{progress['weekly_target']:.2f})\n"
        response += f"└ {progress['status_msg']}\n\n"

        # Motivational tip for each
        if progress["progress_percent"] < 25:
            response += "💡 Tip: Start with a small transfer each week to build momentum!\n"
        elif progress["progress_percent"] < 75:
            response += "💪 Keep your eye on the prize - steady contributions win!\n"
        else:
            response += "🚀 You're almost there! Push a bit more and celebrate!\n"

        response += "\n"

    response += "✨ Want to add money to a goal? Just say 'add RMxxx to my car/house/travel goal'.\n"
    response += "🏆 Need help or want to set a new goal? Say 'set a goal'."

    return response

def get_goals_summary(user_email):
    """Get friendly summary of all goals for chat responses"""
    goals = get_user_goals(user_email)
    if not goals:
        return "Hey there! 😊 I don't see any goals set up yet, but that's totally fine - we all start somewhere!\n\n🎯 **Ready to turn your dreams into plans?** Setting financial goals is like having a roadmap to your future!\n\nI can help you save for anything:\n• 💰 Emergency fund (peace of mind!)\n• 🏖️ Amazing vacation\n• 🚗 That car you've been wanting\n• 🏠 Your dream home\n• 💻 Cool gadgets or tech\n• 🎓 Education or courses\n• 💍 Special occasions\n\nJust say **'set a goal'** and let's make your dreams happen! What do you say? ✨"
    
    summary = f"**Your Financial Goals Journey** 🎯✨\n\n"
    
    total_goals = len(goals)
    completed_goals = sum(1 for goal in goals if get_goal_progress(goal)["progress_percent"] >= 100)
    
    # Add encouraging header
    if completed_goals > 0:
        summary += f"🏆 **Amazing!** You've completed {completed_goals} out of {total_goals} goals! You're a goal-crushing machine! 💪\n\n"
    else:
        summary += f"📈 **You're working on {total_goals} goal{'s' if total_goals > 1 else ''}!** Every step forward is progress! 🌟\n\n"
    
    for goal in goals:
        progress = get_goal_progress(goal)
        summary += f"**{goal['goal_name']}** ({goal['goal_type'].replace('_', ' ').title()})\n"
        summary += f"├ Target: RM{goal['target_amount']:.2f}\n"
        summary += f"├ Saved: RM{goal['current_amount']:.2f} ({progress['progress_percent']:.1f}%)\n"
        summary += f"├ Remaining: RM{progress['remaining_amount']:.2f}\n"
        summary += f"└ Status: {progress['status']}\n"
        summary += f"  💭 {progress['status_msg']}\n\n"
    
    # Add motivational closing
    summary += "🚀 **Keep going!** You're building an amazing financial future! Want to add money to any goal or create a new one? I'm here to help! 😊"
    return summary

def find_goal_by_name(user_email, goal_name_partial):
    """Find goal by partial name match for contributions"""
    goals = get_user_goals(user_email)
    goal_name_lower = goal_name_partial.lower()
    
    # Try exact match first
    for goal in goals:
        if goal_name_lower == goal["goal_name"].lower():
            return goal
    
    # Try partial match
    for goal in goals:
        if goal_name_lower in goal["goal_name"].lower() or goal["goal_name"].lower() in goal_name_lower:
            return goal
    
    return None

def is_category_change_request(text):
    """
    Check if the user is clearly requesting to change the category
    rather than just mentioning a category in a query
    """
    change_keywords = ["change", "switch", "instead", "different", "set", "sorry", "actually", "want", "prefer"]
    query_keywords = ["how much", "what is", "show", "view", "check", "status", "remaining", "left", "spent", "my", "of my"]
    
    # If it contains change keywords, it's likely a change request
    has_change_keyword = any(keyword in text for keyword in change_keywords)
    
    # If it contains query keywords, it's likely a query, not a change request
    has_query_keyword = any(keyword in text for keyword in query_keywords)
    
    # It's a change request if it has change keywords AND doesn't have strong query indicators
    return has_change_keyword and not has_query_keyword

# Add this function near the extract_entities function
def extract_budget_entities(text):
    text = text.lower().strip()
    entities = {}
    
    # Budget patterns
    budget_patterns = [
        r"budget.*?(\$?[\d,.]+)\s*(?:rm)?\s*for (.+?)(?: for (january|february|march|april|may|june|july|august|september|october|november|december))?(?: (\d{4}))?",
        r"set.*?budget.*?(\$?[\d,.]+)\s*(?:rm)?\s*for (.+?)(?: for (january|february|march|april|may|june|july|august|september|october|november|december))?(?: (\d{4}))?",
        r"allocate.*?(\$?[\d,.]+)\s*(?:rm)?\s*for (.+?)(?: for (january|february|march|april|may|june|july|august|september|october|november|december))?(?: (\d{4}))?",
        r"(\$?[\d,.]+)\s*(?:rm)?\s*for (.+?)(?: budget)(?: for (january|february|march|april|may|june|july|august|september|october|november|december))?(?: (\d{4}))?",
        r"rm\s*(\d+\.?\d*)\s*for (.+?)(?: for (january|february|march|april|may|june|july|august|september|october|november|december))?(?: (\d{4}))?",
        r"set.*?(\w+)\s*budget",  # New pattern: "set transportation budget"
        r"budget.*?for (\w+)",    # New pattern: "budget for transportation"
    ]
    
    for pattern in budget_patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            
            # Handle patterns with amounts
            if pattern in [r"set.*?(\w+)\s*budget", r"budget.*?for (\w+)"]:
                # These are the new patterns that only extract category
                category_text = groups[0].strip()
                
                # Map to standard categories
                category_map = {
                    "food": "food", "groceries": "food", "eating": "food", "restaurant": "food",
                    "transport": "transport", "transportation": "transport", "gas": "transport", "fuel": "transport", "bus": "transport", "train": "transport", "taxi": "transport",
                    "entertainment": "entertainment", "movies": "entertainment", "games": "entertainment", "fun": "entertainment",
                    "shopping": "shopping", "clothes": "shopping", "items": "shopping", "purchases": "shopping",
                    "utilities": "utilities", "bills": "utilities", "electricity": "utilities", "water": "utilities", "internet": "utilities", "phone": "utilities",
                    "housing": "housing", "rent": "housing", "mortgage": "housing", "home": "housing",
                    "healthcare": "healthcare", "medical": "healthcare", "health": "healthcare", "doctor": "healthcare",
                    "education": "education", "school": "education", "books": "education", "courses": "education",
                    "other": "other", "misc": "other"
                }
                
                # Find the matching category
                entities["category"] = "other"
                for keyword, category_name in category_map.items():
                    if keyword in category_text:
                        entities["category"] = category_name
                        break
                
                break
            
            # Handle amount patterns (original code)
            amount_str = groups[0].replace('$', '').replace('RM', '').replace('rm', '').replace(',', '')
            
            try:
                entities["amount"] = float(amount_str)
            except ValueError:
                continue
            
            # Extract category from amount patterns
            category_text = groups[1].strip()
            
            # Map to standard categories
            category_map = {
                "food": "food", "groceries": "food", "eating": "food", "restaurant": "food",
                "transport": "transport", "transportation": "transport", "gas": "transport", "fuel": "transport", "bus": "transport", "train": "transport", "taxi": "transport",
                "entertainment": "entertainment", "movies": "entertainment", "games": "entertainment", "fun": "entertainment",
                "shopping": "shopping", "clothes": "shopping", "items": "shopping", "purchases": "shopping",
                "utilities": "utilities", "bills": "utilities", "electricity": "utilities", "water": "utilities", "internet": "utilities", "phone": "utilities",
                "housing": "housing", "rent": "housing", "mortgage": "housing", "home": "housing",
                "healthcare": "healthcare", "medical": "healthcare", "health": "healthcare", "doctor": "healthcare",
                "education": "education", "school": "education", "books": "education", "courses": "education",
                "other": "other", "misc": "other"
            }
            
            # Find the matching category
            entities["category"] = "other"
            for keyword, category_name in category_map.items():
                if keyword in category_text:
                    entities["category"] = category_name
                    break
            
            # Extract month if specified
            if len(groups) > 2 and groups[2]:
                month_map = {
                    "jan": "January", "january": "January",
                    "feb": "February", "february": "February",
                    "mar": "March", "march": "March",
                    "apr": "April", "april": "April",
                    "may": "May",
                    "jun": "June", "june": "June",
                    "jul": "July", "july": "July",
                    "aug": "August", "august": "August",
                    "sep": "September", "september": "September",
                    "oct": "October", "october": "October",
                    "nov": "November", "november": "November",
                    "dec": "December", "december": "December"
                }
                month_lower = groups[2].lower()
                entities["month"] = month_map.get(month_lower, datetime.now().strftime("%B"))
            
            # Extract year if specified
            if len(groups) > 3 and groups[3]:
                try:
                    entities["year"] = int(groups[3])
                except ValueError:
                    pass
            
            break
    
    return entities

# Function to set a budget
def set_budget(user_email, category, amount, month, year):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if budget already exists for this category/month/year
        c.execute("SELECT id FROM budgets WHERE user_email = ? AND category = ? AND month = ? AND year = ?",
                (user_email, category, month, year))
        existing = c.fetchone()
        
        if existing:
            # Update existing budget
            c.execute("UPDATE budgets SET amount = ? WHERE id = ?", (amount, existing[0]))
        else:
            # Create new budget
            c.execute("INSERT INTO budgets (user_email, category, amount, month, year) VALUES (?, ?, ?, ?, ?)",
                    (user_email, category, amount, month, year))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error setting budget: {str(e)}")
        return False

# Function to get user's budgets
def get_budgets(user_email, month=None, year=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if month and year:
        c.execute("SELECT * FROM budgets WHERE user_email = ? AND month = ? AND year = ?",
                 (user_email, month, year))
    else:
        current_month = datetime.now().strftime("%B")
        current_year = datetime.now().year
        c.execute("SELECT * FROM budgets WHERE user_email = ? AND month = ? AND year = ?",
                 (user_email, current_month, current_year))
    
    budgets = c.fetchall()
    conn.close()
    
    # Convert to list of dicts
    budget_list = []
    for budget in budgets:
        budget_list.append({
            "id": budget[0],
            "category": budget[2],
            "amount": budget[3],
            "month": budget[4],
            "year": budget[5]
        })
    
    return budget_list

def show_budget_status(user_email):
    """
    Show user's budget status with current spending - DEBUGGED VERSION
    """
    current_month = datetime.now().strftime("%B")
    current_year = datetime.now().year
    
    print(f"DEBUG: Looking for budgets for user: {user_email}")
    print(f"DEBUG: Current month: {current_month}, Current year: {current_year}")
    
    # Get budgets with debugging
    budgets = get_budgets(user_email, current_month, current_year)
    print(f"DEBUG: Found {len(budgets)} budgets: {budgets}")
    
    if not budgets:
        # Let's also check if budgets exist with different month/year formats
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            # Check all budgets for this user
            c.execute("SELECT * FROM budgets WHERE user_email = ?", (user_email,))
            all_user_budgets = c.fetchall()
            print(f"DEBUG: All budgets for user: {all_user_budgets}")
            
            # Check what months are in database
            c.execute("SELECT DISTINCT month, year FROM budgets WHERE user_email = ?", (user_email,))
            month_years = c.fetchall()
            print(f"DEBUG: Available month/year combinations: {month_years}")
            
            conn.close()
            
        except Exception as e:
            print(f"DEBUG: Database error: {e}")
        
        response = f"📊 **Budget Overview for {current_month} {current_year}**\n\n"
        response += "No budgets set up yet! 💰\n\n"
        response += "🎯 **Ready to take control of your spending?**\n\n"
        response += "Setting up budgets helps you:\n"
        response += "• Track your spending by category\n"
        response += "• Stay within your financial limits\n"
        response += "• Build better money habits\n"
        response += "• Reach your financial goals faster\n\n"
        response += "💡 **Get started:** Just say 'set budget' and I'll walk you through it step by step!\n\n"
        response += "What category would you like to budget for first? 😊"
        return response
    
    # Get spending for comparison
    spending = get_spending_by_category(user_email, current_month, current_year)
    print(f"DEBUG: Spending data: {spending}")
    
    response = f"📊 **Budget Overview for {current_month} {current_year}**\n\n"
    
    total_budget = sum(budget["amount"] for budget in budgets)
    total_spent = sum(spending.values()) if spending else 0
    
    response += f"💰 **Overall Summary:**\n"
    response += f"• Total Budget: RM{total_budget:.2f}\n"
    response += f"• Total Spent: RM{total_spent:.2f}\n"
    response += f"• Remaining: RM{total_budget - total_spent:.2f}\n\n"
    
    response += "📋 **Budget Details:**\n\n"
    
    # Show each budget category
    for budget in budgets:
        category = budget["category"]
        budget_amount = budget["amount"]
        spent = spending.get(category, 0) if spending else 0
        remaining = budget_amount - spent
        percent_used = (spent / budget_amount) * 100 if budget_amount > 0 else 0
        
        # Determine status with emojis
        if percent_used < 50:
            status = "🟢 Excellent"
        elif percent_used < 80:
            status = "🟡 Good"
        elif percent_used < 100:
            status = "🟠 Watch Out"
        else:
            status = "🔴 Over Budget"
        
        response += f"**{category.title()}**\n"
        response += f"├ Budget: RM{budget_amount:.2f}\n"
        response += f"├ Spent: RM{spent:.2f} ({percent_used:.1f}%)\n"
        response += f"├ Remaining: RM{remaining:.2f}\n"
        response += f"└ Status: {status}\n\n"
    
    # Add helpful tips
    over_budget_categories = [b["category"] for b in budgets if spending and spending.get(b["category"], 0) > b["amount"]]
    
    if over_budget_categories:
        response += "⚠️ **Action Needed:**\n"
        response += f"You're over budget in: {', '.join([cat.title() for cat in over_budget_categories])}\n\n"
        response += "💡 **Tips:**\n"
        response += "• Review recent expenses in these categories\n"
        response += "• Look for areas to cut back\n"
        response += "• Consider adjusting your budget if needed\n\n"
    else:
        response += "🎉 **Great job!** You're staying within all your budgets!\n\n"
    
    response += "🔧 **Want to make changes?**\n"
    response += "• Say 'set budget' to create new budgets\n"
    response += "• Ask 'show food budget' for specific categories\n"
    response += "• Say 'help' for more options"
    
    return response

def show_specific_budget(user_email, category):
    """
    Show budget for a specific category, or offer to create one if it doesn't exist
    """
    debug_budget_database(user_email)
    
    current_month = datetime.now().strftime("%B")
    current_year = datetime.now().year
    
    print(f"DEBUG: Looking for budgets for user: {user_email}")
    
    # Get all budgets for the user
    budgets = get_budgets(user_email, current_month, current_year)
    
    # Find the specific category budget
    category_budget = None
    for budget in budgets:
        if budget["category"].lower() == category.lower():
            category_budget = budget
            break
    
    if not category_budget:
        # Category budget doesn't exist - offer to create it
        response = f"💡 **{category.title()} Budget for {current_month} {current_year}**\n\n"
        response += f"You haven't set a {category.lower()} budget yet! 📊\n\n"
        response += f"🎯 **Want to set your {category.lower()} budget?**\n\n"
        response += f"Setting a {category.lower()} budget will help you:\n"
        response += f"• Track your {category.lower()} spending\n"
        response += f"• Stay within your financial limits\n"
        response += f"• Build better spending habits\n"
        response += f"• Reach your financial goals faster\n\n"
        response += f"💰 **Ready to get started?** Just say 'set {category.lower()} budget' and I'll walk you through it!\n\n"
        response += f"Or say 'set budget' to choose from all categories. What sounds good? 😊"
        return response
    
    # Category budget exists - show detailed info
    spending = get_spending_by_category(user_email, current_month, current_year)
    
    budget_amount = category_budget["amount"]
    spent = spending.get(category.lower(), 0)
    remaining = budget_amount - spent
    percent_used = (spent / budget_amount) * 100 if budget_amount > 0 else 0
    
    # Determine status with emojis
    if percent_used < 50:
        status = "🟢 Excellent"
        status_msg = "You're doing great! Keep it up! 👏"
    elif percent_used < 80:
        status = "🟡 Good"
        status_msg = "You're on track! Stay mindful of your spending. 👍"
    elif percent_used < 100:
        status = "🟠 Watch Out"
        status_msg = "Getting close to your limit! Time to be careful. ⚠️"
    else:
        status = "🔴 Over Budget"
        status_msg = f"You're over budget by RM{abs(remaining):.2f}! Time to review your spending. 🚨"
    
    response = f"📊 **{category.title()} Budget for {current_month} {current_year}**\n\n"
    
    response += f"💰 **Budget Summary:**\n"
    response += f"• Budget: RM{budget_amount:.2f}\n"
    response += f"• Spent: RM{spent:.2f} ({percent_used:.1f}%)\n"
    response += f"• Remaining: RM{remaining:.2f}\n"
    response += f"• Status: {status}\n\n"
    
    response += f"💭 **{status_msg}**\n\n"
    
    # Add progress bar visualization
    progress_bars = int(percent_used / 10)
    remaining_bars = 10 - progress_bars
    progress_visual = "█" * progress_bars + "░" * remaining_bars
    response += f"📈 **Progress:** {progress_visual} {percent_used:.1f}%\n\n"
    
    # Add specific tips based on status
    if percent_used >= 100:
        response += "🆘 **Action Needed:**\n"
        response += f"• Review your recent {category.lower()} expenses\n"
        response += f"• Look for ways to cut back on {category.lower()} spending\n"
        response += f"• Consider increasing your {category.lower()} budget if needed\n\n"
    elif percent_used >= 80:
        response += "⚡ **Tips to Stay on Track:**\n"
        response += f"• Be mindful of {category.lower()} purchases for the rest of the month\n"
        response += f"• Look for deals and discounts on {category.lower()}\n"
        response += f"• Consider postponing non-essential {category.lower()} expenses\n\n"
    else:
        response += "🎉 **You're doing great!**\n"
        response += f"• Keep up the good work with your {category.lower()} spending\n"
        response += f"• You have plenty of room left in your {category.lower()} budget\n\n"
    
    response += "🔧 **Want to make changes?**\n"
    response += f"• Say 'set {category.lower()} budget' to update this budget\n"
    response += "• Say 'show budget' to see all your budgets\n"
    response += "• Say 'help' for more options"
    
    return response

def debug_budget_database(user_email):
    """
    Debug function to check budget database structure
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        print("=== BUDGET DATABASE DEBUG ===")
        
        # Check table structure
        c.execute("PRAGMA table_info(budgets)")
        columns = c.fetchall()
        print(f"Budget table columns: {columns}")
        
        # Check all budgets for user
        c.execute("SELECT * FROM budgets WHERE user_email = ?", (user_email,))
        user_budgets = c.fetchall()
        print(f"All budgets for {user_email}: {user_budgets}")
        
        # Check all budgets in database
        c.execute("SELECT * FROM budgets LIMIT 10")
        all_budgets = c.fetchall()
        print(f"First 10 budgets in database: {all_budgets}")
        
        conn.close()
        
    except Exception as e:
        print(f"DEBUG ERROR: {e}")

def handle_goal_conversation(user_email, input_text):
    """
    Enhanced goal conversation handler with destination-specific responses and human-like personality
    """
    input_lower = input_text.lower()
    
    # Detect goal type and timeframe
    goal_type = None
    timeframe = None
    destination = None
    
    # Detect goal type
    if any(car_word in input_lower for car_word in ["car", "vehicle", "auto"]):
        goal_type = "Buy New Car"
    elif any(house_word in input_lower for house_word in ["house", "home", "property"]):
        goal_type = "Buy New House"  
    elif any(travel_word in input_lower for travel_word in ["travel", "trip", "vacation", "holiday"]):
        goal_type = "Go To Travel"
        
        # Detect specific travel destinations with enthusiastic responses
        destinations = {
            "japan": {
                "response": "🇯🇵 **WOW, JAPAN!** What an incredible choice! 🌸\n\nJapan is absolutely magical - from the cherry blossoms in spring to the snow-capped mountains in winter! You'll experience amazing sushi, fascinating culture, beautiful temples, and the most polite people in the world! 🍣⛩️\n\nPlus, you can visit Tokyo's bustling streets, Kyoto's serene temples, and maybe even see Mount Fuji! This is going to be an unforgettable adventure! ✨",
                "budget_note": "Japan can range from budget-friendly to luxury - hostels and local food can keep costs down, while ryokans and fine dining can make it more expensive!"
            },
            "china": {
                "response": "🇨🇳 **CHINA - WOW!** What an amazing destination! 🐉\n\nChina is going to blow your mind! From the incredible Great Wall to the bustling streets of Shanghai, the ancient Forbidden City in Beijing, and the stunning landscapes of Guilin! 🏯🏔️\n\nYou'll taste authentic dim sum, explore thousands of years of history, and see some of the world's most incredible architecture! The contrast between ancient traditions and ultra-modern cities is absolutely fascinating! 🥟✨",
                "budget_note": "China offers great value for money - you can eat like a king for very little, and transportation is very affordable!"
            },
            "korea": {
                "response": "🇰🇷 **SOUTH KOREA - AMAZING CHOICE!** 🌟\n\nK-pop, Korean BBQ, beautiful palaces, and the most advanced technology in the world! Seoul is such a vibrant city with incredible nightlife, shopping, and food! 🍖🎵\n\nPlus you can visit Jeju Island, explore traditional hanbok culture, try authentic kimchi, and experience the famous Korean skincare! This trip is going to be absolutely fantastic! 💄✨",
                "budget_note": "Korea has excellent value - street food is amazing and cheap, and public transport is super efficient!"
            },
            "europe": {
                "response": "🇪🇺 **EUROPE - OH MY GOODNESS!** This is going to be epic! 🏰\n\nWhether you're thinking Paris, Rome, London, Amsterdam, or backpacking through multiple countries - Europe has EVERYTHING! Incredible history, world-class museums, stunning architecture, amazing food, and diverse cultures! 🥐🍝🧀\n\nYou could see the Eiffel Tower, the Colosseum, Big Ben, or explore charming small towns and breathtaking landscapes! This is a trip of a lifetime! ✨",
                "budget_note": "Europe can vary widely - Eastern Europe is very budget-friendly, while Western Europe is pricier but totally worth it!"
            },
            "thailand": {
                "response": "🇹🇭 **THAILAND - SUCH A PERFECT CHOICE!** 🏝️\n\nAmazing beaches, incredible street food, beautiful temples, and the friendliest people! From bustling Bangkok to peaceful islands like Phuket and Koh Samui - Thailand has it all! 🍜🏖️\n\nYou'll get amazing massages, try the most delicious pad thai and mango sticky rice, explore golden temples, and relax on pristine beaches! Plus, your money will go SO far there! 🥭⛩️",
                "budget_note": "Thailand is incredibly budget-friendly - you can live like royalty for very little money!"
            },
            "bali": {
                "response": "🇮🇩 **BALI - OMG YES!** This is going to be absolutely magical! 🌺\n\nBeautiful rice terraces, stunning beaches, incredible Hindu temples, amazing yoga retreats, and the most Instagram-worthy spots ever! Bali is pure paradise! 🧘‍♀️🏖️\n\nYou'll experience incredible Balinese culture, try amazing nasi goreng, get relaxing spa treatments, and witness the most beautiful sunsets! This trip will rejuvenate your soul! 🌅✨",
                "budget_note": "Bali offers amazing value - you can stay in beautiful places and eat incredibly well for very reasonable prices!"
            },
            "australia": {
                "response": "🇦🇺 **AUSTRALIA - MATE, THAT'S BRILLIANT!** 🦘\n\nFrom the iconic Sydney Opera House to the Great Barrier Reef, stunning beaches, unique wildlife, and vibrant cities! Australia is absolutely incredible! 🐨🏄‍♀️\n\nYou could surf at Bondi Beach, snorkel in the reef, see kangaroos and koalas, explore the Outback, or party in Melbourne! This is going to be an adventure of a lifetime! 🌊✨",
                "budget_note": "Australia can be pricey, but the experiences are absolutely worth it - consider working holiday visas if you're young!"
            },
            "singapore": {
                "response": "🇸🇬 **SINGAPORE - FANTASTIC CHOICE!** 🏙️\n\nIt's like stepping into the future! Amazing food courts, the incredible Gardens by the Bay, world-class shopping, and it's so clean and efficient! Plus, it's relatively close to Malaysia! 🌸🍜\n\nYou'll try the best chicken rice ever, explore amazing malls, see the stunning Marina Bay Sands, and experience multiple cultures in one city! 🏗️✨",
                "budget_note": "Singapore can be expensive, but there are plenty of affordable hawker centers with incredible food!"
            }
        }
        
        # Check for destination matches
        for dest_key, dest_info in destinations.items():
            if dest_key in input_lower or any(alias in input_lower for alias in [dest_key]):
                destination = dest_key
                break
        
        # Also check for broader terms
        if not destination:
            if any(term in input_lower for term in ["paris", "france"]):
                destination = "europe"
            elif any(term in input_lower for term in ["london", "uk", "england"]):
                destination = "europe"
            elif any(term in input_lower for term in ["rome", "italy"]):
                destination = "europe"
            elif any(term in input_lower for term in ["seoul", "korean"]):
                destination = "korea"
            elif any(term in input_lower for term in ["tokyo", "japanese"]):
                destination = "japan"
            elif any(term in input_lower for term in ["sydney", "melbourne"]):
                destination = "australia"
            elif any(term in input_lower for term in ["beijing", "shanghai", "chinese"]):
                destination = "china"
            elif any(term in input_lower for term in ["bangkok", "phuket"]):
                destination = "thailand"
    
    # Detect timeframe
    import re
    time_patterns = [
        r"(\d+)\s*month[s]?\s*later",
        r"(\d+)\s*year[s]?\s*later", 
        r"in\s*(\d+)\s*month[s]?",
        r"in\s*(\d+)\s*year[s]?",
        r"next\s*year",
        r"(\d+)\s*month[s]?\s*from\s*now"
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, input_lower)
        if match:
            if "month" in pattern:
                timeframe = f"{match.group(1)} months"
            elif "year" in pattern or "next year" in input_lower:
                if "next year" in input_lower:
                    timeframe = "1 year"
                else:
                    timeframe = f"{match.group(1)} years"
            break
    
    if goal_type and timeframe:
        # Start goal conversation with detected info
        st.session_state.goal_conversation = {
            "stage": "ask_amount",
            "goal_type": goal_type,
            "timeframe": timeframe,
            "destination": destination
        }
        
        response = f"🎯 **Amazing! I love that you're planning ahead!**\n\n"
        
        if goal_type == "Go To Travel" and destination:
            # Use destination-specific response
            dest_info = destinations.get(destination)
            
            if dest_info:
                response += dest_info["response"] + "\n\n"
                response += f"🎯 **Planning Timeline:** {timeframe}\n\n"
                response += f"💰 **Now, let's talk budget!** How much do you think you'll need for this incredible {destination.title()} adventure?\n\n"
                response += f"💡 **Budget Guide:**\n"
                response += f"• Budget trip: RM 3,000 - 5,000\n"
                response += f"• Comfortable trip: RM 6,000 - 10,000\n"
                response += f"• Luxury experience: RM 12,000 - 20,000+\n\n"
                response += dest_info["budget_note"] + "\n\n"
            else:
                response += f"So you want to **travel** in **{timeframe}** - that's a fantastic goal! ✈️✨\n\n"
                response += f"💰 **How much do you think you'll need to save for your amazing trip?**\n\n"
                response += f"For example:\n"
                response += f"• RM 3,000 for local/regional travel\n"
                response += f"• RM 8,000 for international travel\n"
                response += f"• RM 15,000 for luxury travel\n\n"
        else:
            response += f"So you want to **{goal_type.lower()}** in **{timeframe}** - that's a fantastic goal! 🚗✨\n\n"
            response += f"💰 **How much do you think you'll need to save for your {goal_type.lower()}?**\n\n"
            response += f"For example:\n"
            
            if goal_type == "Buy New Car":
                response += f"• RM 50,000 for a decent car\n"
                response += f"• RM 80,000 for a good car\n"
                response += f"• RM 120,000 for a premium car\n\n"
            elif goal_type == "Buy New House":
                response += f"• RM 300,000 for a starter home\n"
                response += f"• RM 500,000 for a nice house\n"
                response += f"• RM 800,000 for a dream home\n\n"
        
        response += f"💡 **Just tell me the amount** and I'll help you create a savings plan!\n\n"
        response += f"🚫 **Want to start over?** Just say **'cancel'** anytime!"
        
        return response
    
    else:
        # If we can't detect specific details, ask for clarification
        response = f"🎯 **I love that you want to set a goal!**\n\n"
        response += f"Let me help you plan this properly! I can help you save for:\n\n"
        response += f"🚗 **Buy New Car** - get that reliable ride you deserve!\n"
        response += f"🏠 **Buy New House** - your dream home awaits!\n"
        response += f"✈️ **Go To Travel** - explore the world and create memories!\n\n"
        response += f"**Which goal interests you most?** And when would you like to achieve it? 😊\n\n"
        response += f"🚫 **Want to cancel?** Just say **'cancel'** anytime!"
        
        return response
    
def save_goal_to_database(user_email, goal_type, goal_amount, timeframe, monthly_savings):
    """
    Save goal to database
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Create goals table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            goal_type TEXT NOT NULL,
            goal_amount REAL NOT NULL,
            timeframe TEXT NOT NULL,
            monthly_savings REAL NOT NULL,
            created_date TEXT NOT NULL,
            target_date TEXT NOT NULL,
            current_savings REAL DEFAULT 0
        )''')
        
        # Calculate target date
        from datetime import datetime, timedelta
        import calendar
        
        created_date = datetime.now().strftime("%Y-%m-%d")
        
        # Extract months from timeframe
        if "month" in timeframe:
            months = int(re.search(r'(\d+)', timeframe).group(1))
        elif "year" in timeframe:
            years = int(re.search(r'(\d+)', timeframe).group(1))
            months = years * 12
        else:
            months = 12
        
        # Calculate target date
        current_date = datetime.now()
        target_date = current_date + timedelta(days=months * 30)  # Approximate
        target_date_str = target_date.strftime("%Y-%m-%d")
        
        # Insert goal
        c.execute('''INSERT INTO goals 
                    (user_email, goal_type, goal_amount, timeframe, monthly_savings, created_date, target_date, current_savings)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (user_email, goal_type, goal_amount, timeframe, monthly_savings, created_date, target_date_str, 0))
        
        conn.commit()
        conn.close()
        
        print(f"Goal saved successfully for {user_email}")
        
    except Exception as e:
        print(f"Error saving goal: {e}")

# ------------------------------- Chatbot Intents Functions -------------------------------
# Function to save intents
def save_intents(intents_data):
    with open('intents.json', 'w', encoding='utf-8') as f:  
        json.dump(intents_data, f, indent=4, ensure_ascii=False)  

# Load intents from the intents.json file
@st.cache_resource
def load_intents():
    try:
        with open('intents.json', 'r', encoding='utf-8') as f:  # Add encoding='utf-8'
            return json.load(f)
    except FileNotFoundError:
        # Create a default intents.json file if it doesn't exist
        default_intents = {
            "intents": [
                {
                    "tag": "greeting",
                    "patterns": ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"],
                    "responses": [
                        "Hello! How can I help with your finances today?",
                        "Hi there! Ready to manage your money?",
                        "Hello! What would you like to do with your finances today?"
                    ]
                },
                {
                    "tag": "expense_add",
                    "patterns": [
                        "spent money on", "i spent", "spent", "spend",
                        "i paid", "buy", "bought", "RM", "purchased", 
                        "add expense", "record expense", "log expense",
                        "track spending", "paid for", "cost me", "cost"
                    ],
                    "responses": [
                        "I'll record that expense for you.",
                        "Got it, I've recorded your expense.",
                        "Your expense has been logged."
                    ]
                },
                {
                    "tag": "fallback",
                    "patterns": [],
                    "responses": ["I'm your personal finance assistant. Type 'help' to see what I can do."]
                }
            ]
        }
        save_intents(default_intents)
        return default_intents

# Load the intents
intents = load_intents()

# Function to predict the intent of a sentence using basic pattern matching
def predict_intent(sentence, intents_json):
    # Initialize variables
    highest_score = 0
    matched_intent = None
    
    # Simple pattern matching approach that doesn't rely heavily on NLTK
    input_words = set(word.lower() for word in sentence.split())
    
    # Check each intent
    for intent in intents_json["intents"]:
        score = 0
        max_pattern_score = 0
        
        # Check each pattern in the intent
        for pattern in intent["patterns"]:
            pattern_words = set(word.lower() for word in pattern.split())
            
            # Count matching words
            matching_words = input_words.intersection(pattern_words)
            if pattern_words:
                pattern_score = len(matching_words) / len(pattern_words)
            else:
                pattern_score = 0
            
            # Update max score for this intent
            max_pattern_score = max(max_pattern_score, pattern_score)
        
        # Use the best pattern match score for this intent
        score = max_pattern_score
        
        # If this intent has a better score, update the result
        if score > highest_score:
            highest_score = score
            matched_intent = intent["tag"]
    
    # If no match found or score too low, use fallback
    if matched_intent is None or highest_score < 0.2:
        matched_intent = "fallback"
    
    return matched_intent, highest_score

# Function to format responses with actual data
def format_response(response, entities, user_email):
    # Replace placeholders with actual values
    if "{amount:.2f}" in response and "amount" in entities:
        response = response.replace("{amount:.2f}", f"{entities['amount']:.2f}")
    
    if "{description}" in response and "description" in entities:
        response = response.replace("{description}", entities["description"])
    
    if "{category}" in response:
        if "category" in entities:
            category = entities["category"]
        elif "description" in entities:
            category = categorize_expense(entities["description"])
        else:
            category = "other"
        response = response.replace("{category}", category)
    
    # Add current month and year if needed
    current_month = datetime.now().strftime("%B")
    current_year = datetime.now().year
    
    if "{month}" in response:
        response = response.replace("{month}", current_month)
    
    if "{year}" in response:
        response = response.replace("{year}", str(current_year))
    
    # Replace expense placeholder with actual expense data
    if "{expenses}" in response:
        expenses = get_expenses(user_email, limit=5)
        if expenses:
            # Group by date for better organization
            grouped_expenses = {}
            for exp in expenses:
                date = exp["date"]
                if date not in grouped_expenses:
                    grouped_expenses[date] = []
                grouped_expenses[date].append(exp)
            
            # Format each date group
            expenses_text = ""
            for date in sorted(grouped_expenses.keys(), reverse=True):
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                    date_header = date_obj.strftime("%A, %B %d, %Y")
                    
                    expenses_for_date = grouped_expenses[date]
                    daily_total = sum(exp["amount"] for exp in expenses_for_date)
                    
                    expenses_text += f"**{date_header}** - Total: RM{daily_total:.2f}\n\n"
                    
                    for exp in expenses_for_date:
                        # Put each expense on its own line with proper indentation and spacing
                        expenses_text += f"• RM{exp['amount']:.2f} for **{exp['description']}** ({exp['category'].title()})\n\n"
                    
                    expenses_text += "\n"
                except Exception as e:
                    expenses_text += f"• Error with date {date}: {str(e)}\n\n"
        else:
            expenses_text = "No expenses recorded yet."
        response = response.replace("{expenses}", expenses_text)
    
     # Replace budget placeholder with actual budget data
    if "{budgets}" in response:
        budgets = get_budgets(user_email, current_month, current_year)
        if budgets:
            budgets_text = ""
            # Get spending for comparison
            spending = get_spending_by_category(user_email, current_month, current_year)
            
            for budget in budgets:
                category = budget["category"]
                budget_amount = budget["amount"]
                spent = spending.get(category, 0)
                remaining = budget_amount - spent
                percent_used = (spent / budget_amount) * 100 if budget_amount > 0 else 0
                
                status = "🟢 Good" if percent_used < 80 else "🟠 Watch" if percent_used < 100 else "🔴 Over"
                
                budgets_text += f"• **{category.title()}**: RM{spent:.2f} of RM{budget_amount:.2f} ({percent_used:.1f}%) - {status}\n\n"
        else:
            budgets_text = "No budgets set up yet."
        response = response.replace("{budgets}", budgets_text)
    
    # Replace spending placeholder with actual spending data
    if "{spending}" in response:
        spending = get_spending_by_category(user_email, current_month, current_year)
        if spending:
            spending_text = ""
            total = sum(spending.values())
            for category, amount in sorted(spending.items(), key=lambda x: x[1], reverse=True):
                percent = (amount / total) * 100 if total > 0 else 0
                spending_text += f"• **{category.title()}**: RM{amount:.2f} ({percent:.1f}% of total)\n\n"
            response = response.replace("{spending}", spending_text)
            
            # Replace total spending placeholder
            if "{total:.2f}" in response:
                response = response.replace("{total:.2f}", f"{total:.2f}")
        else:
            response = response.replace("{spending}", "No spending data available yet.")
            response = response.replace("{total:.2f}", "0.00")
    
    # Replace highest category placeholder with actual data
    if "{highest_category}" in response:
        spending = get_spending_by_category(user_email, current_month, current_year)
        if spending:
            highest_category = max(spending.items(), key=lambda x: x[1])
            response = response.replace("{highest_category}", highest_category[0])
        else:
            response = response.replace("{highest_category}", "any category")
    
    # Replace savings tips with category-specific tips
    if "{tips}" in response:
        spending = get_spending_by_category(user_email, current_month, current_year)
        if spending:
            highest_category = max(spending.items(), key=lambda x: x[1])[0]
            
            category_tips = {
                "food": [
                    "• Meal prep at home instead of eating out\n",
                    "• Use grocery store loyalty programs and coupons\n",
                    "• Make a shopping list and stick to it\n",
                    "• Buy non-perishable items in bulk when on sale\n"
                ],
                "transport": [
                    "• Consider carpooling or public transportation\n",
                    "• Combine errands to reduce trips\n",
                    "• Shop around for better car insurance rates\n",
                    "• Keep up with regular vehicle maintenance to avoid costly repairs\n"
                ],
                "entertainment": [
                    "• Look for free or low-cost events in your area\n",
                    "• Share streaming subscriptions with family or friends\n",
                    "• Check your library for free books, movies, and games\n",
                    "• Take advantage of discounts and happy hours\n"
                ],
                "shopping": [
                    "• Wait 24 hours before making non-essential purchases\n",
                    "• Shop during sales or with discount codes\n",
                    "• Consider buying second-hand for certain items\n",
                    "• Unsubscribe from retailer emails to avoid temptation\n"
                ],
                "utilities": [
                    "• Unsubscribe from retailer emails to avoid temptation\n",
                    "• Turn off lights and appliances when not in use\n",
                    "• Use energy-efficient appliances and light bulbs\n",
                    "• Adjust thermostat settings to save on heating/cooling\n",
                    "• Fix leaky faucets and pipes promptly\n",
                    "• Compare utility providers to find better rates\n"
                ],
                "housing": [
                    "• Consider a roommate to split housing costs\n",
                    "• Negotiate rent when renewing your lease\n",
                    "• Look for ways to reduce utility costs\n",
                    "• Do minor repairs yourself instead of hiring someone\n",
                    "• Consider refinancing your mortgage if interest rates are lower\n"
                ],
                "healthcare": [
                    "• Take advantage of preventive care covered by insurance\n",
                    "• Use generic medications when possible\n",
                    "• Ask about discount programs or payment plans\n",
                    "• Compare prices at different pharmacies\n",
                    "• Maintain healthy habits to prevent costly medical issues\n"
                ],
                "education": [
                    "• Look for scholarships and grants\n",
                    "• Buy used textbooks or rent them\n",
                    "• Take advantage of student discounts\n",
                    "• Consider community college courses that transfer to universities\n",
                    "• Explore online learning options which may be less expensive\n"
                ]
            }
            
            # Generic tips for categories not in our predefined list
            generic_tips = [
                "• Create a specific budget for this category\n",
                "• Track every expense to identify unnecessary spending\n",
                "• Look for more affordable alternatives\n",
                "• Consider if each purchase is a need or a want\n"
            ]
            
            # Get tips for the highest spending category or use generic tips
            tips = category_tips.get(highest_category, generic_tips)
            tips_text = "\n".join(tips)
            
            response = response.replace("{tips}", tips_text)
        else:
            generic_tips = [
                "• Create a budget for each spending category\n",
                "• Track all your expenses to identify patterns\n",
                "• Prioritize needs over wants\n",
                "• Build an emergency fund for unexpected expenses\n"
            ]
            response = response.replace("{tips}", "\n".join(generic_tips))
    
    # Replace $ with RM for Malaysian Ringgit
    response = response.replace("$", "RM")
    
    return response

# Function to get a response based on the intent with improved expense handling
def get_response(intent_tag, text, user_email):
    # Extract entities from the text
    entities = extract_entities(text)
    
    # Handle expense_add intent specifically to add to database
    if intent_tag == "expense_add" and "amount" in entities and "description" in entities:
        amount = entities["amount"]
        description = entities["description"]
        
        # Use the extracted category or categorize the description
        if "category" in entities:
            category = entities["category"]
        else:
            category = categorize_expense(description)
        
        # Add to database and get the ID
        success, expense_id = add_expense(user_email, amount, description, category)
        
        if success:
            # Store the expense in session state for potential category updates
            st.session_state.pending_expense = {
                "id": expense_id,
                "amount": amount,
                "description": description,
                "category": category
            }
            
            # Update the entities with the correct category for response formatting
            entities["category"] = category
            
            # Return confirmation question directly instead of using intents
            return f"I've recorded your expense: RM{amount:.2f} for {description} in the '{category}' category. Is that the right category?"
    
    # Find the intent in the intents list
    for intent in intents["intents"]:
        if intent["tag"] == intent_tag:
            # Get a response based on the intent format
            if isinstance(intent["responses"], dict):
                # For structured responses (like intents with sub-categories)
                first_key = list(intent["responses"].keys())[0]
                if intent["responses"][first_key]:
                    response = random.choice(intent["responses"][first_key])
                else:
                    response = "I understand. How can I help you further?"
            else:
                # For simple list responses
                if intent["responses"]:
                    response = random.choice(intent["responses"])
                else:
                    response = "I'm here to help with your finances."
            
            # Format the response with actual data
            return format_response(response, entities, user_email)
    
    # If no matching intent found, use fallback
    for intent in intents["intents"]:
        if intent["tag"] == "fallback":
            if isinstance(intent["responses"], list) and intent["responses"]:
                response = random.choice(intent["responses"])
            else:
                response = "I'm your personal finance assistant. How can I help you?"
            return format_response(response, entities, user_email)
    
    # Default response if no fallback is found
    return "I'm your personal finance assistant. You can ask me to record expenses, check your budget, or provide spending summaries. Type 'help' to see all the things I can do!"

def debug_intent_classification(input_text):
    """Debug function to see how intents are being classified"""
    intent_tag, confidence = predict_intent(input_text, intents)
    
    # Enhanced budget query detection
    input_lower = input_text.lower()
    
    # Check for GOAL intents first (ADD THIS SECTION)
    goal_set_indicators = [
        "set goal", "create goal", "new goal", "add goal", "save for", "saving goal",
        "want to save", "financial goal", "savings target", "set savings goal",
        "i want to save for", "help me save", "saving plan", "set target",
        "create savings goal", "make a goal", "i want to set goal", "want to set goal"
    ]
    
    goal_query_indicators = [
        "show goals", "view goals", "check goals", "goal progress", "how are my goals",
        "goals status", "my savings goals", "goal summary", "see goals", "what are my goals",
        "goal overview", "show goals", "my goal", "all goals", "check goal progress"
    ]
    
    goal_contribution_indicators = [
        "add to goal", "contribute to goal", "save money for", "put money towards",
        "add money to", "goal contribution", "save for my goal", "progress on goal"
    ]
    
    # Check for goal intents
    if any(indicator in input_lower for indicator in goal_set_indicators):
        return "goal_set", 0.9
    elif any(indicator in input_lower for indicator in goal_query_indicators):
        return "goal_query", 0.9
    elif any(indicator in input_lower for indicator in goal_contribution_indicators):
        return "goal_contribution", 0.9
    
    # Check if this should be budget_query instead of budget_set
    budget_query_indicators = [
        "show", "view", "check", "what is", "what's", "how is", "how's", 
        "status", "progress", "overview", "summary", "see my", "look at",
        "display", "current", "my budget"
    ]
    
    budget_set_indicators = [
        "set budget", "create budget", "make budget", "establish budget", "new budget",
        "setup budget", "allocate budget", "limit", "want to", "help me", "i need to"
    ]
    
    has_query_indicator = any(indicator in input_lower for indicator in budget_query_indicators)
    has_set_indicator = any(indicator in input_lower for indicator in budget_set_indicators)
    
    # Override intent if needed
    if has_query_indicator and not has_set_indicator and "budget" in input_lower:
        intent_tag = "budget_query"
    elif has_set_indicator and "budget" in input_lower:
        intent_tag = "budget_set"

def check_cancel_request(user_input):
    """Enhanced cancel detection with context awareness"""
    cancel_phrases = [
        "cancel", "stop", "nevermind", "never mind", "forget it", "quit", 
        "exit", "abort", "back", "restart", "start over", "clear", "reset",
        "no thanks", "not now", "maybe later", "skip this", "undo", "wrong",
        "i changed my mind", "this is wrong", "not what i want", "help me out"
    ]
    
    user_lower = user_input.lower().strip()
    
    # Direct cancel detection
    if any(phrase in user_lower for phrase in cancel_phrases):
        return True
        
    # Context-aware cancel (when user seems confused)
    confused_phrases = ["i don't understand", "this doesn't work", "confusing", "what?", "huh?"]
    if any(phrase in user_lower for phrase in confused_phrases):
        return True
        
    return False

def handle_cancel_request():
    """Human-like cancel handling with empathy"""
    # Clear all pending states
    for key in ["pending_expense", "correction_stage", "pending_multiple_expenses", 
                "expense_change_mode", "budget_conversation", "goal_conversation"]:
        if key in st.session_state:
            st.session_state[key] = None
    
    # Count cancels for adaptive responses
    if "cancel_count" not in st.session_state:
        st.session_state.cancel_count = 0
    st.session_state.cancel_count += 1
    
    # Adaptive cancel responses
    if st.session_state.cancel_count == 1:
        return "No worries at all! 😊 I completely understand.\n\nLet's start fresh - what would you like to do?\n• Track spending: 'I spent RM20 on lunch'\n• Check budget: 'show my budget'\n• Set goals: 'I want to save for vacation'\n\nJust speak naturally - I'm here to help! ✨"
    
    elif st.session_state.cancel_count <= 3:
        return "Of course! 🤗 Sometimes we need to step back and that's perfectly fine.\n\nI'm here whenever you're ready. Want to try something simple?\n• 'RM15 coffee' (quick expense)\n• 'help' (see what I can do)\n• Just ask me anything about your money! 💭"
    
    else:
        return "Hey there! 💙 I notice we've restarted a few times - no problem at all!\n\nMaybe I'm overcomplicating things? Let's keep it super simple:\n\n📝 **Just tell me naturally:**\n• 'I bought lunch for RM25'\n• 'Show me my spending'\n• 'Help me save money'\n\nI'm here to make your life easier, not harder! What feels right to you? 😊"

def suggest_typo_corrections(user_input):
    """Smart typo detection and suggestions"""
    common_finance_words = [
        "spent", "spend", "paid", "bought", "cost", "price", "money", "budget", 
        "goal", "save", "saving", "expense", "income", "salary", "food", "lunch", 
        "dinner", "transport", "shopping", "entertainment", "utilities", "housing",
        "show", "view", "check", "help", "cancel", "set", "create", "add"
    ]
    
    words = user_input.lower().split()
    suggestions = []
    
    for word in words:
        if len(word) > 3:  # Only check longer words
            matches = difflib.get_close_matches(word, common_finance_words, n=1, cutoff=0.6)
            if matches and matches[0] != word:
                suggestions.append(f"'{word}' → '{matches[0]}'")
    
    return suggestions

def get_category_from_input(text):
    """Smart category extraction from input text"""
    text = text.lower()
    category_map = {
        "food": ["food", "grocery", "groceries", "restaurant", "meal", "dining", "eat", "lunch", "dinner", "breakfast"],
        "transport": ["transport", "bus", "train", "taxi", "car", "travel", "commute", "gas", "fuel", "drive"],
        "entertainment": ["entertainment", "movie", "game", "fun", "show", "streaming", "netflix", "cinema"],
        "shopping": ["shopping", "clothes", "mall", "store", "fashion", "purchase", "stuff"],
        "utilities": ["utilities", "bill", "electric", "water", "internet", "phone", "wifi"],
        "housing": ["housing", "rent", "mortgage", "home", "apartment", "house", "accommodation"],
        "healthcare": ["health", "medical", "doctor", "hospital", "medicine", "clinic", "pharmacy"],
        "education": ["education", "school", "book", "tuition", "learn", "course", "study", "university"],
        "other": ["other", "misc", "miscellaneous"]
    }
    for cat, keywords in category_map.items():
        for word in keywords:
            if word in text:
                return cat
    return "other"

def get_month_from_input(text):
    """Extract month name from text or default to current"""
    months = ["january","february","march","april","may","june","july","august","september","october","november","december"]
    text = text.lower()
    for m in months:
        if m in text:
            return m.title()
    return datetime.now().strftime("%B")

def get_year_from_input(text):
    """Extract year from text or default to current"""
    year_match = re.search(r'(20\d{2})', text)
    if year_match:
        return int(year_match.group(1))
    return datetime.now().year

def get_amount_from_input(text):
    """Extract numeric budget amount from text"""
    amount_match = re.search(r'(\d+\.?\d*)', text.replace(',', ''))
    if amount_match:
        try:
            return float(amount_match.group(1))
        except:
            return None
    return None

def process_budget_conversation(input_text, user_email):
    """Advanced budget setting conversation handler with friendly revision flow"""
    conv = st.session_state.budget_conversation
    stage = conv.get("stage", "ask_category")
    input_lower = input_text.lower().strip()

    # Cancel logic
    if any(word in input_lower for word in ["cancel", "stop", "quit", "exit", "abort"]):
        del st.session_state.budget_conversation
        return "No problem! Budget setup cancelled. Let me know anytime if you want to set a budget again. 😊"

    # Ask for category
    if stage == "ask_category":
        category = get_category_from_input(input_lower)
        if category == "other" and not any(cat in input_lower for cat in ["other","misc"]):
            return "I couldn't figure out the category. Please type one of: Food, Transport, Entertainment, Shopping, Utilities, Housing, Healthcare, Education, Other."
        conv["category"] = category
        conv["stage"] = "ask_amount"
        return f"Great! Setting budget for **{category.title()}**. How much do you want to allocate for this category monthly? (e.g., RM500)"

    # Ask for amount
    if stage == "ask_amount":
        amount = get_amount_from_input(input_text)
        if not amount or amount <= 0:
            return "I couldn't find a valid amount. Please enter the budget amount in Ringgit, e.g. '500' or 'RM500'."
        conv["amount"] = amount
        conv["stage"] = "ask_month"
        return f"Got it! RM{amount:.2f} for **{conv['category'].title()}**. For which month is this budget? (e.g., September)"

    # Ask for month
    if stage == "ask_month":
        month = get_month_from_input(input_text)
        if not month:
            return "Please specify the month (e.g., September)."
        conv["month"] = month
        conv["stage"] = "ask_year"
        return f"Budget for **{conv['category'].title()}**, RM{conv['amount']:.2f}, in {month}. What year? (e.g., 2025)"

    # Ask for year
    if stage == "ask_year":
        year = get_year_from_input(input_text)
        if not year or year < 2020 or year > 2100:
            return "Please enter a valid year, e.g. 2025."
        conv["year"] = year
        conv["stage"] = "confirm"
        return (f"Please confirm: Budget **RM{conv['amount']:.2f}** for **{conv['category'].title()}** in **{conv['month']} {year}**.\n"
                "Type 'yes' to confirm or type 'change' to revise.")

    # Enhanced Revision Flow
    if stage == "confirm":
        if input_lower in ["yes", "y", "confirm", "ok"]:
            # Save budget
            result = set_budget(user_email, conv["category"], conv["amount"], conv["month"], conv["year"])
            del st.session_state.budget_conversation
            if result:
                return (f"🎉 **Budget saved!** RM{conv['amount']:.2f} for {conv['category'].title()} in {conv['month']} {conv['year']}.\n"
                        "You can now track your spending against this budget!")
            else:
                return "Sorry, there was a problem saving your budget. Please try again."
        elif input_lower in ["no", "n", "change", "edit"]:
            conv["stage"] = "revise_part"
            return ("No problem! 😊 Which part would you like to change?\n"
                    "**Category, Amount, Month, or Year?**\n"
                    "Just type which one you'd like to update.")
        else:
            return "Please type 'yes' to confirm or 'change' to revise."

    # Revision: Select part to change
    if stage == "revise_part":
        # Recognize which part to change
        if "category" in input_lower:
            conv["stage"] = "revise_category"
            return f"Please enter the new category (e.g., Food, Transport, etc.):"
        elif "amount" in input_lower or "value" in input_lower or "ringgit" in input_lower:
            conv["stage"] = "revise_amount"
            return f"Please enter the new amount in RM:"
        elif "month" in input_lower:
            conv["stage"] = "revise_month"
            return f"Please enter the new month (e.g., September):"
        elif "year" in input_lower:
            conv["stage"] = "revise_year"
            return f"Please enter the new year (e.g., 2025):"
        else:
            return "I didn't catch that. Type 'Category', 'Amount', 'Month', or 'Year'."

    if stage == "revise_category":
        category = get_category_from_input(input_lower)
        if category == "other" and not any(cat in input_lower for cat in ["other","misc"]):
            return "I couldn't figure out the category. Please type one of: Food, Transport, Entertainment, Shopping, Utilities, Housing, Healthcare, Education, Other."
        conv["category"] = category
        conv["stage"] = "confirm"
        return (f"Updated! Please confirm: Budget **RM{conv['amount']:.2f}** for **{category.title()}** in **{conv['month']} {conv['year']}**.\n"
                "Type 'yes' to confirm or 'change' to revise another part.")

    if stage == "revise_amount":
        amount = get_amount_from_input(input_text)
        if not amount or amount <= 0:
            return "I couldn't find a valid amount. Please enter the budget amount in Ringgit, e.g. '500' or 'RM500'."
        conv["amount"] = amount
        conv["stage"] = "confirm"
        return (f"Updated! Please confirm: Budget **RM{amount:.2f}** for **{conv['category'].title()}** in **{conv['month']} {conv['year']}**.\n"
                "Type 'yes' to confirm or 'change' to revise another part.")

    if stage == "revise_month":
        month = get_month_from_input(input_text)
        if not month:
            return "Please specify the new month (e.g., September)."
        conv["month"] = month
        conv["stage"] = "confirm"
        return (f"Updated! Please confirm: Budget **RM{conv['amount']:.2f}** for **{conv['category'].title()}** in **{month} {conv['year']}**.\n"
                "Type 'yes' to confirm or 'change' to revise another part.")

    if stage == "revise_year":
        year = get_year_from_input(input_text)
        if not year or year < 2020 or year > 2100:
            return "Please enter a valid year, e.g. 2025."
        conv["year"] = year
        conv["stage"] = "confirm"
        return (f"Updated! Please confirm: Budget **RM{conv['amount']:.2f}** for **{conv['category'].title()}** in **{conv['month']} {year}**.\n"
                "Type 'yes' to confirm or 'change' to revise another part.")

    # Fallback
    return "I'm having trouble understanding your budget setup. Please try again or type 'cancel' to exit."

# Function to process user input with yes/no handling for category confirmation
def process_user_input(input_text, user_email):
    """
    Process user input with clear priority handling and organized sections.
    """
    
    # ==================== SETUP AND CLEANING ====================
    input_text = input_text.strip()
    input_lower = input_text.lower()

        # === GOAL CONVERSATION HANDLING: TOP PRIORITY ===
    if "goal_conversation" in st.session_state and st.session_state.goal_conversation:
        goal_conv = st.session_state.goal_conversation

        if goal_conv.get("stage") == "ask_amount":
            amount_match = re.search(r'(\d+(?:\.\d+)?)', input_lower)
            if amount_match:
                goal_amount = float(amount_match.group(1))
                goal_conv["goal_amount"] = goal_amount
                goal_conv["stage"] = "ask_timeframe"
                return (
                    f"Great! You've set RM{goal_amount:.2f} for your goal.\n"
                    f"Now, what's your savings timeframe? (minimum 6 months, e.g., 12 months, 2 years)\n"
                    f"This helps me plan the monthly savings amount for you!"
                )
            else:
                return "How much do you want to save for this goal? (e.g., RM30000)"

        if goal_conv.get("stage") == "ask_timeframe":
            time_match = re.search(r'(\d+)\s*(month|months|year|years|week|weeks)', input_lower.replace(" ", ""))
            if not time_match:
                time_match = re.search(r'(\d+)\s*(month|months|year|years|week|weeks)', input_lower)
            if time_match:
                num = int(time_match.group(1))
                unit = time_match.group(2)
                if unit.startswith("year"):
                    months = num * 12
                    timeframe_str = f"{num} years"
                elif unit.startswith("month"):
                    months = num
                    timeframe_str = f"{num} months"
                elif unit.startswith("week"):
                    months = max(1, round(num / 4))
                    timeframe_str = f"{num} weeks (≈ {months} months)"
                else:
                    months = 0

                if months < 6:
                    return (
                        "Sorry, goals must be set for at least 6 months later.\n"
                        "Please enter a savings timeframe of 6 months or more (e.g., 6 months, 1 year, 12 months)."
                    )

                goal_conv["timeframe"] = timeframe_str
                goal_conv["months"] = months
                goal_conv["stage"] = "confirm_goal"
                monthly_savings = goal_conv["goal_amount"] / months
                return (
                    f"Perfect! You'll save RM{goal_conv['goal_amount']:.2f} in {timeframe_str}.\n"
                    f"That means RM{monthly_savings:.2f} per month.\n"
                    f"Do you want to create this goal? Type 'yes' to confirm or 'no' to cancel."
                )
            else:
                return "Please tell me your savings timeframe (minimum 6 months, e.g., 12 months, 2 years, 8 weeks) for this goal."

        if goal_conv.get("stage") == "confirm_goal":
            if input_lower in ["yes", "y", "confirm", "ok"]:
                goal_type = goal_conv["goal_type"]
                goal_amount = goal_conv["goal_amount"]
                timeframe = goal_conv["timeframe"]
                months = goal_conv["months"]
                monthly_savings = goal_amount / months
                target_date = (datetime.now() + timedelta(days=months * 30)).strftime("%Y-%m-%d")
                # Use add_goal instead of save_goal_to_database
                success, goal_id = add_goal(
                user_email,
                goal_name=goal_type,       # Use goal_type as name for simplicity
                goal_type=goal_type,
                target_amount=goal_amount,
                target_date=target_date,
                monthly_contribution=monthly_savings,
                goal_details={}            # Empty details for quick save
            )
            del st.session_state.goal_conversation
            if success:
                return (
                    f"🎉 Your '{goal_type}' goal for RM{goal_amount:.2f} over {timeframe} is set!\n"
                    f"You need to save RM{monthly_savings:.2f} per month. Best of luck!"
                )
            else:
                return "❌ Sorry, failed to save your goal. Please try again!"
        elif input_lower in ["no", "n", "cancel"]:
            del st.session_state.goal_conversation
            return "No worries! Goal creation cancelled. You can start again anytime."
        else:
            return "Type 'yes' to confirm this goal, or 'no' to cancel."

    major_goal_keywords = {
        "buy car": "Buy New Car",
        "buy a car": "Buy New Car",
        "buy new car": "Buy New Car",
        "buy a new car": "Buy New Car",
        "buy house": "Buy New House",
        "buy a house": "Buy New House",
        "buy new house": "Buy New House",
        "buy a new house": "Buy New House",
        "go to travel": "Go To Travel",
        "travel": "Go To Travel",
        "new car": "Buy New Car",
        "new house": "Buy New House",
    }
    for phrase, goal_type in major_goal_keywords.items():
        if phrase in input_lower:
            # Start a goal conversation with this major goal type
            st.session_state.goal_conversation = {
                "stage": "ask_amount",
                "goal_type": goal_type,
                "custom_prompted": True
            }
            return f"🎯 **Let's set your '{goal_type}' goal!**\n\nHow much do you want to save for this goal? (e.g., RM50,000 for car)\n\nI'll help you plan the savings timeline next!"
    
    if "budget_conversation" in st.session_state:
        return process_budget_conversation(input_text, user_email)
    
    # Define profanity words
    profanity_words = [
        "fuck", "shit", "damn", "bitch", "ass", "asshole", "bastard", "crap", 
        "hell", "piss", "stupid", "idiot", "moron", "dumb", "suck", "sucks",
        "hate you", "hate this", "useless", "garbage", "trash", "rubbish",
        "bodoh", "bangang", "lancau", "pukimak", "cibai", "kanina", "wtf"
    ]

    # ==================== PRIORITY 1: EXPENSE CONFIRMATION (HIGHEST PRIORITY) ====================
    # This MUST be checked before length validation to handle "no" responses properly
    assistant_messages = [msg for msg in st.session_state.messages if msg["role"] == "assistant"]
    
    if assistant_messages and "pending_expense" in st.session_state:
        last_assistant_msg = assistant_messages[-1]["content"].lower()
        
        if "is that the right category?" in last_assistant_msg:
            # Handle YES responses
            if input_lower in ["yes", "y", "yeah", "correct", "right", "yep", "sure"]:
                del st.session_state.pending_expense
                return "✅ **Perfect!** Your expense has been saved! 🎉\n\nYour spending tracking is getting better and better! What else would you like to record today? 😊"

            elif input_lower in ["no", "n", "nope"] or "change" in input_lower or "wrong" in input_lower:
                st.session_state.correction_stage = "ask_what_to_change"
                return "No worries! Let's fix that right away! 🔧\n\n**What would you like to change?**\n• Say **'category'** to change the category\n• Say **'amount'** to change the amount\n\nWhat needs fixing? 😊"
            
            else:
                return "I didn't understand that. Is the category correct? Please answer with **yes** or **no**."
            
                # ==================== PRIORITY 2: EXPENSE CORRECTION STAGES ====================
    if "correction_stage" in st.session_state and "pending_expense" in st.session_state:
        
        if st.session_state.correction_stage == "ask_what_to_change":
            if "category" in input_lower:
                st.session_state.correction_stage = "change_category"
                return "What category would you like to use instead? Choose from: Food, Transport, Entertainment, Shopping, Utilities, Housing, Healthcare, Education, Other"
            elif "amount" in input_lower:
                st.session_state.correction_stage = "change_amount"
                return "What is the correct amount for this expense?"
            else:
                # Default to category change
                st.session_state.correction_stage = "change_category"
                return "I'll help you change the category. What category would you like to use instead?"
        
        elif st.session_state.correction_stage == "change_category":
            new_category = input_text.lower().strip()
            standard_categories = ["food", "transport", "entertainment", "shopping", "utilities", "housing", "healthcare", "education", "other"]
            
            # Find matching category
            category_match = new_category
            for category in standard_categories:
                if category in new_category:
                    category_match = category
                    break
            
            # Update expense category
            expense_id = st.session_state.pending_expense["id"]
            if update_expense_category(expense_id, category_match):
                st.session_state.correction_stage = None
                del st.session_state.pending_expense
                return f"✅ I've updated the category to '{category_match}'. Your expense has been recorded successfully."
            else:
                return "Sorry, I had trouble updating the category. Can you try again?"
        
        elif st.session_state.correction_stage == "change_amount":
            amount_match = re.search(r"(\d+\.?\d*)", input_lower)
            if amount_match:
                try:
                    new_amount = float(amount_match.group(1))
                    expense_id = st.session_state.pending_expense["id"]
                    
                    if update_expense_amount(expense_id, new_amount):
                        st.session_state.correction_stage = None
                        del st.session_state.pending_expense
                        return f"✅ I've updated the amount to RM{new_amount:.2f}. Your expense has been recorded successfully."
                    else:
                        return "Sorry, I had trouble updating the amount. Can you try again?"
                except ValueError:
                    return "I couldn't understand that amount. Please provide a number like '25' or '25.50'."
            else:
                return "I couldn't find a valid amount. Please just provide the number, like '25' or '25.50'."

       # ==================== PRIORITY 3: MULTIPLE EXPENSES & EXPENSE CHANGES ====================

    # FIRST: Handle expense change mode (HIGHEST PRIORITY)
    if "expense_change_mode" in st.session_state:
        
        if st.session_state.expense_change_mode == "select_expense":
            # User is selecting which expense to change
            expenses_list = st.session_state.pending_multiple_expenses
            
            # Check if user provided a number
            number_match = re.search(r'(\d+)', input_text)
            if number_match:
                expense_index = int(number_match.group(1)) - 1
                if 0 <= expense_index < len(expenses_list):
                    st.session_state.changing_expense_index = expense_index
                    st.session_state.expense_change_mode = "ask_what_to_change"
                    
                    expense = expenses_list[expense_index]
                    return f"What would you like to change about **RM{expense['amount']:.2f} for {expense['description']}**?\n\n• Say **'amount'** to change the price\n• Say **'description'** to change what you bought\n• Say **'category'** to change the category\n\nWhat needs to be fixed?"
                else:
                    return f"Please choose a number between 1 and {len(expenses_list)}."
            else:
                return "I need a number (1, 2, 3, etc.) to know which expense to change. Please try again!"
        
        elif st.session_state.expense_change_mode == "ask_what_to_change":
            # User is saying what to change
            if "amount" in input_lower or "price" in input_lower:
                st.session_state.expense_change_mode = "change_amount"
                return "What's the correct amount for this expense?"
            elif "description" in input_lower or "item" in input_lower or "what" in input_lower:
                st.session_state.expense_change_mode = "change_description"
                return "What did you actually spend money on?"
            elif "category" in input_lower:
                st.session_state.expense_change_mode = "change_category"
                return "What category should this be? Choose from: Food, Transport, Entertainment, Shopping, Utilities, Housing, Healthcare, Education, Other"
            else:
                return "Please tell me what to change: **'amount'**, **'description'**, or **'category'**?"
        
        elif "changing_expense_index" in st.session_state:
            # User is making the actual change
            expense_index = st.session_state.changing_expense_index
            expenses_list = st.session_state.pending_multiple_expenses
            
            if st.session_state.expense_change_mode == "change_amount":
                amount_match = re.search(r"(\d+\.?\d*)", input_text)
                if amount_match:
                    new_amount = float(amount_match.group(1))
                    expenses_list[expense_index]["amount"] = new_amount
                    
                    # Clear change mode
                    del st.session_state.expense_change_mode
                    del st.session_state.changing_expense_index
                    
                    # Show updated list
                    response = "✅ **Amount updated!** Here's your updated list:\n\n"
                    total_amount = 0
                    for i, expense in enumerate(expenses_list, 1):
                        response += f"**{i}.** RM{expense['amount']:.2f} for **{expense['description']}** → *{expense['category'].title()}*\n"
                        total_amount += expense['amount']
                    
                    response += f"\n💰 **Total:** RM{total_amount:.2f}\n\n✅ **Is this correct now?** Say 'Yes' to record or 'No' to make more changes."
                    return response
                else:
                    return "I couldn't find a valid amount. Please provide just the number, like '25' or '25.50'."
            
            elif st.session_state.expense_change_mode == "change_description":
                new_description = input_text.strip()
                expenses_list[expense_index]["description"] = new_description
                expenses_list[expense_index]["category"] = categorize_expense(new_description)
                
                # Clear change mode
                del st.session_state.expense_change_mode
                del st.session_state.changing_expense_index
                
                # Show updated list
                response = "✅ **Description updated!** Here's your updated list:\n\n"
                total_amount = 0
                for i, expense in enumerate(expenses_list, 1):
                    response += f"**{i}.** RM{expense['amount']:.2f} for **{expense['description']}** → *{expense['category'].title()}*\n"
                    total_amount += expense['amount']
                
                response += f"\n💰 **Total:** RM{total_amount:.2f}\n\n✅ **Is this correct now?** Say 'Yes' to record or 'No' to make more changes."
                return response
            
            elif st.session_state.expense_change_mode == "change_category":
                new_category = input_text.lower().strip()
                standard_categories = ["food", "transport", "entertainment", "shopping", "utilities", "housing", "healthcare", "education", "other"]
                
                # Find matching category
                category_match = "other"
                for category in standard_categories:
                    if category in new_category:
                        category_match = category
                        break
                
                expenses_list[expense_index]["category"] = category_match
                
                # Clear change mode
                del st.session_state.expense_change_mode
                del st.session_state.changing_expense_index
                
                # Show updated list
                response = "✅ **Category updated!** Here's your updated list:\n\n"
                total_amount = 0
                for i, expense in enumerate(expenses_list, 1):
                    response += f"**{i}.** RM{expense['amount']:.2f} for **{expense['description']}** → *{expense['category'].title()}*\n"
                    total_amount += expense['amount']
                
                response += f"\n💰 **Total:** RM{total_amount:.2f}\n\n✅ **Is this correct now?** Say 'Yes' to record or 'No' to make more changes."
                return response

    # SECOND: Handle regular multiple expenses confirmation (ONLY if not in change mode)
    if "pending_multiple_expenses" in st.session_state and st.session_state.pending_multiple_expenses and "expense_change_mode" not in st.session_state:
        
        if input_lower in ["yes", "y", "correct", "right", "confirm", "ok", "yeah", "yep"]:
            expenses_list = st.session_state.pending_multiple_expenses
            success, expense_ids = add_multiple_expenses(user_email, expenses_list)
            
            if success:
                del st.session_state.pending_multiple_expenses
                total_amount = sum(exp["amount"] for exp in expenses_list)
                
                # Enhanced confirmation with detailed summary
                response = "✅ **Perfect! All expenses have been recorded successfully!**\n\n"
                response += "📝 **Final Summary:**\n\n"
                
                for i, exp in enumerate(expenses_list, 1):
                    response += f"**{i}.** RM{exp['amount']:.2f} for **{exp['description']}** → *{exp['category'].title()}* category\n"
                
                response += f"\n💰 **Total Recorded:** RM{total_amount:.2f}\n"
                response += f"📊 **Categories Used:** {len(set(exp['category'] for exp in expenses_list))} different categories\n\n"
                response += "🎉 Great job tracking your expenses! What else can I help you with today?"
                
                return response
            else:
                return "❌ Sorry, there was an error recording your expenses. Please try again."
        
        elif input_lower in ["no", "n", "wrong", "incorrect", "change"]:
            # Ask which expense to change
            st.session_state.expense_change_mode = "select_expense"
            expenses_list = st.session_state.pending_multiple_expenses
            
            response = "🔧 **No problem! Let's fix that.**\n\n"
            response += "Which expense would you like to change?\n\n"
            
            for i, exp in enumerate(expenses_list, 1):
                response += f"**{i}.** RM{exp['amount']:.2f} for {exp['description']} ({exp['category'].title()})\n"
            
            response += f"\nJust tell me the number (1, 2, 3, etc.)!"
            
            return response
        
        else:
            return "🤔 I didn't understand that. Please say **'Yes'** to confirm all expenses or **'No'** to make changes."

                # ==================== PRIORITY 4: INPUT VALIDATION ====================
    # Now check length AFTER confirmation checks (THIS FIXES THE "NO" BUG!)
    if len(input_text) <= 2:
        helpful_responses = [
            "🤔 I didn't quite catch that! Could you tell me more?\n\n💡 **Try saying:**\n• 'I spent RM10 on nasi lemak'\n• 'Show my expenses'\n• 'Set a budget'\n• 'Help' for more options",
            
            "😊 That's a bit short for me to understand! Could you be more specific?\n\n🎯 **You can:**\n• Record expenses: 'RM15 for roti canai'\n• Check spending: 'Show my budget'\n• Get help: 'What can you do?'",
            
            "🤷‍♂️ I'm not sure what you meant! Want to try again?\n\n✨ **Popular commands:**\n• Track expenses\n• View my spending\n• Set up budgets\n• Create goals"
        ]
        return random.choice(helpful_responses)
    
    # Handle common unclear patterns
    unclear_patterns = ["test", "hello test", "asdf", "qwerty", "123", "abc", "xyz", "haha", "lol"]
    if input_text.lower() in unclear_patterns:
        return "😄 Testing me out? That's cool! I'm here and ready to help with your finances!\n\n💰 **Try these:**\n• 'I spent RM8 on mee goreng'\n• 'Show my recent expenses'\n• 'Help me set a budget'\n• 'What can you do?'\n\nWhat would you like to do? 😊"
    
    # Handle random characters or gibberish
    if not any(char.isalpha() for char in input_text) and not any(word in input_text.lower() for word in ["rm", "spent", "budget", "goal"]):
        return "🤖 I see some numbers or symbols, but I'm not sure what you're trying to tell me!\n\n💡 **For expenses, try:**\n• 'RM20 for lunch'\n• 'I spent RM5 on coffee'\n\n📊 **For other features:**\n• 'Show my budget'\n• 'Help'\n\nWhat can I help you with? 😊"
    
    # Check if input contains profanity
    if any(word in input_lower for word in profanity_words):
        professional_responses = [
            "😊 I understand you might be frustrated! I'm here to help make managing your finances easier and less stressful.\n\n💰 **Let's focus on something positive:**\n• Track your spending\n• Set up a budget\n• Plan for your goals\n\nHow can I help you take control of your money today? 🌟",
            
            "🤝 I get it - finances can be stressful sometimes! But I'm here to make it simpler for you.\n\n✨ **Let's turn this around:**\n• 'Show my expenses' - see where your money goes\n• 'Set a budget' - take control\n• 'Help me save' - build your future\n\nWhat would you like to work on? 💪",
            
            "😌 No worries! Sometimes money management can feel overwhelming, but we can tackle it together step by step.\n\n🎯 **Ready to get started?**\n• Record today's expenses\n• Review your budget\n• Set a savings goal\n\nI'm here to help - what would you like to do? 😊"
        ]
        return random.choice(professional_responses)
    
    # Handle aggressive/angry patterns
    angry_patterns = ["angry", "mad", "frustrated", "annoyed", "pissed off", "fed up", "sick of", "tired of"]
    if any(pattern in input_lower for pattern in angry_patterns):
        return "😔 I can sense you're feeling frustrated, and that's completely understandable! Money management can be overwhelming sometimes.\n\n🤗 **I'm here to help make it easier:**\n• Let's start small: track just one expense\n• Quick win: check your recent spending\n• Get organized: set up a simple budget\n\nTake a deep breath - we've got this together! What would feel manageable right now? 💙"
    
        # ==================== PRIORITY 4.5: GOAL CONVERSATION HANDLING ====================
    
    # Check for goal-related phrases that should trigger goal conversation
    goal_keywords = [
        "buy new car", "buy a car", "new car", "car goal",
        "buy new house", "buy a house", "new house", "house goal", "dream home",
        "go to travel", "travel goal", "vacation", "trip", "holiday",
        "want to buy", "plan to buy", "save for", "saving for",
        "6 month later", "1 year later", "next year", "months later", "years later"
    ]
    
    # If user mentions goal-related keywords, handle as goal conversation
    if any(keyword in input_lower for keyword in goal_keywords):
        # Check if it's a goal-setting request
        if any(phrase in input_lower for phrase in [
            "want to buy", "plan to buy", "save for", "saving for", 
            "buy new", "get a new", "purchase", "goal", "dream"
        ]):
            # This should trigger goal conversation instead of expense detection
            return handle_goal_conversation(user_email, input_text)
    
    # ==================== PRIORITY 5: SPECIAL COMMANDS ====================
    # Handle button clicks and special commands
    
    if any(cmd in input_text.lower() for cmd in ["set budget", "track expenses", "set a goal", "set goal"]):
        # Clear any pending states that might interfere
        if "pending_multiple_expenses" in st.session_state:
            del st.session_state.pending_multiple_expenses
        if "pending_expense" in st.session_state:
            del st.session_state.pending_expense
        if "correction_stage" in st.session_state:
            del st.session_state.correction_stage
    
    # PRIORITY ORDER: Check GOAL commands FIRST before budget commands
    
    # Handle GOAL commands first (higher priority)
    if any(goal_phrase in input_text.lower() for goal_phrase in ["set a goal", "set goal", "set my goal", "set my goals", "set a goals", "want to set goal", "i want to set goal", "create goal", "new goal"]):
        # Clear any ongoing conversations
        if "budget_conversation" in st.session_state:
            del st.session_state.budget_conversation
            
        return "Hey there! 😊 I don't see any goals set up yet, but that's totally fine - we all start somewhere!\n\n🎯 **Ready to turn your dreams into plans?** Setting financial goals is like having a roadmap to your future!\n\nI can help you save for anything:\n• 🚗 **Buy New Car** - get that reliable ride you deserve!\n• 🏠 **Buy New House** - your dream home awaits!\n• ✈️ **Go To Travel** - explore the world and create memories!\n\nJust say **'what goals you want to plan?'** and let's make your dreams happen! What do you say? ✨"
    
    # Handle BUDGET commands second (lower priority)
    elif "set budget" in input_text.lower():
        # Clear any ongoing conversations  
        if "goal_conversation" in st.session_state:
            del st.session_state.goal_conversation
            
        # Start budget conversation properly
        st.session_state.budget_conversation = {"stage": "ask_category"}
        return "I'm so excited to help you set up a budget! 🎉 This is going to make such a difference in managing your money!\n\n**Which spending category would you like to start with?** Here are your options:\n\n🍽️ **Food** - groceries, restaurants, takeout\n\n🚗 **Transport** - gas, public transport, parking\n\n🎬 **Entertainment** - movies, games, subscriptions\n\n🛍️ **Shopping** - clothes, personal items\n\n💡 **Utilities** - electricity, water, internet, phone\n\n🏠 **Housing** - rent, mortgage payments\n\n⚕️ **Healthcare** - medical expenses, medicine\n\n📚 **Education** - books, courses, training\n\n📦 **Other** - miscellaneous expenses\n\nJust tell me which category you'd like to focus on first! I'll walk you through everything step by step. 😊"

    # Handle expense viewing requests
    if input_text.lower() in ["show my daily expense", "show daily expense", "daily expense", "today's expense", "show today's expense"]:
        return show_daily_expenses(user_email)

    if input_text.lower() in ["show my monthly expenses", "show monthly expenses", "monthly expenses", "monthly summary", "show month's expenses", "show expenses for this month"]:
        return show_monthly_expenses(user_email)

    # Handle income setting
    if any(word in input_text.lower() for word in ["income", "salary", "earn", "monthly income"]):
        amount_match = re.search(r"(\d+(?:\.\d+)?)", input_text)
        if amount_match:
            income_amount = float(amount_match.group(1))
            success = set_user_income(user_email, income_amount)
            
            if success:
                response = "💰 **Income Successfully Set!**\n\n"
                response += f"Your monthly income: **RM{income_amount:.2f}**\n\n"
                response += "🎯 **Great news!** Now you can set financial goals!\n\n"
                response += "Available goals:\n\n"
                response += "🚗 **New Car** - Save for your dream vehicle\n\n"
                response += "🏠 **New House** - Build towards homeownership\n\n"
                response += "🏖️ **Dream Vacation** - Plan that perfect getaway\n\n"
                response += "Just say 'set a goal for [car/house/vacation]' to get started!"
                return response
            else:
                return "❌ Sorry, there was an error setting your income. Please try again."
        else:
            response = "💭 **Please specify your monthly income amount.**\n\n"
            response += "For example:\n\n"
            response += "• 'My monthly income is RM5000'\n\n"
            response += "• 'I earn RM3500 per month'\n\n"
            response += "• 'Set income RM4200'\n\n"
            response += "What's your monthly income?"
            return response
        
            # ==================== PRIORITY 6: CONVERSATION HANDLING ====================
    # Handle budget conversation flow
    if "budget_conversation" in st.session_state:
        stage = st.session_state.budget_conversation["stage"]
        
        # Enhanced cancel detection
        cancel_words = ["cancel", "stop", "nevermind", "never mind", "forget it", "change mind", "quit", "exit", "abort", "back"]
        if any(word in input_lower for word in cancel_words):
            del st.session_state.budget_conversation
            return "No problem at all! 😊 Budget planning should never feel rushed.\n\nWhenever you're ready to set up a budget, just say **'set budget'** and I'll be here to help you through it step by step!\n\nIs there anything else I can help you with right now? 💭"
        
        # Handle different stages of budget conversation
        if stage == "ask_category":
            # User is providing a category
            category = input_text.lower().strip()
            
            # Enhanced category mapping
            if any(word in category for word in ["food", "grocery", "restaurant", "meal", "dining", "eat", "lunch", "dinner", "breakfast"]):
                selected_category = "food"
            elif any(word in category for word in ["transport", "bus", "train", "taxi", "car", "travel", "commute", "gas", "fuel", "drive"]):
                selected_category = "transport"
            elif any(word in category for word in ["entertainment", "movie", "game", "fun", "show", "streaming", "netflix", "cinema"]):
                selected_category = "entertainment"
            elif any(word in category for word in ["shopping", "clothes", "mall", "store", "fashion", "cloth", "purchase", "stuff"]):
                selected_category = "shopping"
            elif any(word in category for word in ["utilities", "bill", "electric", "water", "internet", "phone", "wifi", "utility"]):
                selected_category = "utilities"
            elif any(word in category for word in ["housing", "rent", "mortgage", "home", "apartment", "house", "accommodation"]):
                selected_category = "housing"
            elif any(word in category for word in ["health", "medical", "doctor", "hospital", "medicine", "clinic", "pharmacy"]):
                selected_category = "healthcare"
            elif any(word in category for word in ["education", "school", "book", "tuition", "learn", "course", "study", "university"]):
                selected_category = "education"
            else:
                selected_category = "other"
            
            # Store the category and move to next stage
            st.session_state.budget_conversation["category"] = selected_category
            st.session_state.budget_conversation["stage"] = "ask_amount"
            
            return f"**{selected_category.title()} Budget** - Excellent choice!\n\nNow for the fun part! What's a realistic monthly amount you'd like to set aside for {selected_category.title()}?\n\nThink about your typical spending in this area and what feels manageable. You can always adjust it later!\n\nJust tell me the amount - like **'350'** for RM350. What sounds right to you? 🤔"
        
        elif stage == "ask_amount":
            # Extract amount from budget conversation context
            amount_match = re.search(r"(\d+\.?\d*)", input_text)
            if amount_match:
                try:
                    amount = float(amount_match.group(1))
                    # Store the amount and move to confirmation stage
                    st.session_state.budget_conversation["amount"] = amount
                    st.session_state.budget_conversation["stage"] = "confirm"
                    
                    category = st.session_state.budget_conversation["category"]
                    
                    return f"**RM{amount:.2f} for {category.title()}** - That sounds like a well-thought-out amount! 👍\n\n📋 **Quick Summary:**\n• Category: **{category.title()}**\n• Monthly Budget: **RM{amount:.2f}**\n• This will help you track and control your {category.lower()} spending!\n\nShall I activate this budget for you? Say **'yes'** to confirm or **'no'** to make changes! 🚀"
                except ValueError:
                    return "Oops! I'm having trouble reading that number! 😅\n\nCould you help me out by typing just the amount as a simple number?\n\n**Examples:**\n• Type **'250'** for RM250\n• Type **'99.50'** for RM99.50\n\nWhat amount would you like to budget? 💰"
            else:
                return "I'm looking for the budget amount, but I can't quite find it in your message! 🔍\n\nCould you tell me how much you'd like to set aside for this category? Just the number is perfect!\n\n**For example:** Type **'400'** for RM400\n\nWhat's your ideal budget amount? 💡"
        
        elif stage == "confirm":
            # User is confirming the budget
            if input_text.lower() in ["yes", "y", "confirm", "ok", "sure", "go ahead", "do it", "yep", "yup", "absolutely", "definitely", "perfect"]:
                # Get the budget details
                category = st.session_state.budget_conversation["category"]
                amount = st.session_state.budget_conversation["amount"]
                month = datetime.now().strftime("%B")
                year = datetime.now().year
                
                # Set the budget
                success = set_budget(user_email, category, amount, month, year)
                
                # Clear the conversation state
                del st.session_state.budget_conversation
                
                if success:
                    return f"🎉 **WOOHOO!** Your {category.title()} budget is now active! 💪\n\n**RM{amount:.2f} for {category.title()}** - You're taking control of your finances like a pro! This is exactly how successful people manage their money!\n\nFeel like setting up another budget? Just say **'set budget'** again! I'm excited to help you build these amazing habits! 🌟"
                else:
                    return "Oh dear! 😔 Something went wrong on my end while setting up your budget.\n\nThis is unusual - could you please try again? I really want to get this perfect for you! 💪"
            
            elif input_text.lower() in ["no", "n", "cancel", "wait", "hold on", "not yet", "nope", "stop", "not really"]:
                # Clear the conversation state
                del st.session_state.budget_conversation
                return "Absolutely no problem! 😊 I totally understand wanting to get the numbers just right.\n\nBudgeting is personal, and it should feel comfortable for you. Take your time to think about what works best!\n\nWhen you're ready to try again, just say **'set budget'** and I'll be right here to help! Is there anything else I can assist you with? 💭"
            
            else:
                return "I want to make sure I understand you perfectly! 😊\n\n**Could you say:**\n• **'Yes'** to activate this budget\n• **'No'** if you'd like to make changes\n\nI'm here to get this exactly right for you! 🎯"

    
    # ==================== PRIORITY 7: NEW EXPENSE DETECTION ====================
    # DEBUG: Add debugging
    print(f"DEBUG: About to check expenses for: '{input_text}'")
    
    # Check for multiple expenses first - with debugging
    multiple_expenses = debug_expense_parsing(input_text)
    
    if len(multiple_expenses) > 1:
        print(f"DEBUG: ✅ Multiple expenses detected: {len(multiple_expenses)}")
        st.session_state.pending_multiple_expenses = multiple_expenses
        
        response = "🧾 **Great! I found multiple expenses in your message.**\n\n"
        response += "Let me confirm what I understood:\n\n"
        
        total_amount = 0
        for i, expense in enumerate(multiple_expenses, 1):
            response += f"**{i}.** RM{expense['amount']:.2f} for **{expense['description']}** → *{expense['category'].title()}* category\n"
            total_amount += expense['amount']
        
        response += f"\n💰 **Total Amount:** RM{total_amount:.2f}\n"
        response += f"📊 **Summary:** {len(multiple_expenses)} expenses across {len(set(exp['category'] for exp in multiple_expenses))} different categories\n\n"
        response += "✅ **Is this correct?** Say **'Yes'** to record all expenses or **'No'** to make changes."
        
        return response
    
    elif len(multiple_expenses) == 1:
        print(f"DEBUG: ⚠️ Only 1 expense found in multiple detection, treating as single")
        # Treat as single expense
        expense = multiple_expenses[0]
        amount = expense["amount"]
        description = expense["description"] 
        category = expense["category"]
        
        success, expense_id = add_expense(user_email, amount, description, category)
        
        if success:
            st.session_state.pending_expense = {
                "id": expense_id,
                "amount": amount,
                "description": description,
                "category": category
            }
            return f"I've recorded your expense: RM{amount:.2f} for {description} in the '{category}' category. Is that the right category?"
    
    else:
        print(f"DEBUG: ❌ No expenses detected in multiple detection, trying single")
        # Check for single expense with original method
        entities = extract_entities(input_text)
        if "amount" in entities and "description" in entities:
            print(f"DEBUG: ✅ Single expense detected with original method")
            amount = entities["amount"]
            description = entities["description"]
            category = categorize_expense(description)
            
            success, expense_id = add_expense(user_email, amount, description, category)
            
            if success:
                st.session_state.pending_expense = {
                    "id": expense_id,
                    "amount": amount,
                    "description": description,
                    "category": category
                }
                return f"I've recorded your expense: RM{amount:.2f} for {description} in the '{category}' category. Is that the right category?"
        else:
            print(f"DEBUG: ❌ No expenses detected at all")
    
# ==================== PRIORITY 7: GOAL CONVERSATION HANDLING 
    

    # ==================== PRIORITY 8: INTENT PROCESSING ====================
    intent_tag, confidence = predict_intent(input_text, intents)
    
    # Check for specific category budget queries first
    category_budget_patterns = [
        r"show\s+(\w+)\s+budget",
        r"view\s+(\w+)\s+budget", 
        r"check\s+(\w+)\s+budget",
        r"(\w+)\s+budget\s+status",
        r"my\s+(\w+)\s+budget"
    ]
    
    for pattern in category_budget_patterns:
        match = re.search(pattern, input_lower)
        if match:
            category = match.group(1)
            # Map common category names
            category_map = {
                "food": "food", "grocery": "food", "dining": "food",
                "transport": "transport", "transportation": "transport", "travel": "transport",
                "entertainment": "entertainment", "fun": "entertainment", "movie": "entertainment",
                "shopping": "shopping", "clothes": "shopping", "retail": "shopping",
                "utilities": "utilities", "bills": "utilities", "utility": "utilities",
                "housing": "housing", "rent": "housing", "home": "housing",
                "healthcare": "healthcare", "medical": "healthcare", "health": "healthcare",
                "education": "education", "school": "education", "learning": "education"
            }
            
            mapped_category = category_map.get(category.lower(), category.lower())
            return show_specific_budget(user_email, mapped_category)
        
    if "show my budget" in input_lower or "view my budget" in input_lower or "check my budget" in input_lower:
        return show_budget_status(user_email)
    
    # Handle general intents
    if intent_tag == "expense_query":
        return show_daily_expenses(user_email)
    
    elif intent_tag == "budget_query":
        return show_budget_status(user_email)
    
    elif intent_tag == "goal_query":
        return show_goals_status(user_email)

    # ==================== PRIORITY 9: FALLBACK HANDLING ====================
    try:
        return get_response(intent_tag, input_text, user_email)
    except Exception as e:
        return "I'm having trouble understanding that. Could you try rephrasing your request?"

def debug_expense_parsing(text):
    """Debug function to see what's being detected"""
    print(f"DEBUG: Input text: '{text}'")
    
    # Test single expense detection
    single_entities = extract_entities(text)
    print(f"DEBUG: Single expense entities: {single_entities}")
    
    # Test multiple expense detection  
    multiple_expenses = extract_multiple_expenses(text)
    print(f"DEBUG: Multiple expenses found: {len(multiple_expenses)}")
    for i, exp in enumerate(multiple_expenses):
        print(f"DEBUG: Expense {i+1}: {exp}")
    
    return multiple_expenses
        
def get_user_expenses(user_email):
    """
    Get all expenses for a specific user with debug info
    """
    try:
        conn = sqlite3.connect('finance_data.db')
        cursor = conn.cursor()
        
        print(f"DEBUG: Looking for expenses for user: {user_email}")
        
        # First, check what's actually in the database
        cursor.execute("SELECT COUNT(*) FROM expenses")
        total_count = cursor.fetchone()[0]
        print(f"DEBUG: Total expenses in database: {total_count}")
        
        cursor.execute("SELECT COUNT(*) FROM expenses WHERE user_email = ?", (user_email,))
        user_count = cursor.fetchone()[0]
        print(f"DEBUG: Expenses for {user_email}: {user_count}")
        
        # Get user expenses
        cursor.execute("""
            SELECT amount, description, category, date, datetime 
            FROM expenses 
            WHERE user_email = ? 
            ORDER BY datetime DESC
        """, (user_email,))
        
        rows = cursor.fetchall()
        conn.close()
        
        print(f"DEBUG: Retrieved {len(rows)} expenses")
        for i, row in enumerate(rows[:3]):  # Show first 3
            print(f"DEBUG: Expense {i+1}: Amount={row[0]}, Description={row[1]}, Date={row[3]}")
        
        expenses = []
        for row in rows:
            expenses.append({
                'amount': row[0],
                'description': row[1], 
                'category': row[2],
                'date': row[3],
                'datetime': row[4]
            })
        
        return expenses
        
    except Exception as e:
        print(f"DEBUG: Error getting expenses: {e}")
        return []
        
def show_daily_expenses(user_email):
    """
    Show today's expenses with better formatting and weekly summary
    """
    from datetime import datetime, timedelta
    
    today = datetime.now().strftime("%A, %B %d, %Y")
    today_short = datetime.now().strftime("%Y-%m-%d")  # 2025-09-03
    
    print(f"DEBUG: Today's date for filtering: {today_short}")
    print(f"DEBUG: User email: {user_email}")
    
    # Get today's expenses using the correct database connection
    try:
        conn = sqlite3.connect(DB_PATH)  # Use DB_PATH instead of hardcoded path
        c = conn.cursor()
        
        # Get today's expenses - FIXED QUERY
        c.execute("""
            SELECT amount, description, category, date
            FROM expenses 
            WHERE user_email = ? AND date = ?
            ORDER BY id DESC
        """, (user_email, today_short))
        
        today_expenses = c.fetchall()
        
        # Get this week's expenses for weekly summary
        week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        c.execute("""
            SELECT amount, description, category, date
            FROM expenses 
            WHERE user_email = ? AND date >= ?
            ORDER BY date DESC, id DESC
        """, (user_email, week_start))
        
        week_expenses = c.fetchall()
        conn.close()
        
        print(f"DEBUG: Found {len(today_expenses)} expenses for today")
        print(f"DEBUG: Found {len(week_expenses)} expenses for this week")
        
    except Exception as e:
        print(f"DEBUG: Database error: {e}")
        return f"❌ **Error retrieving expenses:** {str(e)}\n\nPlease try again!"
    
    # Build response with proper formatting
    response = f"📅 **{today}**\n\n"
    
    if not today_expenses:
        response += "No expenses recorded for today yet! 💸\n\n"
        response += "✨ **Ready to start tracking?**\n"
        response += "• 'I spent RM8 on nasi lemak'\n"
        response += "• 'RM15 for roti canai'\n" 
        response += "• 'RM25 groceries at Aeon'\n\n"
        response += "What did you spend money on today? 😊\n\n"
    else:
        # Calculate today's total
        total_today = sum(float(exp[0]) for exp in today_expenses)
        response += f"**Daily Total: RM{total_today:.2f}**\n\n"
        
        # Group by category for better display
        category_totals = {}
        
        for expense in today_expenses:
            amount = float(expense[0])
            description = expense[1]
            category = expense[2]
            
            # Add to category totals
            if category not in category_totals:
                category_totals[category] = 0
            category_totals[category] += amount
            
            # Format individual expense with proper line breaks
            response += f"• RM{amount:.2f} for **{description}** ({category.title()})\n"
        
        response += "\n"
        
        # Add category summary if multiple categories
        if len(category_totals) > 1:
            response += "💰 **Category Breakdown:**\n"
            for category, total in category_totals.items():
                response += f"• {category.title()}: RM{total:.2f}\n"
            response += "\n"
    
    # Add weekly summary if there are weekly expenses
    if week_expenses:
        response += "📊 **This Week's Summary:**\n"
        
        # Group weekly expenses by date
        weekly_by_date = {}
        weekly_total = 0
        
        for expense in week_expenses:
            date = expense[3]
            amount = float(expense[0])
            weekly_total += amount
            
            if date not in weekly_by_date:
                weekly_by_date[date] = 0
            weekly_by_date[date] += amount
        
        # Show last 7 days
        response += f"**Weekly Total: RM{weekly_total:.2f}**\n\n"
        
        # Sort dates and show recent days
        sorted_dates = sorted(weekly_by_date.items(), reverse=True)[:7]
        for date, daily_total in sorted_dates:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%a, %b %d")
                response += f"• {formatted_date}: RM{daily_total:.2f}\n"
            except:
                response += f"• {date}: RM{daily_total:.2f}\n"
        
        response += "\n"
    
    # Add monthly prompt at the end
    response += "📈 **Want to see your monthly expenses?** Just say 'show monthly expenses'! 📊"
    
    return response

def show_monthly_expenses(user_email):
    """
    Show this month's expenses with better formatting
    """
    from datetime import datetime
    
    # Get current month info
    now = datetime.now()
    month_name = now.strftime("%B %Y")
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get this month's expenses
        c.execute("""
            SELECT amount, description, category, date
            FROM expenses 
            WHERE user_email = ? AND date >= ?
            ORDER BY date DESC, id DESC
        """, (user_email, month_start))
        
        monthly_expenses = c.fetchall()
        conn.close()
        
    except Exception as e:
        return f"❌ **Error retrieving monthly expenses:** {str(e)}"
    
    response = f"📅 **{month_name}**\n\n"
    
    if not monthly_expenses:
        response += "No expenses recorded this month yet! 💸\n\n"
        response += "Start tracking your daily expenses to see your monthly summary! 😊"
        return response
    
    # Calculate monthly total
    monthly_total = sum(float(exp[0]) for exp in monthly_expenses)
    response += f"**Monthly Total: RM{monthly_total:.2f}**\n\n"
    
    # Group by category
    category_totals = {}
    daily_totals = {}
    
    for expense in monthly_expenses:
        amount = float(expense[0])
        category = expense[2]
        date = expense[3]
        
        # Category totals
        if category not in category_totals:
            category_totals[category] = 0
        category_totals[category] += amount
        
        # Daily totals
        if date not in daily_totals:
            daily_totals[date] = 0
        daily_totals[date] += amount
    
    # Show category breakdown
    response += "💰 **Category Breakdown:**\n"
    for category, total in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        percentage = (total / monthly_total) * 100
        response += f"• {category.title()}: RM{total:.2f} ({percentage:.1f}%)\n"
    
    response += "\n"
    
    # Show recent daily totals (last 10 days)
    response += "📊 **Recent Daily Spending:**\n"
    recent_days = sorted(daily_totals.items(), reverse=True)[:10]
    for date, total in recent_days:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%a, %b %d")
            response += f"• {formatted_date}: RM{total:.2f}\n"
        except:
            response += f"• {date}: RM{total:.2f}\n"
    
    return response

# -------------------------------- UI Layout --------------------------------
# Add a header
st.title("Personal Finance Chatbot")

# Display current date and time
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.write(f"Current date & time: {current_time}")

# Add a sidebar
st.sidebar.title("Navigation")

def create_annotated_chart(spending_data, title="Spending by Category"):
    """Create a bar chart with annotations"""
    # Check if there's data
    if not spending_data:
        return None
        
    # Sort categories by amount
    sorted_categories = sorted(spending_data.items(), key=lambda x: x[1], reverse=True)
    categories = [cat.title() for cat, _ in sorted_categories]
    amounts = [amt for _, amt in sorted_categories]
    
    # Create the figure
    fig = plt.figure(figsize=(10, 5))
    ax = fig.add_subplot(111)
    
    # Create the bar chart
    bars = ax.bar(categories, amounts, color=plt.cm.tab10.colors[:len(categories)])
    
    # Add value annotations on top of each bar
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width()/2.,
            height + 5,
            f'RM{amounts[i]:.0f}',
            ha='center', 
            va='bottom',
            fontsize=9
        )
    
    # Customize the chart
    ax.set_title(title, fontsize=14, pad=20)
    ax.set_xlabel('Category', fontsize=12, labelpad=10)
    ax.set_ylabel('Amount (RM)', fontsize=12, labelpad=10)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Add some padding to the top for the annotations
    ax.set_ylim(0, max(amounts) * 1.15 if amounts else 1)
    
    plt.tight_layout()
    return fig

# Only show page selection if authenticated
if st.session_state.authenticated:
    page = st.sidebar.selectbox("Choose a page", ["Home", "Spending Analysis", "Budget Tracking", "About"])
    
    # Add debug panel
    if st.sidebar.checkbox("Show Debug Info"):
        st.sidebar.subheader("Debug Information")
        
        if "debug_info" in st.session_state:
            st.sidebar.text_area("Debug Log", st.session_state.debug_info, height=300)
        
        if "pending_expense" in st.session_state:
            st.sidebar.write("Pending expense:")
            st.sidebar.write(st.session_state.pending_expense)
        
        if "correction_stage" in st.session_state and st.session_state.correction_stage:
            st.sidebar.write(f"Correction stage: {st.session_state.correction_stage}")
        
        if "custom_categories" in st.session_state and st.session_state.custom_categories:
            st.sidebar.write("Custom categories:")
            st.sidebar.write(st.session_state.custom_categories)
        
        if st.session_state.messages:
            st.sidebar.write("Last message:")
            last_msg = st.session_state.messages[-1]["content"]
            st.sidebar.write(last_msg[:100] + "..." if len(last_msg) > 100 else last_msg)
            
            # Check if last message contains confirmation question
            contains_confirmation = "is that the right category?" in last_msg.lower()
            st.sidebar.write(f"Contains confirmation question: {contains_confirmation}")
    
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.session_state.messages = []  # Clear chat history on logout
        st.rerun()
else:
    page = "Home"

# Authentication section
if not st.session_state.authenticated:
    st.header("Welcome to the Personal Finance Chatbot")
    st.write("Please login or sign up to continue.")
    
    # Create tabs for Login and Sign Up
    tab_list = ["Login", "Sign Up"]
    auth_tab1, auth_tab2 = st.tabs(tab_list)
    
    with auth_tab1:  # Login Tab
        with st.form("login_form"):
            # If coming from successful signup, pre-fill the email
            default_email = st.session_state.signup_email if st.session_state.signup_email else ""
            login_email = st.text_input("Email", value=default_email, key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            login_submitted = st.form_submit_button("Login")
            
            if login_submitted:
                if not login_email or not login_password:
                    st.error("Please fill in all fields.")
                else:
                    users = load_users()
                    hashed_password = hash_password(login_password)
                    
                    if login_email in users and users[login_email]["password"] == hashed_password:
                        st.session_state.authenticated = True
                        st.session_state.current_user = login_email
                        
                        # Initialize messages with a greeting
                        if not st.session_state.messages:
                            # Get a greeting from the greeting intent
                            for intent in intents["intents"]:
                                if intent["tag"] == "greeting":
                                    greeting = random.choice(intent["responses"])
                                    st.session_state.messages.append({"role": "assistant", "content": greeting})
                                    break
                        
                        # Check if it's time for the daily prompt
                        now = datetime.now()
                        st.session_state.last_daily_prompt = now
                        
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")
    
    with auth_tab2:  # Sign Up Tab
        # Show success message if signup was successful
        if st.session_state.signup_success:
            st.success(f"Account created successfully! Your email ({st.session_state.signup_email}) is ready for login. Please switch to the Login tab.")
        
        with st.form("signup_form"):
            signup_name = st.text_input("Full Name", key="signup_name")
            signup_email = st.text_input("Email", key="signup_email_input")
            signup_password = st.text_input("Password", type="password", key="signup_password")
            signup_confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm_password")
            
            # Display password requirements
            st.markdown("""
            **Password requirements:**
            - At least 8 characters long
            - Include at least one letter
            - Include at least one number
            """)
            
            signup_submitted = st.form_submit_button("Sign Up")
            
            if signup_submitted:
                # First validate all inputs before proceeding
                if not signup_name or not signup_email or not signup_password or not signup_confirm_password:
                    st.error("Please fill in all fields.")
                elif not is_valid_email(signup_email):
                    st.error("Please enter a valid email address.")
                elif signup_password != signup_confirm_password:
                    st.error("Passwords do not match.")
                else:
                    # Validate password strength
                    is_valid, password_error = is_valid_password(signup_password)
                    if not is_valid:
                        st.error(password_error)
                    else:
                        users = load_users()
                        
                        if signup_email in users:
                            st.error("Email already exists. Please login instead.")
                        else:
                            # All validations passed, create the user
                            users[signup_email] = {
                                "name": signup_name,
                                "password": hash_password(signup_password),
                                "joined_date": current_time
                            }
                            save_users(users)
                            
                            # Store email for pre-filling login form
                            st.session_state.signup_email = signup_email
                            # Set success flag to show message on next render
                            st.session_state.signup_success = True
                            
                            # Force a rerun to show the success message
                            st.rerun()

# Create different pages based on selection if authenticated
# In your Home page
elif page == "Home":
    # Get user name safely with a fallback
    user_info = load_users().get(st.session_state.current_user, {})
    user_name = user_info.get("name", "User")
    
    # Enhanced welcome header
    st.header(f"Welcome, {user_name}! 👋")

    # ADD THIS NEW SECTION - Quick Action Buttons
    st.subheader("💡 What can I help with?")
    
    # Create three columns for the main action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💰 Track Expenses", 
                    help="Record your daily spending", 
                    use_container_width=True):
            # Simulate user clicking "track expenses"
            st.session_state.messages.append({"role": "user", "content": "track expenses"})
            
            # Process the input and get response
            response = process_user_input("track expenses", st.session_state.current_user)
            
            # Add response to messages
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col2:
        if st.button("📊 Set Budgets", 
                    help="Create and manage your monthly budgets", 
                    use_container_width=True):
            # Simulate user clicking "set budget"
            st.session_state.messages.append({"role": "user", "content": "set budget"})
            
            # Process the input and get response
            response = process_user_input("set budget", st.session_state.current_user)
            
            # Add response to messages
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col3:
        if st.button("🎯 Create Goals", 
                    help="Set financial goals and track progress", 
                    use_container_width=True):
            # Simulate user clicking "set a goal"
            st.session_state.messages.append({"role": "user", "content": "set a goal"})
            
            # Process the input and get response
            response = process_user_input("set a goal", st.session_state.current_user)
            
            # Add response to messages
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()

            # ADD THIS AFTER THE MAIN BUTTONS - Secondary action buttons
    st.caption("🔍 Quick Actions:")
    
    # Create columns for secondary buttons
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📋 View Expenses", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "show my expenses"})
            response = process_user_input("show my expenses", st.session_state.current_user)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col2:
        if st.button("💼 Check Budget", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "show my budget"})
            response = process_user_input("show my budget", st.session_state.current_user)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col3:
        if st.button("🎯 View Goals", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "show my goals"})
            response = process_user_input("show my goals", st.session_state.current_user)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col4:
        if st.button("💡 Get Help", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "help"})
            response = process_user_input("help", st.session_state.current_user)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    # Add a divider between buttons and chat
    st.divider()
    
    # Check if we should prompt for daily expenses
    now = datetime.now()
    if (st.session_state.last_daily_prompt is None or 
        (now - st.session_state.last_daily_prompt).total_seconds() > 8 * 3600):  # Prompt once every 8 hours
        # Add the daily prompt to the messages if it's not already there
        if not st.session_state.messages or "Any spending today?" not in st.session_state.messages[-1].get("content", ""):
            # Get a daily prompt from the daily_prompt intent
            daily_prompt = "Any spending today?"
            for intent in intents["intents"]:
                if intent["tag"] == "daily_prompt":
                    daily_prompt = random.choice(intent["responses"])
                    break
            
            with st.chat_message("assistant"):
                st.markdown(daily_prompt)
            st.session_state.messages.append({"role": "assistant", "content": daily_prompt})
        st.session_state.last_daily_prompt = now
    
    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me about your finances or record an expense..."):
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Process the user's message and generate a response
        response = process_user_input(prompt, st.session_state.current_user)
        
        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            st.markdown(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})

elif page == "Spending Analysis":
    st.markdown("# Spending Analysis 💰")
    st.sidebar.markdown("# Spending Analysis 💰")
    
    # Get the current user's email
    user_email = st.session_state.current_user
    
    # Get current date/time for default values
    current_date = datetime.now()
    current_month = current_date.month
    current_year = current_date.year
    
    # Create date filters in a container at the top
    with st.container():
        st.subheader("Select Time Period")
        col1, col2 = st.columns(2)
        
        with col1:
            # Month selection
            months = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
            selected_month = st.selectbox("Month", months, index=current_month-1)
            # Convert month name to number
            month_num = months.index(selected_month) + 1
        
        with col2:
            # Year selection (allow current year and 2 years back)
            available_years = list(range(current_year-2, current_year+1))
            selected_year = st.selectbox("Year", available_years, index=len(available_years)-1)
    
    # Convert selected month to datetime objects for filtering
    start_date = f"{selected_year}-{month_num:02d}-01"
    if month_num == 12:
        end_date = f"{selected_year+1}-01-01"
    else:
        end_date = f"{selected_year}-{month_num+1:02d}-01"
    
    # Get spending data for the selected period
    spending_data = get_spending_by_category(user_email, month_num, selected_year)
    
    # Get all expenses for the selected period
    expenses = get_expenses(user_email, start_date=start_date, end_date=end_date)
    
    # Create tabs for different views
    analysis_tab1, analysis_tab2, analysis_tab3 = st.tabs(["Overview", "Categories", "Transactions"])
    
    with analysis_tab1:
        st.subheader(f"Spending Overview for {selected_month} {selected_year}")
    
        if spending_data:
            # Calculate total spending
            total_spending = sum(spending_data.values())
            
            # Create a row of metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    label=f"Total Spending",
                    value=f"RM{total_spending:.2f}"
                )
            
            with col2:
                # Transaction count
                st.metric(
                    label="Number of Transactions",
                    value=len(expenses)
                )
            
            with col3:
                # Average transaction
                if len(expenses) > 0:
                    avg_transaction = total_spending / len(expenses)
                    st.metric(
                        label="Average Transaction",
                        value=f"RM{avg_transaction:.2f}"
                    )
            
            # Add a separator
            st.markdown("---")
            
            # Enhanced spending by category chart
            st.subheader("Spending by Category")
            chart_fig = create_annotated_chart(spending_data)
            if chart_fig:
                st.pyplot(chart_fig)
            
            # Display category details in a clean table
            st.subheader("Category Details")
            
            # Create a DataFrame for the table
            table_data = []
            for category, amount in sorted(spending_data.items(), key=lambda x: x[1], reverse=True):
                percentage = (amount / total_spending) * 100
                table_data.append({
                    "Category": category.title(),
                    "Amount": f"RM{amount:.2f}",
                    "Percentage": f"{percentage:.1f}%"
                })
            
            # Display as a clean dataframe
            st.dataframe(pd.DataFrame(table_data), hide_index=True, use_container_width=True)
            
        else:
            st.info(f"No spending data available for {selected_month} {selected_year}. Start recording your expenses to see visualizations.")
            
            # Display sample data for demonstration
            st.subheader("Sample Data (For Demonstration)")
            sample_data = {
                'Food': 250.0,
                'Transport': 150.0,
                'Entertainment': 100.0,
                'Shopping': 200.0,
                'Utilities': 120.0
            }
            
            # Create and display sample chart
            sample_chart_fig = create_annotated_chart(sample_data, "Sample Spending Distribution")
            if sample_chart_fig:
                st.pyplot(sample_chart_fig)
            
            st.caption("This is sample data. Your actual spending will be displayed here once you start recording expenses.")
        
        with analysis_tab2:
            st.subheader(f"Category Analysis for {selected_month} {selected_year}")
            
            if spending_data:
                # Create a pie chart for category breakdown
                fig, ax = plt.subplots(figsize=(10, 6))
                
                # Calculate percentages for pie chart
                total = sum(spending_data.values())
                labels = [f"{cat.title()} (RM{amt:.2f})" for cat, amt in spending_data.items()]
                sizes = [amt for amt in spending_data.values()]
                
                # Create the pie chart with better colors and layout
                colors = plt.cm.tab10.colors[:len(sizes)]
                wedges, texts, autotexts = ax.pie(
                    sizes, 
                    labels=None,  # We'll add a legend instead
                    autopct='%1.1f%%', 
                    startangle=90,
                    colors=colors,
                    shadow=False,
                    wedgeprops={'edgecolor': 'white', 'linewidth': 1}
                )
                
                # Enhance the appearance of percentage text
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontsize(11)
                    autotext.set_fontweight('bold')
                
                # Add a legend
                categories = [cat.title() for cat in spending_data.keys()]
                ax.legend(wedges, categories, title="Categories", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                
                ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
                plt.title(f"Spending by Category - {selected_month} {selected_year}", fontsize=14, pad=20)
                
                st.pyplot(fig)
                
                # Display category details in a table
                st.subheader("Category Details")
                
                # Create a DataFrame for the table
                table_data = []
                for category, amount in sorted(spending_data.items(), key=lambda x: x[1], reverse=True):
                    percentage = (amount / total) * 100
                    table_data.append({
                        "Category": category.title(),
                        "Amount": f"RM{amount:.2f}",
                        "Percentage": f"{percentage:.1f}%"
                    })
                
                st.table(pd.DataFrame(table_data))
                
                # Add monthly trend if we have data from previous months
                st.subheader("Month-to-Month Comparison")
                
                # Get data for previous month
                prev_month_num = month_num - 1 if month_num > 1 else 12
                prev_month_year = selected_year if month_num > 1 else selected_year - 1
                prev_month_name = months[prev_month_num-1]
                
                prev_spending = get_spending_by_category(user_email, prev_month_num, prev_month_year)
                
                if prev_spending:
                    # Create comparison data
                    comparison_data = []
                    all_categories = set(list(spending_data.keys()) + list(prev_spending.keys()))
                    
                    for category in all_categories:
                        current_amount = spending_data.get(category, 0)
                        prev_amount = prev_spending.get(category, 0)
                        change = current_amount - prev_amount
                        change_pct = (change / prev_amount * 100) if prev_amount > 0 else 0
                        
                        comparison_data.append({
                            "Category": category.title(),
                            f"{prev_month_name}": f"RM{prev_amount:.2f}",
                            f"{selected_month}": f"RM{current_amount:.2f}",
                            "Change": f"RM{change:.2f}",
                            "Change %": f"{change_pct:+.1f}%" if prev_amount > 0 else "N/A"
                        })
                    
                    # Sort by current month amount
                    comparison_data.sort(key=lambda x: float(x[f"{selected_month}"].replace("RM", "")), reverse=True)
                    
                    # Display the comparison table
                    st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)
                else:
                    st.info(f"No data available for {prev_month_name} {prev_month_year} to make a comparison.")
            else:
                st.info(f"No spending data available for {selected_month} {selected_year}. Start recording expenses to see category breakdowns.")
    
    with analysis_tab3:
        st.subheader(f"Transactions for {selected_month} {selected_year}")
        
        if expenses:
            # Add category filter
            all_categories = sorted(set(exp["category"].title() for exp in expenses))
            selected_categories = st.multiselect(
                "Filter by category", 
                options=["All Categories"] + all_categories, 
                default=["All Categories"]
            )
            
            # Filter expenses based on selected categories
            filtered_expenses = expenses
            if selected_categories and "All Categories" not in selected_categories:
                filtered_expenses = [exp for exp in expenses if exp["category"].title() in selected_categories]
            
            # Group transactions by date
            grouped_expenses = {}
            for expense in filtered_expenses:
                date = expense["date"]
                if date not in grouped_expenses:
                    grouped_expenses[date] = []
                grouped_expenses[date].append(expense)
            
            # Sort dates in reverse chronological order (newest first)
            sorted_dates = sorted(grouped_expenses.keys(), reverse=True)
            
            # Display transactions grouped by date
            for date in sorted_dates:
                # Format the date header
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%A, %B %d, %Y")
                    
                    # Calculate daily total
                    daily_total = sum(exp["amount"] for exp in grouped_expenses[date])
                    
                    # Create expander for each date
                    with st.expander(f"{formatted_date} - RM{daily_total:.2f}", expanded=True):
                        # Create a DataFrame for this date's transactions
                        date_expenses = grouped_expenses[date]
                        date_df = pd.DataFrame({
                            "Description": [exp["description"] for exp in date_expenses],
                            "Category": [exp["category"].title() for exp in date_expenses],
                            "Amount": [f"RM{exp['amount']:.2f}" for exp in date_expenses]
                        })
                        
                        # Display the DataFrame with a clean index
                        st.dataframe(date_df, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Error formatting date {date}: {str(e)}")
            
            # Add a download button for the filtered transactions
            exp_df = pd.DataFrame(filtered_expenses)
            csv = exp_df.to_csv(index=False)
            st.download_button(
                label=f"Download {selected_month} {selected_year} Transactions",
                data=csv,
                file_name=f"transactions_{selected_month.lower()}_{selected_year}.csv",
                mime="text/csv"
            )
        else:
            st.info(f"No transactions recorded for {selected_month} {selected_year}. Start recording your expenses through the chatbot.")

elif page == "Budget Tracking":
    st.markdown("# Budget Tracking 📊")
    st.sidebar.markdown("# Budget Tracking 📊")
    
    # Get the current user's email
    user_email = st.session_state.current_user
    
    # Get current budgets
    current_month = datetime.now().strftime("%B")
    current_year = datetime.now().year
    budgets = get_budgets(user_email, current_month, current_year)
    
    # Show current budgets if any exist
    if budgets:
        st.subheader("Your Current Budgets")
        
        # Get spending for comparison
        spending = get_spending_by_category(user_email, current_month, current_year)
        
        # Create a DataFrame for budget display
        budget_data = []
        for budget in budgets:
            category = budget["category"]
            budget_amount = budget["amount"]
            spent = spending.get(category, 0)
            remaining = budget_amount - spent
            percent_used = (spent / budget_amount) * 100 if budget_amount > 0 else 0
            
            status = "🟢 Good" if percent_used < 80 else "🟠 Watch" if percent_used < 100 else "🔴 Over"
            
            budget_data.append({
                "Category": category.title(),
                "Budget": f"RM{budget_amount:.2f}",
                "Spent": f"RM{spent:.2f}",
                "Remaining": f"RM{remaining:.2f}",
                "Used": f"{percent_used:.1f}%",
                "Status": status
            })
        
        st.table(pd.DataFrame(budget_data))
        
        # Create a visualization of budget vs. actual
        st.subheader("Budget vs. Actual Spending")
        
        # Prepare data for the chart
        chart_categories = []
        budget_amounts = []
        spent_amounts = []
        
        for budget in budgets:
            category = budget["category"]
            budget_amount = budget["amount"]
            spent = spending.get(category, 0)
            
            chart_categories.append(category.title())
            budget_amounts.append(budget_amount)
            spent_amounts.append(spent)
        
        # Create a DataFrame for the chart
        chart_data = pd.DataFrame({
            'Category': chart_categories,
            'Budget': budget_amounts,
            'Actual': spent_amounts
        })
        
        # Plot the chart
        chart_data = chart_data.set_index('Category')
        st.bar_chart(chart_data)
    
    # Create a simple form to set a budget
    st.subheader("Set a New Budget")
    
    with st.form("budget_form"):
        # Category selection
        categories = ["Food", "Transport", "Entertainment", "Shopping", "Utilities", "Housing", "Healthcare", "Education", "Other"]
        selected_category = st.selectbox("Category", categories)
        
        # Amount input
        budget_amount = st.number_input("Budget Amount (RM)", min_value=0.0, format="%.2f")
        
        # Month selection
        current_month_num = datetime.now().month
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        selected_month = st.selectbox("Month", months, index=current_month_num-1)
        
        # Year selection
        current_year = datetime.now().year
        selected_year = st.selectbox("Year", list(range(current_year-1, current_year+2)), index=1)
        
        # Submit button
        submitted = st.form_submit_button("Set Budget")
        
        if submitted:
            # Set the budget in the database
            success = set_budget(user_email, selected_category.lower(), budget_amount, selected_month, selected_year)
            
            if success:
                st.success(f"Budget of RM{budget_amount:.2f} set for {selected_category} in {selected_month} {selected_year}.")
                st.rerun()  # Refresh to show the new budget

elif page == "Goals":
    st.title("🎯 Your Financial Dreams & Goals")
    st.sidebar.title("🎯 Financial Goals")
    
    # Get the current user's email
    user_email = st.session_state.current_user
    
    # Get user's goals and templates
    goals = get_user_goals(user_email)
    goal_templates = get_smart_goal_suggestions()
    
    # Enhanced header with personality
    if goals:
        # Create a nice header box
        st.success("🌟 **Your Goals Dashboard** - Every goal you achieve brings you closer to financial freedom!")
        
        # Overall progress metrics
        total_target = sum(goal["target_amount"] for goal in goals)
        total_saved = sum(goal["current_amount"] for goal in goals)
        overall_progress = (total_saved / total_target) * 100 if total_target > 0 else 0
        completed_goals = sum(1 for goal in goals if get_enhanced_goal_progress(goal)["progress_percent"] >= 100)
        
        # Enhanced metrics display
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🎯 Active Goals", len(goals))
        
        with col2:
            st.metric("🏆 Completed", completed_goals)
        
        with col3:
            st.metric("💰 Total Saved", f"RM{total_saved:,.2f}")
        
        with col4:
            st.metric("📊 Overall Progress", f"{overall_progress:.1f}%")
        
        # Enhanced motivation message
        if completed_goals > 0:
            st.balloons()
            st.success(f"🎉 **INCREDIBLE!** You've completed {completed_goals} goal{'s' if completed_goals > 1 else ''}! You're building an amazing financial future!")
        elif overall_progress >= 75:
            st.info("🔥 **OUTSTANDING!** You're making fantastic progress! Keep up this incredible momentum!")
        elif overall_progress >= 50:
            st.info("📈 **EXCELLENT WORK!** You're over halfway to your dreams! The momentum is building!")
        elif overall_progress >= 25:
            st.info("🎯 **GREAT START!** You're building solid foundations for your financial future!")
        else:
            st.info("🌱 **EVERY JOURNEY STARTS SOMEWHERE!** You've taken the hardest step - getting started!")
        
        st.divider()
        
        # Enhanced individual goal display
        for i, goal in enumerate(goals):
            progress = get_enhanced_goal_progress(goal)
            suggestions = get_smart_contribution_suggestions(goal, user_email)
            
            # Create goal container
            with st.container():
                # Goal header with enhanced info
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    icon = progress['current_milestone']['icon'] if progress.get('current_milestone') else '🎯'
                    st.subheader(f"{icon} {goal['goal_name']}")
                    st.caption(f"**Goal Type:** {goal['goal_type'].replace('_', ' ').title()}")
                
                with col2:
                    st.metric("Progress", f"{progress['progress_percent']:.1f}%")
                
                with col3:
                    if progress['status_color'] == 'success':
                        st.success(f"**{progress['status']}**")
                    elif progress['status_color'] == 'warning':
                        st.warning(f"**{progress['status']}**")
                    elif progress['status_color'] == 'error':
                        st.error(f"**{progress['status']}**")
                    else:
                        st.info(f"**{progress['status']}**")
                
                # Enhanced progress bar
                st.progress(progress['progress_percent'] / 100, text=f"RM{goal['current_amount']:,.0f} / RM{goal['target_amount']:,.0f}")
                
                # Goal details and insights
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"💭 **Status:** {progress['status_msg']}")
                    st.write(f"🎯 **Next Action:** {progress['next_action']}")
                    
                    # Show milestone achievement
                    if progress.get("current_milestone"):
                        st.write(f"🏅 **Milestone:** {progress['current_milestone']['message']}")
                    
                    # Progress insights
                    if progress["velocity_status"] == "ahead":
                        st.success(f"🚀 You're saving faster than needed! At this pace, you'll finish early!")
                    elif progress["velocity_status"] == "behind":
                        st.warning(f"⚡ Consider increasing contributions to stay on track!")
                
                with col2:
                    st.write(f"**💰 Remaining:** RM{progress['remaining_amount']:,.2f}")
                    st.write(f"**📅 Days Left:** {progress['days_remaining']} days")
                    if progress['days_remaining'] > 0:
                        st.write(f"**💡 Weekly Target:** RM{progress['weekly_target']:.2f}")
                        st.write(f"**📈 Daily Target:** RM{progress['daily_target']:.2f}")
                
                # Enhanced goal details
                details_display = format_goal_details_display(goal)
                if details_display:
                    with st.expander("📋 Goal Details", expanded=False):
                        st.markdown(details_display)
                
                # Smart contribution section
                with st.expander("💰 Make a Contribution", expanded=False):
                    contrib_col1, contrib_col2 = st.columns([2, 1])
                    
                    with contrib_col1:
                        st.write("**🚀 Smart Contribution Suggestions:**")
                        
                        # Quick amount buttons
                        if suggestions:
                            button_cols = st.columns(min(4, len(suggestions)))
                            for idx, suggestion in enumerate(suggestions[:4]):
                                with button_cols[idx]:
                                    if st.button(f"RM{suggestion['amount']:.0f}", 
                                               key=f"quick_{goal['id']}_{idx}", 
                                               help=suggestion['description'],
                                               use_container_width=True):
                                        success = add_goal_contribution(goal['id'], user_email, suggestion['amount'], f"Quick contribution: {suggestion['description']}")
                                        if success:
                                            st.success(f"🎉 Added RM{suggestion['amount']:.2f}!")
                                            st.rerun()
                        
                        # Custom amount form
                        with st.form(f"contrib_form_{goal['id']}"):
                            custom_amount = st.number_input("Custom Amount (RM)", min_value=0.0, format="%.2f", key=f"custom_{goal['id']}")
                            contrib_note = st.text_input("Note (optional)", placeholder="e.g., Birthday money, side hustle earnings")
                            
                            if st.form_submit_button("💫 Add Contribution", type="primary", use_container_width=True):
                                if custom_amount > 0:
                                    success = add_goal_contribution(goal['id'], user_email, custom_amount, contrib_note or f"Custom contribution")
                                    if success:
                                        st.balloons()
                                        st.success(f"🎉 Amazing! Added RM{custom_amount:.2f} to {goal['goal_name']}!")
                                        st.rerun()
                                else:
                                    st.error("Please enter an amount to contribute! Every ringgit counts!")
                    
                    with contrib_col2:
                        st.write("**📊 Contribution Impact:**")
                        if custom_amount and custom_amount > 0:
                            new_progress = ((goal['current_amount'] + custom_amount) / goal['target_amount']) * 100
                            st.write(f"New Progress: {new_progress:.1f}%")
                            st.write(f"Remaining: RM{goal['target_amount'] - goal['current_amount'] - custom_amount:.2f}")
                        else:
                            st.info("Enter an amount above to see the impact!")
                
                st.divider()
    
    else:
        # Enhanced empty state
        st.info("🎯 **Welcome to Your Goals Journey!**")
        st.write("Turn your dreams into achievable financial plans!")
        
        st.markdown("""
        ### 🌟 Why Set Financial Goals?
        
        **Goals transform wishes into reality!** Here's why you should start today:
        
        🎯 **Clear Direction** - Know exactly what you're saving for  
        💪 **Stay Motivated** - Track progress and celebrate wins  
        📈 **Build Discipline** - Develop consistent saving habits  
        🏆 **Achieve More** - People with written goals achieve 42% more!  
        """)
    
     # Enhanced goal creation form
    st.divider()
    st.subheader("✨ Create Your Next Goal")
    
    # Goal template suggestions
    st.write("### 🚀 Popular Goal Templates")
    
    template_cols = st.columns(3)
    for idx, (template_key, template) in enumerate(list(goal_templates.items())[:3]):
        with template_cols[idx % 3]:
            with st.container():
                st.info(f"**{template['icon']} {template['name']}**")
                st.caption(template['description'])
                st.write(f"**Amount Range:** RM{min(template['suggested_amounts']):,} - RM{max(template['suggested_amounts']):,}")
                st.caption(f"💡 {template['tips']}")
                
                if st.button(f"Use {template['name']} Template", key=f"template_{template_key}", use_container_width=True):
                    st.session_state[f"selected_template"] = template_key
                    st.rerun()
    
    # Enhanced goal creation form
    with st.form("enhanced_goal_form"):
        st.write("### 🎯 Create Custom Goal")
        
        # Check if template was selected
        selected_template_key = st.session_state.get("selected_template")
        selected_template = goal_templates.get(selected_template_key) if selected_template_key else None
        
        col1, col2 = st.columns(2)
        
        with col1:
            goal_name = st.text_input(
                "🎯 Goal Name", 
                value=selected_template["name"] if selected_template else "",
                placeholder="e.g., Dream Vacation to Japan",
                help="Give your goal an inspiring name!"
            )
            
            goal_type = st.selectbox("📂 Goal Category", [
                "emergency_fund", "vacation", "car", "house", "electronics", 
                "education", "debt_payoff", "investment", "wedding", "other"
            ], 
            index=list(goal_templates.keys()).index(selected_template_key) if selected_template_key and selected_template_key in goal_templates else 0,
            format_func=lambda x: {
                "emergency_fund": "💰 Emergency Fund",
                "vacation": "🏖️ Vacation", 
                "car": "🚗 Car",
                "house": "🏠 House/Property",
                "electronics": "💻 Electronics/Tech",
                "education": "🎓 Education",
                "debt_payoff": "💳 Debt Payoff",
                "investment": "📈 Investment",
                "wedding": "💍 Wedding",
                "other": "📦 Other"
            }[x])
            
            # Smart amount suggestions
            if selected_template:
                suggested_amount = st.selectbox(
                    "💰 Suggested Amounts",
                    selected_template["suggested_amounts"],
                    format_func=lambda x: f"RM{x:,}"
                )
                target_amount = st.number_input("💰 Or Enter Custom Amount", value=float(suggested_amount), min_value=0.0, format="%.2f")
            else:
                target_amount = st.number_input("💰 Target Amount", min_value=0.0, format="%.2f")
        
        with col2:
            target_date = st.date_input(
                "📅 Target Date", 
                min_value=datetime.now().date(),
                value=datetime.now().date() + timedelta(days=365),
                help="When do you want to achieve this goal?"
            )
            
            # Smart timeline suggestions
            if selected_template:
                suggested_months = st.selectbox(
                    "⏰ Suggested Timeline",
                    selected_template["timeline_months"],
                    format_func=lambda x: f"{x} months"
                )
                if st.checkbox("Use suggested timeline"):
                    target_date = datetime.now().date() + timedelta(days=suggested_months * 30)
            
            monthly_contribution = st.number_input(
                "📈 Planned Monthly Savings", 
                min_value=0.0, 
                format="%.2f",
                help="How much can you save monthly?"
            )
        
        # Goal feasibility analysis
        if target_amount > 0:
            feasibility = calculate_goal_feasibility(target_amount, target_date, user_email)
            priority = get_goal_priority_suggestion(user_email, goal_type)
            
            st.write("### 📊 Goal Analysis")
            col1, col2 = st.columns(2)
            
            with col1:
                if feasibility['difficulty'] == 'easy':
                    st.success(f"**Feasibility:** {feasibility['feasibility']}\n\n{feasibility['message']}")
                elif feasibility['difficulty'] == 'medium':
                    st.info(f"**Feasibility:** {feasibility['feasibility']}\n\n{feasibility['message']}")
                elif feasibility['difficulty'] == 'hard':
                    st.warning(f"**Feasibility:** {feasibility['feasibility']}\n\n{feasibility['message']}")
                else:
                    st.error(f"**Feasibility:** {feasibility['feasibility']}\n\n{feasibility['message']}")
            
            with col2:
                st.info(f"**Priority Suggestion:**\n\n{priority}")
        
        # Enhanced goal details
        st.divider()
        st.write("### 📋 Goal Details (Highly Recommended)")
        st.caption("*Adding specific details makes your goal 10x more likely to be achieved!*")
        
        goal_details = get_goal_details_form(goal_type)
        
        # Enhanced submit button
        if st.form_submit_button("🚀 Create My Amazing Goal!", type="primary", use_container_width=True):
            if goal_name and target_amount > 0:
                target_date_str = target_date.strftime("%Y-%m-%d")
                success, goal_id = add_goal(
                    user_email, goal_name, goal_type, target_amount, 
                    target_date_str, monthly_contribution, goal_details
                )
                
                if success:
                    # Clear template selection
                    if "selected_template" in st.session_state:
                        del st.session_state["selected_template"]
                    
                    st.balloons()
                    st.success("🎉 **GOAL CREATED!** Your dream is now a plan! Let's make it happen!")
                    st.rerun()
                else:
                    st.error("Oops! Something went wrong. Please try again!")
            else:
                st.error("Please fill in the goal name and target amount!")
        
elif page == "About":
    st.header("About Personal Finance Chatbot")
    st.write("""
    This Personal Finance Chatbot is designed to make it easy for users to record daily expenses through simple interactive conversations. 
    The goal is to encourage better money management by providing insights into spending patterns and giving personalized savings advice.
    
    ### Features:
    1. **Daily Spending Logging**: Easily record your expenses through chat
    2. **Spending Analysis**: View your spending patterns by category
    3. **Savings Advice**: Get personalized tips based on your spending habits
    4. **Budget Tracking**: Set and track your monthly budget
    
    ### How to Use:
    - **Record an expense**: Type something like "I spent RM50 on groceries" or "RM20 for lunch"
    - **View your expenses**: Ask "Show me my recent expenses" or "What did I spend money on?"
    - **Get spending summary**: Ask "What's my spending summary?" or "Show me my spending by category"
    - **Budget management**: Say "Set a budget" or check "How am I doing on my budget?"
    - **Savings advice**: Ask "How can I save money?" for personalized tips
    
    ### Privacy:
    Your financial data is stored securely and is only accessible to you when logged in.
    """)