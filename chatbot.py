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

# Set page configuration
st.set_page_config(page_title="Personal Finance Chatbot", page_icon="📊")

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
    
    conn.commit()
    conn.close()

# Call init_db to ensure tables exist
init_db()

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
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        date = datetime.now().strftime("%Y-%m-%d")
        c.execute("INSERT INTO expenses (user_email, amount, description, category, date) VALUES (?, ?, ?, ?, ?)",
                 (user_email, amount, description, category, date))
        last_id = c.lastrowid
        conn.commit()
        conn.close()
        return True, last_id
    except Exception as e:
        st.error(f"Error adding expense: {str(e)}")
        return False, None

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
    
    # Standard categories with their keywords
    categories = {
        "food": ["grocery", "groceries", "restaurant", "lunch", "dinner", "breakfast", "food", "meal", "coffee", 
                 "snack", "eat", "eating", "dining", "dine", "cafe", "cafeteria", "fastfood", "fast food", "drinks",
                 "takeout", "take-out", "takeaway", "take-away", "pizza", "burger", "sushi", "dessert", "desert", 
                 "ice cream", "cake", "pastry", "bakery", "tissue"],
        
        "transport": ["gas", "fuel", "bus", "train", "taxi", "grab", "uber", "lyft", "fare", "ticket", "transport",
                      "transportation", "commute", "travel", "subway", "mrt", "lrt", "petrol", "diesel", "car", 
                      "ride", "toll", "parking"],
        
        "entertainment": ["movie", "cinema", "ktv", "karaoke", "game", "concert", "show", "entertainment", "fun", 
                         "leisure", "theater", "theatre", "park", "ticket", "streaming", "subscription", "netflix", 
                         "spotify", "disney"],
        
        "shopping": ["clothes", "clothing", "shoes", "shirt", "dress", "pants", "fashion", "mall", "shop", 
                    "shopping", "boutique", "store", "retail", "buy", "purchase", "merchandise", "apparel", 
                    "accessories", "jewelry", "gift", "lipstick", "cosmetics", "makeup"],
        
        "utilities": ["electricity", "electric", "water", "bill", "utility", "phone", "internet", "wifi", "service",
                     "broadband", "gas", "subscription", "cable", "tv", "television", "streaming"],
        
        "housing": ["rent", "mortgage", "housing", "apartment", "house", "accommodation", "condo", "condominium", 
                   "room", "deposit", "lease", "property", "maintenance", "repair", "renovation"],
        
        "healthcare": ["doctor", "clinic", "hospital", "medicine", "medical", "health", "healthcare", "prescription", 
                      "pharmacy", "dental", "dentist", "vitamin", "supplement", "drug", "treatment", "therapy", 
                      "checkup", "insurance"],
        
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
def get_expenses(user_email, limit=None, start_date=None, end_date=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    query = "SELECT * FROM expenses WHERE user_email = ?"
    params = [user_email]
    
    if start_date and end_date:
        query += " AND date BETWEEN ? AND ?"
        params.extend([start_date, end_date])
    
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
            expenses_text = ""
            for exp in expenses:
                expenses_text += f"• **{exp['date']}**: RM{exp['amount']:.2f} for **{exp['description']}** ({exp['category'].title()})\n\n"
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
                    "• Keep up with regular vehicle maintenance to avoid costly repairs"
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

def process_user_input(input_text, user_email):
    """
    Process user input, handling expense entry, confirmation, and general queries.
    """
    # Debug info for tracing issues
    debug_info = []
    debug_info.append(f"Input: {input_text}")
    debug_info.append(f"Messages count: {len(st.session_state.messages) if 'messages' in st.session_state else 0}")
    debug_info.append(f"Has pending_expense: {'pending_expense' in st.session_state}")
    
    # IMPORTANT FIX: We need to look at the assistant's last message, not the user's
    # Find the last assistant message
    assistant_messages = [msg for msg in st.session_state.messages if msg["role"] == "assistant"]
    
    if assistant_messages and "pending_expense" in st.session_state:
        last_assistant_msg = assistant_messages[-1]["content"].lower()
        debug_info.append(f"Last assistant message: {last_assistant_msg[:50]}...")
        debug_info.append(f"Contains 'right category': {'is that the right category?' in last_assistant_msg}")
        
        # CASE 1: Check if the last assistant message was asking about category confirmation
        if "is that the right category?" in last_assistant_msg:
            input_lower = input_text.lower().strip()
            debug_info.append(f"In confirmation flow, input: {input_lower}")
            
            # Handle YES responses
            if input_lower == "yes" or input_lower == "y" or input_lower == "yeah" or input_lower == "correct" or input_lower == "that's right" or input_lower == "right" or input_lower == "yep" or input_lower == "yup" or input_lower == "sure":
                debug_info.append("Detected YES response")
                # User confirmed the category - finalize the expense
                del st.session_state.pending_expense
                st.session_state.debug_info = "\n".join(debug_info)
                return "Great! Your expense has been recorded successfully. What else can I help you with today?"
            
            # Handle NO responses
            elif input_lower == "no" or input_lower == "n" or input_lower == "nope" or "change" in input_lower or "wrong" in input_lower or "incorrect" in input_lower:
                debug_info.append(f"Detected NO response: {input_lower}")
                # Set state to collect new category
                st.session_state.correction_stage = "ask_what_to_change"
                st.session_state.debug_info = "\n".join(debug_info)
                return "What would you like to change - the category or the amount?"
            
            # If we don't recognize the response, ask again
            else:
                debug_info.append("Unclear response")
                st.session_state.debug_info = "\n".join(debug_info)
                return "I didn't understand that. Is the category correct? Please answer with yes or no."
    
    # The rest of the function remains the same...
    # CASE 2: Asking what to change (category or amount)
    if "correction_stage" in st.session_state and st.session_state.correction_stage == "ask_what_to_change" and "pending_expense" in st.session_state:
        input_lower = input_text.lower().strip()
        debug_info.append(f"In correction stage 'ask_what_to_change', input: {input_lower}")
        
        # Handle CATEGORY change request
        if "category" in input_lower or "type" in input_lower or "classification" in input_lower or "group" in input_lower:
            debug_info.append("User wants to change category")
            st.session_state.correction_stage = "change_category"
            
            standard_categories = ["food", "transport", "entertainment", "shopping", 
                                 "utilities", "housing", "healthcare", "education", "other"]
            categories_list = ", ".join([cat.title() for cat in standard_categories])
            
            st.session_state.debug_info = "\n".join(debug_info)
            return f"What category would you like to use instead? Choose from: {categories_list}, or type a custom category."
        
        # Handle AMOUNT change request
        elif "amount" in input_lower or "value" in input_lower or "cost" in input_lower or "price" in input_lower or "rm" in input_lower or "money" in input_lower or "expense" in input_lower:
            debug_info.append("User wants to change amount")
            st.session_state.correction_stage = "change_amount"
            st.session_state.debug_info = "\n".join(debug_info)
            return "What is the correct amount for this expense?"
        
        # Default to category change if unclear
        else:
            debug_info.append("Defaulting to category change")
            st.session_state.correction_stage = "change_category"
            
            standard_categories = ["food", "transport", "entertainment", "shopping", 
                                 "utilities", "housing", "healthcare", "education", "other"]
            categories_list = ", ".join([cat.title() for cat in standard_categories])
            
            st.session_state.debug_info = "\n".join(debug_info)
            return f"I'll help you change the category. What category would you like to use instead? Choose from: {categories_list}, or type a custom category."
    
    # CASE 3: Changing the category
    elif "correction_stage" in st.session_state and st.session_state.correction_stage == "change_category" and "pending_expense" in st.session_state:
        # User is providing a new category
        new_category = input_text.lower().strip()
        debug_info.append(f"In correction stage 'change_category', new category: {new_category}")
        
        # Check for standard categories
        standard_categories = ["food", "transport", "entertainment", "shopping", 
                             "utilities", "housing", "healthcare", "education", "other"]
        
        category_match = new_category
        
        # Try to match with standard categories
        for category in standard_categories:
            if category in new_category:
                category_match = category
                break
        
        # If no match with standard categories, treat as custom category
        if category_match not in standard_categories:
            debug_info.append(f"Adding custom category: {category_match}")
            add_custom_category(category_match)
        
        # Update the expense category in the database
        expense_id = st.session_state.pending_expense["id"]
        
        if update_expense_category(expense_id, category_match):
            # Reset correction mode
            st.session_state.correction_stage = None
            # Clear pending expense
            del st.session_state.pending_expense
            
            st.session_state.debug_info = "\n".join(debug_info)
            return f"I've updated the category to '{category_match}'. Your expense has been recorded successfully."
        else:
            st.session_state.debug_info = "\n".join(debug_info)
            return "Sorry, I had trouble updating the category. Can you try again?"
    
    # CASE 4: Changing the amount
    elif "correction_stage" in st.session_state and st.session_state.correction_stage == "change_amount" and "pending_expense" in st.session_state:
        # Extract the new amount
        input_lower = input_text.lower().strip()
        debug_info.append(f"In correction stage 'change_amount', input: {input_lower}")
        
        # Try to get a numeric amount
        amount_match = re.search(r"(\d+\.?\d*)", input_lower)
        if amount_match:
            try:
                new_amount = float(amount_match.group(1))
                debug_info.append(f"Extracted amount: {new_amount}")
                
                # Update the expense amount in the database
                expense_id = st.session_state.pending_expense["id"]
                
                if update_expense_amount(expense_id, new_amount):
                    # Reset correction mode
                    st.session_state.correction_stage = None
                    # Clear pending expense
                    del st.session_state.pending_expense
                    
                    st.session_state.debug_info = "\n".join(debug_info)
                    return f"I've updated the amount to RM{new_amount:.2f}. Your expense has been recorded successfully."
                else:
                    st.session_state.debug_info = "\n".join(debug_info)
                    return "Sorry, I had trouble updating the amount. Can you try again?"
            except Exception as e:
                debug_info.append(f"Error: {str(e)}")
                st.session_state.debug_info = "\n".join(debug_info)
                return f"I couldn't understand that amount. Please provide a number like '25' or '25.50'."
        else:
            debug_info.append("No numeric amount found")
            st.session_state.debug_info = "\n".join(debug_info)
            return "I couldn't find a valid amount in your message. Please just provide the number, like '25' or '25.50'."
    
    # Step 2: If not in a confirmation flow, check if input is an expense
    debug_info.append("Not in confirmation flow or confirmation condition not met")
    entities = extract_entities(input_text)
    debug_info.append(f"Extracted entities: {entities}")
    
    if "amount" in entities and "description" in entities:
        amount = entities["amount"]
        description = entities["description"]
        category = entities.get("category", categorize_expense(description))
        debug_info.append(f"Detected expense: {amount} for {description} in {category}")
        
        # Add to database
        success, expense_id = add_expense(user_email, amount, description, category)
        
        if success:
            # Store in session state for potential updates
            st.session_state.pending_expense = {
                "id": expense_id,
                "amount": amount,
                "description": description,
                "category": category
            }
            debug_info.append(f"Added expense to DB, id: {expense_id}")
            
            # Store debug info
            st.session_state.debug_info = "\n".join(debug_info)
            
            # Ask for confirmation
            return f"I've recorded your expense: RM{amount:.2f} for {description} in the '{category}' category. Is that the right category?"
        else:
            debug_info.append("Failed to add expense to DB")
            st.session_state.debug_info = "\n".join(debug_info)
            return "I couldn't record your expense. Please try again with format like 'spent RM50 on lunch'."
    
    # Step 3: If not a confirmation or direct expense, handle with intents
    debug_info.append("Processing as regular intent")
    intent_tag, confidence = predict_intent(input_text, intents)
    debug_info.append(f"Predicted intent: {intent_tag} with confidence: {confidence}")
    
    # If it looks like an expense but the intent wasn't detected correctly
    if "amount" in entities and "description" in entities and intent_tag != "expense_add":
        debug_info.append("Overriding intent to expense_add")
        intent_tag = "expense_add"  # Override the intent
    
    # Store debug info
    st.session_state.debug_info = "\n".join(debug_info)
    
    # Handle budget_set intent specifically
    if intent_tag == "budget_set":
        # Check if we're in the middle of a budget setting conversation
        if "budget_conversation" in st.session_state:
            stage = st.session_state.budget_conversation["stage"]
            
            if stage == "ask_amount":
                # User is responding with an amount
                amount_match = re.search(r"(\d+\.?\d*)", input_text)
                if amount_match:
                    try:
                        amount = float(amount_match.group(1))
                        # Store the amount and move to confirmation stage
                        st.session_state.budget_conversation["amount"] = amount
                        st.session_state.budget_conversation["stage"] = "confirm"
                        
                        category = st.session_state.budget_conversation["category"]
                        return f"Confirm: Set budget of RM{amount:.2f} for {category.title()}? Type 'YES' to confirm or 'NO' to cancel."
                    except ValueError:
                        return "I couldn't understand that amount. Please provide a number like '500' or '500.50'."
                else:
                    return "I couldn't find a valid amount in your message. Please provide a number like '500' or '500.50'."
            
            elif stage == "confirm":
                # User is confirming the budget
                if input_text.lower() in ["yes", "y", "confirm", "ok"]:
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
                        return f"Great! I've set your budget for {category.title()} to RM{amount:.2f} for {month} {year}."
                    else:
                        return "Sorry, I couldn't set that budget. Please try again."
                
                elif input_text.lower() in ["no", "n", "cancel"]:
                    # Clear the conversation state
                    del st.session_state.budget_conversation
                    return "Budget setting cancelled. What would you like to do instead?"
                
                else:
                    return "Please type 'YES' to confirm or 'NO' to cancel the budget setting."
        
        else:
            # New budget request - try to extract category from the message
            category = None
            
            # Check if the message contains a category
            category_keywords = {
                "food": ["food", "groceries", "eating", "restaurant", "lunch", "dinner", "breakfast"],
                "transport": ["transport", "transportation", "gas", "fuel", "bus", "train", "taxi", "grab"],
                "entertainment": ["entertainment", "movies", "games", "fun", "leisure", "cinema"],
                "shopping": ["shopping", "clothes", "items", "purchases", "mall", "store"],
                "utilities": ["utilities", "bills", "electricity", "water", "internet", "phone"],
                "housing": ["housing", "rent", "mortgage", "home", "apartment"],
                "healthcare": ["healthcare", "medical", "health", "doctor", "hospital"],
                "education": ["education", "school", "books", "courses", "tuition"],
                "other": ["other", "misc", "miscellaneous"]
            }
            
            input_lower = input_text.lower()
            for cat, keywords in category_keywords.items():
                for keyword in keywords:
                    if keyword in input_lower:
                        category = cat
                        break
                if category:
                    break
            
            if category:
                # Found a category in the initial request
                st.session_state.budget_conversation = {
                    "stage": "ask_amount",
                    "category": category
                }
                return f"Sure! How much would you like to budget for {category.title()}? (e.g., RM500)"
            else:
                # No category found, ask for it
                st.session_state.budget_conversation = {"stage": "ask_category"}
                return "Which category would you like to set a budget for? (Food, Transport, Entertainment, Shopping, Utilities, Housing, Healthcare, Education, Other)"
    
    # Handle responses in the middle of budget conversation
    # Replace the entire budget conversation section with this more robust version:

    # In the budget conversation section, replace the category detection part with this:

    elif "budget_conversation" in st.session_state:
        stage = st.session_state.budget_conversation["stage"]
    
    # First, check if user wants to cancel or change their mind
    cancel_words = ["cancel", "stop", "nevermind", "never mind", "forget it", "change mind"]
    if any(word in input_text.lower() for word in cancel_words):
        del st.session_state.budget_conversation
        return "Okay, cancelled the budget setting. What would you like to do instead?"
    
    # Check if user is trying to specify a different category
    input_lower = input_text.lower()
    
    # Simple category detection - check for category keywords directly
    if "food" in input_lower or "grocery" in input_lower or "restaurant" in input_lower:
        new_category = "food"
    elif "transport" in input_lower or "bus" in input_lower or "train" in input_lower or "taxi" in input_lower or "gas" in input_lower:
        new_category = "transport"
    elif "entertainment" in input_lower or "movie" in input_lower or "game" in input_lower or "fun" in input_lower:
        new_category = "entertainment"
    elif "shopping" in input_lower or "clothes" in input_lower or "mall" in input_lower or "store" in input_lower:
        new_category = "shopping"
    elif "utilities" in input_lower or "bill" in input_lower or "electric" in input_lower or "water" in input_lower or "internet" in input_lower:
        new_category = "utilities"
    elif "housing" in input_lower or "rent" in input_lower or "mortgage" in input_lower or "home" in input_lower:
        new_category = "housing"
    elif "health" in input_lower or "medical" in input_lower or "doctor" in input_lower:
        new_category = "healthcare"
    elif "education" in input_lower or "school" in input_lower or "book" in input_lower:
        new_category = "education"
    elif "other" in input_lower or "misc" in input_lower:
        new_category = "other"
    else:
        new_category = None
    
    # If user specified a new category during the conversation
    if new_category:
        if stage == "ask_amount":
            # User changed their mind about category
            st.session_state.budget_conversation["category"] = new_category
            return f"Okay, changed to {new_category.title()}. How much would you like to budget for {new_category.title()}? (e.g., RM500)"
        elif stage == "confirm":
            # User changed their mind during confirmation
            st.session_state.budget_conversation["category"] = new_category
            st.session_state.budget_conversation["stage"] = "ask_amount"
            return f"Okay, changed to {new_category.title()}. How much would you like to budget for {new_category.title()}? (e.g., RM500)"
        else:
            # If we're in ask_category stage but user specified a category, use it
            st.session_state.budget_conversation["category"] = new_category
            st.session_state.budget_conversation["stage"] = "ask_amount"
            return f"Sure! How much would you like to budget for {new_category.title()}? (e.g., RM500)"
    
    # Normal conversation flow
    if stage == "ask_category":
        # User is providing a category
        category = input_text.lower().strip()
        
        # Simple category mapping
        if "food" in category or "grocery" in category or "restaurant" in category:
            selected_category = "food"
        elif "transport" in category or "bus" in category or "train" in category or "taxi" in category:
            selected_category = "transport"
        elif "entertainment" in category or "movie" in category or "game" in category:
            selected_category = "entertainment"
        elif "shopping" in category or "clothes" in category or "mall" in category:
            selected_category = "shopping"
        elif "utilities" in category or "bill" in category or "electric" in category:
            selected_category = "utilities"
        elif "housing" in category or "rent" in category or "mortgage" in category:
            selected_category = "housing"
        elif "health" in category or "medical" in category or "doctor" in category:
            selected_category = "healthcare"
        elif "education" in category or "school" in category or "book" in category:
            selected_category = "education"
        else:
            selected_category = "other"
        
        # Store the category and move to next stage
        st.session_state.budget_conversation["category"] = selected_category
        st.session_state.budget_conversation["stage"] = "ask_amount"
        return f"Sure! How much would you like to budget for {selected_category.title()}? (e.g., RM500)"
    
    elif stage == "ask_amount":
        # User is responding with an amount
        amount_match = re.search(r"(\d+\.?\d*)", input_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1))
                # Store the amount and move to confirmation stage
                st.session_state.budget_conversation["amount"] = amount
                st.session_state.budget_conversation["stage"] = "confirm"
                
                category = st.session_state.budget_conversation["category"]
                return f"Confirm: Set budget of RM{amount:.2f} for {category.title()}? Type 'YES' to confirm or 'NO' to cancel."
            except ValueError:
                return "I couldn't understand that amount. Please provide a number like '500' or '500.50'."
        else:
            # If no amount found, check if user wants to change category
            if "change" in input_lower or "different" in input_lower:
                st.session_state.budget_conversation["stage"] = "ask_category"
                return "Which category would you like to set a budget for instead? (Food, Transport, Entertainment, Shopping, Utilities, Housing, Healthcare, Education, Other)"
            else:
                return "I couldn't find a valid amount. Please provide a number like '500' or '500.50'. Or say 'change category' if you want to pick a different category."
    
    elif stage == "confirm":
        # User is confirming the budget
        if input_text.lower() in ["yes", "y", "confirm", "ok"]:
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
                return f"Great! ✅ I've set your budget for {category.title()} to RM{amount:.2f} for {month} {year}."
            else:
                return "Sorry, I couldn't set that budget. Please try again."
        
        elif input_text.lower() in ["no", "n", "cancel"]:
            # Clear the conversation state
            del st.session_state.budget_conversation
            return "Budget setting cancelled. What would you like to do instead?"
        
        else:
            # Check if user wants to change amount or category during confirmation
            if "change amount" in input_lower or "different amount" in input_lower:
                st.session_state.budget_conversation["stage"] = "ask_amount"
                return f"How much would you like to budget for {st.session_state.budget_conversation['category'].title()} instead?"
            elif "change category" in input_lower or "different category" in input_lower:
                st.session_state.budget_conversation["stage"] = "ask_category"
                return "Which category would you like to set a budget for instead? (Food, Transport, Entertainment, Shopping, Utilities, Housing, Healthcare, Education, Other)"
            else:
                return "Please type 'YES' to confirm or 'NO' to cancel. Or say 'change amount' or 'change category' if you want to make changes."

    # Get response based on intent for all other intents
    try:
    # Use get_response to handle regular intents
        return get_response(intent_tag, input_text, user_email)
    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
    return "I'm having trouble understanding that. Could you try rephrasing your request?"

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