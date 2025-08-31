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
    else:
        # Show all categories
        budget_text = f"**All Budgets for {month} {year}:**\n\n"
        total_budget = 0
        total_spent = 0
        
        for budget in budgets:
            category_name = budget["category"]
            budget_amount = budget["amount"]
            spent = spending.get(category_name, 0)
            remaining = budget_amount - spent
            percent_used = (spent / budget_amount) * 100 if budget_amount > 0 else 0
            
            status = "🟢 Good" if percent_used < 80 else "🟠 Watch" if percent_used < 100 else "🔴 Over"
            
            budget_text += f"• **{category_name.title()}**: RM{spent:.2f} of RM{budget_amount:.2f} ({percent_used:.1f}%) - {status}\n\n"
            total_budget += budget_amount
            total_spent += spent
        
        # Add totals
        total_remaining = total_budget - total_spent
        total_percent = (total_spent / total_budget) * 100 if total_budget > 0 else 0
        budget_text += f"**Totals:** RM{total_spent:.2f} of RM{total_budget:.2f} ({total_percent:.1f}%) spent, RM{total_remaining:.2f} remaining"
    
    return budget_text

# -------------------------------- Goals Functions -------------------------------
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
    
    return intent_tag, confidence

# Helper function to create the goal with details (FIXED)
def process_goal_creation():
    """Process the final goal creation with all collected details"""
    user_email = st.session_state.current_user  # Get user email
    goal_name = st.session_state.goal_conversation["goal_name"]
    amount = st.session_state.goal_conversation["amount"]
    target_date = st.session_state.goal_conversation["target_date"]
    goal_type = st.session_state.goal_conversation["goal_type"]
    details = st.session_state.goal_conversation.get("details", {})
    
    target_date_str = target_date.strftime("%Y-%m-%d")
    
    success, goal_id = add_goal(user_email, goal_name, goal_type, amount, target_date_str, 0, details)
    
    # Clear conversation state
    del st.session_state.goal_conversation
    
    if success:
        # Calculate helpful information
        today = datetime.now()
        days_until = (target_date - today).days
        months_until = max(1, days_until / 30.44)
        monthly_suggestion = amount / months_until
        weekly_suggestion = amount / (days_until / 7) if days_until > 0 else amount
        
        # Create detailed summary based on goal type and details
        details_summary = ""
        if goal_type == "car" and details:
            if details.get("brand") and details.get("model"):
                details_summary = f"\n🚗 **Your Dream Car**: {details['brand']} {details['model']}"
                if details.get("condition"):
                    details_summary += f" ({details['condition']})"
        elif goal_type == "vacation" and details:
            vacation_info = []
            if details.get("destination"):
                vacation_info.append(f"📍 Destination: {details['destination']}")
            if details.get("duration"):
                vacation_info.append(f"⏰ Duration: {details['duration']}")
            if details.get("travel_style"):
                vacation_info.append(f"✈️ Style: {details['travel_style']}")
            if vacation_info:
                details_summary = f"\n🏖️ **Trip Details**:\n" + "\n".join([f"• {info}" for info in vacation_info])
        elif goal_type == "electronics" and details:
            device_info = []
            if details.get("device_type"):
                device_info.append(f"📱 Device: {details['device_type']}")
            if details.get("brand"):
                device_info.append(f"🏷️ Brand: {details['brand']}")
            if details.get("model"):
                device_info.append(f"📦 Model: {details['model']}")
            if details.get("usage"):
                device_info.append(f"🎯 Use: {details['usage']}")
            if device_info:
                details_summary = f"\n💻 **Device Details**:\n" + "\n".join([f"• {info}" for info in device_info])
        elif goal_type == "house" and details:
            house_info = []
            if details.get("property_type"):
                house_info.append(f"🏠 Type: {details['property_type']}")
            if details.get("location"):
                house_info.append(f"📍 Location: {details['location']}")
            if house_info:
                details_summary = f"\n🏡 **Property Details**:\n" + "\n".join([f"• {info}" for info in house_info])
        elif goal_type == "wedding" and details:
            wedding_info = []
            if details.get("wedding_style"):
                wedding_info.append(f"💒 Style: {details['wedding_style']}")
            if details.get("guest_count"):
                wedding_info.append(f"👥 Guests: {details['guest_count']}")
            if wedding_info:
                details_summary = f"\n💍 **Wedding Details**:\n" + "\n".join([f"• {info}" for info in wedding_info])
        elif goal_type == "education" and details:
            education_info = []
            if details.get("education_type"):
                education_info.append(f"🎓 Type: {details['education_type']}")
            if details.get("field_of_study"):
                education_info.append(f"📚 Field: {details['field_of_study']}")
            if education_info:
                details_summary = f"\n📖 **Education Details**:\n" + "\n".join([f"• {info}" for info in education_info])
        
        # Celebratory and informative response
        celebration_messages = [
            "🎉 **Boom! Goal Created with Details!**",
            "✨ **Amazing! Your Detailed Goal is Live!**",
            "🚀 **Fantastic! Detailed Goal Successfully Set Up!**",
            "🏆 **Awesome! Your Specific Dream is Now a Plan!**"
        ]
        
        tips = [
            "💡 **Pro Tip**: Having specific details makes your goal more motivating!",
            "💪 **Remember**: The clearer your vision, the stronger your motivation!",
            "🌟 **You've got this!** Detailed goals are 10x more likely to be achieved!",
            "📈 **Smart move!** Specific goals create specific action plans!"
        ]
        
        celebration = random.choice(celebration_messages)
        tip = random.choice(tips)
        
        return f"{celebration}\n\n**Your '{goal_name}' Goal is Ready!** 🎯{details_summary}\n\n📊 **Goal Summary:**\n• **Target**: RM{amount:.2f}\n• **Target Date**: {target_date.strftime('%B %d, %Y')}\n• **Time Left**: {days_until} days ({months_until:.1f} months)\n\n💰 **Saving Suggestions:**\n• **Monthly**: RM{monthly_suggestion:.2f}\n• **Weekly**: RM{weekly_suggestion:.2f}\n\n{tip}\n\nReady to make your first contribution or create another goal? I'm here to help! 😊"
    else:
        return "Oops! I had a small hiccup creating your goal. 😅 Don't worry - let's try again! Just say **'set a goal'** and we'll get it sorted! 💪"

def process_user_input(input_text, user_email):
    """
    Process user input, handling expense entry, confirmation, and general queries.
    """
    # Debug info for tracing issues
    debug_info = []
    debug_info.append(f"Input: {input_text}")
    debug_info.append(f"Messages count: {len(st.session_state.messages) if 'messages' in st.session_state else 0}")
    debug_info.append(f"Has pending_expense: {'pending_expense' in st.session_state}")
    debug_info.append(f"Has budget_conversation: {'budget_conversation' in st.session_state}")
    
    # PRIORITY 1: Handle budget conversation first (highest priority)
    if "budget_conversation" in st.session_state:
        debug_info.append("Processing budget conversation")
        stage = st.session_state.budget_conversation["stage"]
        input_lower = input_text.lower()
        
        # Enhanced cancel detection
        cancel_words = ["cancel", "stop", "nevermind", "never mind", "forget it", "change mind", "quit", "exit", "abort", "back"]
        if any(word in input_lower for word in cancel_words):
            del st.session_state.budget_conversation
            st.session_state.debug_info = "\n".join(debug_info)
            return "No problem at all! 😊 Budget planning should never feel rushed.\n\nWhenever you're ready to set up a budget, just say **'set budget'** and I'll be here to help you through it step by step!\n\nIs there anything else I can help you with right now? 💭"
        
        # Handle different stages of budget conversation
        if stage == "ask_category":
            debug_info.append("Budget conversation: ask_category stage")
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
            
            category_encouragement = {
                "food": "Excellent choice! Food budgeting is one of the most impactful areas. 🍽️",
                "transport": "Smart pick! Transport costs can really sneak up on you. 🚗",
                "entertainment": "Great thinking! It's important to budget for the fun stuff too. 🎬",
                "shopping": "Good idea! Shopping budgets help prevent those impulse buys. 🛍️",
                "utilities": "Very practical! Bills are so predictable when budgeted properly. 💡",
                "housing": "Essential choice! Housing is typically the biggest expense. 🏠",
                "healthcare": "Wise decision! Healthcare costs can be unpredictable. ⚕️",
                "education": "Fantastic! Investing in knowledge always pays off. 📚",
                "other": "Smart to budget for miscellaneous expenses! 📦"
            }
            
            encouragement = category_encouragement.get(selected_category, "Great choice for budgeting! 💰")
            
            st.session_state.debug_info = "\n".join(debug_info)
            return f"**{selected_category.title()} Budget** - {encouragement}\n\nNow for the fun part! What's a realistic monthly amount you'd like to set aside for {selected_category.title()}?\n\nThink about your typical spending in this area and what feels manageable. You can always adjust it later!\n\nJust tell me the amount - like **'350'** for RM350. What sounds right to you? 🤔"
        
        elif stage == "ask_amount":
            debug_info.append("Budget conversation: ask_amount stage")
            
            # IMPORTANT: Extract amount from budget conversation context, not expense patterns
            amount_match = re.search(r"(\d+\.?\d*)", input_text)
            if amount_match:
                try:
                    amount = float(amount_match.group(1))
                    # Store the amount and move to confirmation stage
                    st.session_state.budget_conversation["amount"] = amount
                    st.session_state.budget_conversation["stage"] = "confirm"
                    
                    category = st.session_state.budget_conversation["category"]
                    
                    # Personalized responses based on amount ranges
                    if amount >= 1000:
                        amount_feedback = "That's a substantial budget! 💪 You're really committed to managing this area well."
                    elif amount >= 500:
                        amount_feedback = "That sounds like a well-thought-out amount! 👍 Very reasonable."
                    elif amount >= 200:
                        amount_feedback = "Great! That's a practical and manageable budget. 😊"
                    elif amount >= 50:
                        amount_feedback = "Smart to start conservative! 🎯 You can always increase it later."
                    else:
                        amount_feedback = "That's a tight budget! 💪 Great discipline - every ringgit counts!"
                    
                    st.session_state.debug_info = "\n".join(debug_info)
                    return f"**RM{amount:.2f} for {category.title()}** - {amount_feedback}\n\n📋 **Quick Summary:**\n• Category: **{category.title()}**\n• Monthly Budget: **RM{amount:.2f}**\n• This will help you track and control your {category.lower()} spending!\n\nShall I activate this budget for you? Say **'yes'** to confirm or **'no'** to make changes! 🚀"
                except ValueError:
                    st.session_state.debug_info = "\n".join(debug_info)
                    return "Oops! I'm having trouble reading that number! 😅\n\nCould you help me out by typing just the amount as a simple number?\n\n**Examples:**\n• Type **'250'** for RM250\n• Type **'99.50'** for RM99.50\n\nWhat amount would you like to budget? 💰"
            else:
                # Check for category change requests
                if any(word in input_lower for word in ["change", "different", "switch", "another", "other"]):
                    st.session_state.budget_conversation["stage"] = "ask_category"
                    st.session_state.debug_info = "\n".join(debug_info)
                    return "Sure thing! Let's pick a different category! 🔄\n\nWhich spending area would you prefer to budget for? You can choose from Food, Transport, Entertainment, Shopping, Utilities, Housing, Healthcare, Education, or Other!\n\nWhat sounds more interesting to you? 😊"
                else:
                    st.session_state.debug_info = "\n".join(debug_info)
                    return "I'm looking for the budget amount, but I can't quite find it in your message! 🔍\n\nCould you tell me how much you'd like to set aside for this category? Just the number is perfect!\n\n**For example:** Type **'400'** for RM400\n\nWhat's your ideal budget amount? 💡"
        
        elif stage == "confirm":
            debug_info.append("Budget conversation: confirm stage")
            
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
                    # Multiple celebration messages
                    celebration_intros = [
                        "🎉 **Woohoo! Budget Activated!**",
                        "✅ **Success! You're All Set!**", 
                        "🌟 **Fantastic! Budget is Live!**",
                        "🚀 **Amazing! Budget Locked In!**"
                    ]
                    
                    motivational_endings = [
                        "You're building incredible financial habits! 💪",
                        "This is going to make such a difference in your money management! 📊",
                        "Smart money moves like this add up to big wins! 🏆",
                        "I'm so proud of you for taking control of your finances! 🌟",
                        "You're on the path to financial success! 🎯"
                    ]
                    
                    intro = random.choice(celebration_intros)
                    ending = random.choice(motivational_endings)
                    
                    st.session_state.debug_info = "\n".join(debug_info)
                    return f"{intro}\n\nYour **{category.title()}** budget of **RM{amount:.2f}** is now active for {month} {year}!\n\n{ending}\n\nI'll keep track of your spending and let you know how you're doing. Want to set up more budgets? Just say **'set budget'** again! 😊"
                else:
                    st.session_state.debug_info = "\n".join(debug_info)
                    return "Oh dear! 😔 Something went wrong on my end while setting up your budget.\n\nThis is unusual - could you please try again? I really want to get this perfect for you! Sometimes technology has its hiccups, but we'll get through this together! 💪"
            
            elif input_text.lower() in ["no", "n", "cancel", "wait", "hold on", "not yet", "nope", "stop", "not really"]:
                # Clear the conversation state
                del st.session_state.budget_conversation
                st.session_state.debug_info = "\n".join(debug_info)
                return "Absolutely no problem! 😊 I totally understand wanting to get the numbers just right.\n\nBudgeting is personal, and it should feel comfortable for you. Take your time to think about what works best!\n\nWhen you're ready to try again, just say **'set budget'** and I'll be right here to help! Is there anything else I can assist you with? 💭"
            
            else:
                # Handle unclear confirmation responses
                if any(phrase in input_lower for phrase in ["change amount", "different amount", "wrong amount", "adjust amount", "modify amount"]):
                    st.session_state.budget_conversation["stage"] = "ask_amount"
                    st.session_state.debug_info = "\n".join(debug_info)
                    return f"Of course! Let's adjust the amount for your **{st.session_state.budget_conversation['category'].title()}** budget! 🔧\n\nWhat amount would you prefer instead? Just give me the new number! 💰"
                elif any(phrase in input_lower for phrase in ["change category", "different category", "wrong category", "switch category"]):
                    st.session_state.budget_conversation["stage"] = "ask_category"
                    st.session_state.debug_info = "\n".join(debug_info)
                    return "Sure thing! Let's switch to a different category! 🔄\n\nWhich spending area would you like to budget for instead? Choose from Food, Transport, Entertainment, Shopping, Utilities, Housing, Healthcare, Education, or Other! 😊"
                else:
                    st.session_state.debug_info = "\n".join(debug_info)
                    return "I want to make sure I understand you perfectly! 😊\n\n**Could you say:**\n• **'Yes'** to activate this budget\n• **'No'** if you'd like to make changes\n\nI'm here to get this exactly right for you! 🎯"

    # ENHANCED Goal Conversation Handling - COMPLETELY FIXED
    if "goal_conversation" in st.session_state:
        stage = st.session_state.goal_conversation.get("stage", "ask_goal_name")
        input_lower = input_text.lower()
        
        # Enhanced cancel detection
        cancel_words = ["cancel", "stop", "nevermind", "never mind", "forget it", "change mind", "quit", "exit", "abort"]
        if any(word in input_lower for word in cancel_words):
            del st.session_state.goal_conversation
            return "No worries at all! 😊 Setting goals should be exciting, not stressful!\n\nWhenever you're ready to turn a dream into a plan, just say **'set a goal'** and I'll be here to help make it happen! Take your time! 💭"
        
        if stage == "ask_goal_name":
            # Store goal name and ask for amount with encouragement
            goal_name = input_text.strip()
            st.session_state.goal_conversation["goal_name"] = goal_name
            st.session_state.goal_conversation["stage"] = "ask_amount"
            
            # Encouraging responses based on goal type
            encouragement_map = {
                "emergency": "Smart choice! Emergency funds are like financial superheroes - they're there when you need them most! 🦸‍♀️",
                "vacation": "How exciting! Vacations create memories that last a lifetime! 🏖️✈️",
                "car": "Great thinking! Reliable transportation opens up so many opportunities! 🚗",
                "house": "Amazing! Homeownership is such a rewarding milestone! 🏠",
                "wedding": "How wonderful! Your special day deserves to be everything you dreamed of! 💍",
                "education": "Fantastic! Investing in yourself is the best investment you can make! 🎓",
                "laptop": "Perfect! Good tech can really boost your productivity and creativity! 💻",
                "phone": "Nice! Staying connected with great tech is so important these days! 📱"
            }
            
            encouragement = "Perfect choice! I love helping people save for their dreams! 🌟"
            for keyword, message in encouragement_map.items():
                if keyword in goal_name.lower():
                    encouragement = message
                    break
            
            return f"**{goal_name}** - {encouragement}\n\nNow, how much do you want to save for this goal? Just tell me the target amount - for example:\n• **'5000'** for RM5,000\n• **'1200'** for RM1,200\n\nWhat's your target amount? 💰"
        
        elif stage == "ask_amount":
            # Extract amount and ask for date with helpful suggestions
            amount_match = re.search(r"(\d+\.?\d*)", input_text)
            if amount_match:
                try:
                    amount = float(amount_match.group(1))
                    st.session_state.goal_conversation["amount"] = amount
                    st.session_state.goal_conversation["stage"] = "ask_date"
                    
                    # Encouraging response based on amount
                    if amount >= 10000:
                        amount_encouragement = "Wow! That's a significant goal! I love your ambition! 🚀"
                    elif amount >= 5000:
                        amount_encouragement = "That's a solid target! You're thinking big! 💪"
                    elif amount >= 1000:
                        amount_encouragement = "Great target amount! Very achievable with the right plan! 📈"
                    else:
                        amount_encouragement = "Perfect! Starting with achievable goals is super smart! 🎯"
                    
                    return f"Excellent! RM{amount:.2f} for {st.session_state.goal_conversation['goal_name']}! {amount_encouragement}\n\nWhen would you like to achieve this goal? You can tell me:\n\n⏰ **Timeframe Examples:**\n• 'In 6 months'\n• 'By next December'\n• 'In 1 year'\n• 'By summer 2025'\n• Or any specific date!\n\nWhen do you want to reach this goal? 📅"
                except ValueError:
                    return "Hmm, I'm having trouble reading that number! 😅 Could you help me out by just typing the amount?\n\n**For example:**\n• Type **'3000'** for RM3,000\n• Type **'599.99'** for RM599.99\n\nWhat's your target amount? 💰"
            else:
                return "I'm looking for your target amount! 🔍 How much do you want to save for this goal?\n\nJust tell me the number - like **'2500'** for RM2,500. What's your target? 💡"
        
        elif stage == "ask_date":
            # Process date with friendly parsing and create goal
            try:
                input_lower = input_text.lower()
                today = datetime.now()
                
                # Enhanced date parsing
                if "month" in input_lower:
                    months_match = re.search(r"(\d+)", input_lower)
                    if months_match:
                        months_num = int(months_match.group(1))
                        target_date = today + timedelta(days=months_num * 30)
                    else:
                        target_date = today + timedelta(days=180)  # Default 6 months
                elif "year" in input_lower:
                    if "next year" in input_lower:
                        target_date = today.replace(year=today.year + 1, month=12, day=31)
                    else:
                        years_match = re.search(r"(\d+)", input_lower)
                        if years_match:
                            years_num = int(years_match.group(1))
                            target_date = today + timedelta(days=years_num * 365)
                        else:
                            target_date = today + timedelta(days=365)
                elif "december" in input_lower or "dec" in input_lower:
                    year = today.year if today.month <= 12 else today.year + 1
                    target_date = datetime(year, 12, 31)
                elif "summer" in input_lower:
                    year = today.year + 1 if "2025" in input_lower else today.year
                    target_date = datetime(year, 6, 21)  # Summer solstice
                elif "january" in input_lower or "jan" in input_lower:
                    year = today.year + 1
                    target_date = datetime(year, 1, 31)
                else:
                    # Default to 1 year from now
                    target_date = today + timedelta(days=365)
                
                # Create the goal
                goal_name = st.session_state.goal_conversation["goal_name"]
                amount = st.session_state.goal_conversation["amount"]
                
                # Determine goal type based on name
                goal_type = "savings"  # default
                goal_name_lower = goal_name.lower()
                if any(word in goal_name_lower for word in ["emergency", "fund"]):
                    goal_type = "emergency_fund"
                elif any(word in goal_name_lower for word in ["vacation", "trip", "travel", "holiday"]):
                    goal_type = "vacation"
                elif any(word in goal_name_lower for word in ["car", "vehicle"]):
                    goal_type = "car"
                elif any(word in goal_name_lower for word in ["house", "home", "property"]):
                    goal_type = "house"
                elif any(word in goal_name_lower for word in ["laptop", "computer", "phone", "gadget", "tech"]):
                    goal_type = "electronics"
                elif any(word in goal_name_lower for word in ["education", "course", "school", "study"]):
                    goal_type = "education"
                elif any(word in goal_name_lower for word in ["wedding", "marriage"]):
                    goal_type = "wedding"
                elif any(word in goal_name_lower for word in ["debt", "loan", "payoff"]):
                    goal_type = "debt_payoff"
                
                target_date_str = target_date.strftime("%Y-%m-%d")
                
                success, goal_id = add_goal(user_email, goal_name, goal_type, amount, target_date_str, 0)
                
                # Clear conversation state
                del st.session_state.goal_conversation
                
                if success:
                    # Calculate helpful information
                    days_until = (target_date - today).days
                    months_until = max(1, days_until / 30.44)
                    monthly_suggestion = amount / months_until
                    weekly_suggestion = amount / (days_until / 7) if days_until > 0 else amount
                    
                    # Celebratory and informative response
                    celebration_messages = [
                        "🎉 **Boom! Goal Created!**",
                        "✨ **Amazing! Your Goal is Live!**",
                        "🚀 **Fantastic! Goal Successfully Set Up!**",
                        "🏆 **Awesome! Your Dream is Now a Plan!**"
                    ]
                    
                    tips = [
                        "💡 **Pro Tip**: Set up automatic transfers to make saving effortless!",
                        "💪 **Remember**: Small, consistent contributions add up to big results!",
                        "🌟 **You've got this!** Every RM you save brings you closer to your goal!",
                        "📈 **Smart move!** People with written goals are 42% more likely to achieve them!"
                    ]
                    
                    celebration = random.choice(celebration_messages)
                    tip = random.choice(tips)
                    
                    return f"{celebration}\n\n**Your '{goal_name}' Goal is Ready!** 🎯\n\n📊 **Goal Details:**\n• **Target**: RM{amount:.2f}\n• **Target Date**: {target_date.strftime('%B %d, %Y')}\n• **Time Left**: {days_until} days ({months_until:.1f} months)\n\n💰 **Saving Suggestions:**\n• **Monthly**: RM{monthly_suggestion:.2f}\n• **Weekly**: RM{weekly_suggestion:.2f}\n\n{tip}\n\nReady to make your first contribution or create another goal? I'm here to help! 😊"
                else:
                    return "Oops! I had a small hiccup creating your goal. 😅 Don't worry - let's try again! Just say **'set a goal'** and we'll get it sorted! 💪"
                    
            except Exception as e:
                del st.session_state.goal_conversation
                return "I had a little trouble understanding that date, but no worries! 😊 Let's try again - just say **'set a goal'** and I'll help you through it step by step! 🎯"
    
    # PRIORITY 2: Handle expense confirmation flow
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
            if input_lower in ["yes", "y", "yeah", "correct", "that's right", "right", "yep", "yup", "sure"]:
                debug_info.append("Detected YES response")
                # User confirmed the category - finalize the expense
                del st.session_state.pending_expense
                st.session_state.debug_info = "\n".join(debug_info)
                return "Great! Your expense has been recorded successfully. What else can I help you with today?"
            
            # Handle NO responses
            elif input_lower in ["no", "n", "nope"] or any(word in input_lower for word in ["change", "wrong", "incorrect"]):
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
    
    # PRIORITY 3: Handle expense correction stages
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
    
    # PRIORITY 4: Handle category/amount changes
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
    
    # PRIORITY 5: Check if input is an expense (only if not in budget conversation)
    debug_info.append("Checking for expense patterns")
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
    
    # PRIORITY 6: Handle intents (budget_set, budget_query, etc.)
    debug_info.append("Processing as regular intent")
    
    # Use improved intent classification
    intent_tag, confidence = debug_intent_classification(input_text)
    debug_info.append(f"Predicted intent: {intent_tag} with confidence: {confidence}")
    
    # Store debug info
    st.session_state.debug_info = "\n".join(debug_info)
    
    # Handle budget_set intent specifically
    if intent_tag == "budget_set":
        debug_info.append("Processing budget_set intent")
        
        # Extract category from the message if any
        category = None
        category_keywords = {
            "food": ["food", "groceries", "eating", "restaurant", "lunch", "dinner", "breakfast", "meals", "dining"],
            "transport": ["transport", "transportation", "gas", "fuel", "bus", "train", "taxi", "grab", "car", "travel"],
            "entertainment": ["entertainment", "movies", "games", "fun", "leisure", "cinema", "shows", "streaming"],
            "shopping": ["shopping", "clothes", "items", "purchases", "mall", "store", "clothing", "fashion"],
            "utilities": ["utilities", "bills", "electricity", "water", "internet", "phone", "wifi"],
            "housing": ["housing", "rent", "mortgage", "home", "apartment", "house"],
            "healthcare": ["healthcare", "medical", "health", "doctor", "hospital", "medicine"],
            "education": ["education", "school", "books", "courses", "tuition", "learning"],
            "other": ["other", "misc", "miscellaneous", "everything else"]
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
            
            category_tips = {
                "food": "Great choice! Food budgeting helps with meal planning and reduces food waste. 🍽️",
                "transport": "Smart thinking! Transport costs can really add up quickly. 🚗",
                "entertainment": "Excellent! It's important to budget for fun while staying responsible. 🎬",
                "shopping": "Good idea! Shopping budgets help prevent impulse purchases. 🛍️",
                "utilities": "Very practical! Utility budgets help with monthly planning. 💡",
                "housing": "Essential! Housing is usually the biggest expense category. 🏠",
                "healthcare": "Wise choice! Health expenses can be unpredictable. ⚕️",
                "education": "Fantastic! Investing in learning is always worthwhile. 📚",
                "other": "Good thinking! It's smart to budget for miscellaneous expenses. 📦"
            }
            
            tip = category_tips.get(category, "Excellent choice for budgeting! 💰")
            
            return f"**{category.title()} Budget Setup** 🎯\n\n{tip}\n\nNow, what's a realistic monthly amount you'd like to set aside for {category.title()}? Think about your typical spending in this area.\n\nJust tell me the amount - for example:\n• **'500'** for RM500\n• **'75.50'** for RM75.50\n\nWhat feels right to you? 💭"
        else:
            # No category found, ask for it
            st.session_state.budget_conversation = {"stage": "ask_category"}
            return "I'm so excited to help you set up a budget! 🎉 This is going to make such a difference in managing your money!\n\n**Which spending category would you like to start with?** Here are your options:\n\n🍽️ **Food** - groceries, restaurants, takeout\n🚗 **Transport** - gas, public transport, parking\n🎬 **Entertainment** - movies, games, subscriptions\n🛍️ **Shopping** - clothes, personal items\n💡 **Utilities** - electricity, water, internet, phone\n🏠 **Housing** - rent, mortgage payments\n⚕️ **Healthcare** - medical expenses, medicine\n📚 **Education** - books, courses, training\n📦 **Other** - miscellaneous expenses\n\nJust tell me which category you'd like to focus on first! I'll walk you through everything step by step. 😊"
    
    # Handle budget query requests with the fixed version from before
    elif intent_tag == "budget_query":
        input_lower = input_text.lower()
        
        # IMPROVED category detection with more precise matching
        specific_category = None
        
        # Check for specific category mentions with exact word boundaries
        if any(word in input_lower for word in ["food budget", "my food", "food spending"]):
            specific_category = "food"
        elif any(word in input_lower for word in ["transport budget", "my transport", "transport spending", "transportation budget"]):
            specific_category = "transport"
        elif any(word in input_lower for word in ["entertainment budget", "my entertainment", "entertainment spending"]):
            specific_category = "entertainment"
        elif any(word in input_lower for word in ["shopping budget", "my shopping", "shopping spending"]):
            specific_category = "shopping"
        elif any(word in input_lower for word in ["utilities budget", "my utilities", "utilities spending", "utility budget"]):
            specific_category = "utilities"
        elif any(word in input_lower for word in ["housing budget", "my housing", "housing spending", "rent budget", "mortgage budget"]):
            specific_category = "housing"
        elif any(word in input_lower for word in ["healthcare budget", "my healthcare", "healthcare spending", "health budget", "medical budget"]):
            specific_category = "healthcare"
        elif any(word in input_lower for word in ["education budget", "my education", "education spending", "school budget"]):
            specific_category = "education"
        elif any(word in input_lower for word in ["other budget", "my other", "other spending", "misc budget"]):
            specific_category = "other"
        
        # Check if user wants ALL budgets (improved detection)
        show_all_patterns = [
            "show my budget", "show all budget", "show my all budget", 
            "what is my budget", "what's my budget", "my budget",
            "check my budget", "view my budget", "budget overview",
            "budget status", "how's my budget", "all my budgets"
        ]
        
        show_all = any(pattern in input_lower for pattern in show_all_patterns)
        
        # If we found a specific category mention AND it's not a "show all" request
        if specific_category and not show_all:
            # Make sure it's really asking about that specific category
            category_specific_phrases = [
                f"{specific_category} budget", f"my {specific_category}", 
                f"{specific_category} spending", f"how my {specific_category}"
            ]
            
            # Double-check that the input is actually asking about this specific category
            if not any(phrase in input_lower for phrase in category_specific_phrases):
                specific_category = None
                show_all = True
        
        # Get current month and year
        current_month = datetime.now().strftime("%B")
        current_year = datetime.now().year
        
        # Get budgets and spending data
        budgets = get_budgets(user_email, current_month, current_year)
        spending = get_spending_by_category(user_email, current_month, current_year)
        
        if not budgets:
            return f"Hey there! 😊 I don't see any budgets set up yet, but that's totally fine - everyone starts somewhere!\n\n🚀 **Ready to create your first budget?** It's one of the smartest financial moves you can make!\n\nI can help you set up budgets for:\n• Food & Dining 🍽️\n• Transportation 🚗\n• Entertainment 🎬\n• Shopping 🛍️\n• Utilities 💡\n• Housing 🏠\n• Healthcare ⚕️\n• Education 📚\n• Other expenses 📦\n\nJust say something like **'set a budget for food'** and I'll walk you through it step by step! Want to give it a try? 💪"
        
        budget_text = ""
        
        if specific_category and not show_all:
            # Show specific category budget
            found_budget = False
            for budget in budgets:
                if budget["category"] == specific_category:
                    budget_amount = budget["amount"]
                    spent = spending.get(specific_category, 0)
                    remaining = budget_amount - spent
                    percent_used = (spent / budget_amount) * 100 if budget_amount > 0 else 0
                    
                    # Super personalized status messages
                    if percent_used < 50:
                        status = "🟢 Excellent!"
                        status_msg = "You're doing fantastic! You've only used {:.1f}% of your budget. Keep up the great work! 🌟".format(percent_used)
                    elif percent_used < 80:
                        status = "🟢 Going Strong!"
                        status_msg = "You're doing really well! {:.1f}% used - you're on a great track! 👍".format(percent_used)
                    elif percent_used < 95:
                        status = "🟠 Getting Close"
                        status_msg = "Heads up! You're at {:.1f}% of your budget. Maybe watch the spending a bit? 👀".format(percent_used)
                    elif percent_used < 100:
                        status = "🟠 Almost There"
                        status_msg = "You're at {:.1f}% - almost at your limit! Just RM{:.2f} left to stay on budget. 🎯".format(percent_used, remaining)
                    else:
                        over_amount = spent - budget_amount
                        status = "🔴 Over Budget"
                        status_msg = "You're RM{:.2f} over your budget, but don't worry! This happens to everyone. Want help adjusting your budget or finding ways to cut back? 💪".format(over_amount)
                    
                    budget_text = f"**Your {specific_category.title()} Budget for {current_month} {current_year}** 📊\n\n"
                    budget_text += f"💰 **Budget Set**: RM{budget_amount:.2f}\n"
                    budget_text += f"💸 **Spent So Far**: RM{spent:.2f}\n"
                    budget_text += f"🏦 **Remaining**: RM{remaining:.2f}\n"
                    budget_text += f"📈 **Percentage Used**: {percent_used:.1f}%\n"
                    budget_text += f"🎯 **Status**: {status}\n\n"
                    budget_text += f"💬 **My Take**: {status_msg}\n\n"
                    
                    if percent_used < 100:
                        budget_text += f"🎉 **You're doing great!** Want to check other budgets or set up new ones?"
                    else:
                        budget_text += f"💡 **Tip**: Consider adjusting your budget or looking for ways to save in this category!"
                    
                    found_budget = True
                    break
            
            if not found_budget:
                budget_text = f"🤔 **Hmm!** I don't see a budget set up for **{specific_category.title()}** yet!\n\nWould you like me to help you create one? It's super easy - just say **'set a budget for {specific_category}'** and I'll walk you through it!\n\nSetting up budgets for all your spending categories is one of the best ways to stay on top of your finances! 💪"
        else:
            # Show all budgets - (same as before, but ensuring it shows ALL budgets)
            budget_text = f"**Your Complete Budget Overview for {current_month} {current_year}** 📊✨\n\n"
            total_budget = 0
            total_spent = 0
            good_count = 0
            over_count = 0
            
            for budget in budgets:
                category_name = budget["category"]
                budget_amount = budget["amount"]
                spent = spending.get(category_name, 0)
                remaining = budget_amount - spent
                percent_used = (spent / budget_amount) * 100 if budget_amount > 0 else 0
                
                if percent_used < 80:
                    status = "🟢"
                    good_count += 1
                elif percent_used < 100:
                    status = "🟠"
                else:
                    status = "🔴"
                    over_count += 1
                
                budget_text += f"**{category_name.title()}** {status}\n"
                budget_text += f"├ Budget: RM{budget_amount:.2f} | Spent: RM{spent:.2f} | Left: RM{remaining:.2f}\n"
                budget_text += f"└ {percent_used:.1f}% used\n\n"
                
                total_budget += budget_amount
                total_spent += spent
            
            # Enhanced overall summary with personality
            total_remaining = total_budget - total_spent
            total_percent = (total_spent / total_budget) * 100 if total_budget > 0 else 0
            
            budget_text += f"📋 **Overall Summary:**\n"
            budget_text += f"• Total Budget: RM{total_budget:.2f}\n"
            budget_text += f"• Total Spent: RM{total_spent:.2f} ({total_percent:.1f}%)\n"
            budget_text += f"• Total Remaining: RM{total_remaining:.2f}\n\n"
            
            # Personalized overall assessment
            if total_percent < 60:
                overall_msg = "🌟 **Outstanding!** You're absolutely crushing your budget goals! You've only used {:.1f}% of your total budget. This level of discipline is incredible! 🏆".format(total_percent)
            elif total_percent < 80:
                overall_msg = "👍 **Excellent work!** You're doing really well with {:.1f}% of your budget used. Keep up this fantastic pace! 💪".format(total_percent)
            elif total_percent < 95:
                overall_msg = "😊 **Good progress!** You're at {:.1f}% of your total budget. You're managing your money well! 📈".format(total_percent)
            elif total_percent < 100:
                overall_msg = "⚠️ **Almost there!** You're at {:.1f}% - just RM{:.2f} left to stay within budget. You've got this! 🎯".format(total_percent, total_remaining)
            else:
                over_amount = total_spent - total_budget
                overall_msg = "💪 **Over budget by RM{:.2f}** - but hey, this happens! Don't be hard on yourself. Want to discuss adjusting your budgets or finding savings opportunities? I'm here to help! 🤝".format(over_amount)
            
            budget_text += f"💬 **My Assessment**: {overall_msg}\n\n"
            
            # Action suggestions
            if good_count == len(budgets):
                budget_text += f"🎉 You're doing amazing across all categories! Maybe consider setting up budgets for other areas?"
            elif over_count > 0:
                budget_text += f"💡 **Suggestion**: Focus on the categories marked 🔴 - I can help you find ways to save or adjust those budgets!"
            else:
                budget_text += f"🚀 **Keep it up!** You're managing your money like a pro!"
            
            budget_text += f"\n\nNeed help with any specific budget or want to add new ones? Just let me know! 😊"
        
        return budget_text
    
        # Handle goal_query intent - ENHANCED VERSION
    elif intent_tag == "goal_query":
        goals_summary = get_goals_summary(user_email)
        return goals_summary
    
    # Handle goal_set intent - ENHANCED VERSION
    elif intent_tag == "goal_set":
        # Check if they mentioned a specific goal type in their message
        input_lower = input_text.lower()
        goal_suggestions = {
            "emergency": "emergency fund",
            "vacation": "vacation fund", 
            "car": "new car",
            "house": "house down payment",
            "laptop": "new laptop",
            "phone": "new phone",
            "wedding": "wedding fund",
            "education": "education fund"
        }
        
        suggested_goal = None
        for keyword, suggestion in goal_suggestions.items():
            if keyword in input_lower:
                suggested_goal = suggestion
                break
        
        if suggested_goal:
            # Start with the detected goal
            st.session_state.goal_conversation = {
                "stage": "ask_amount",
                "goal_name": suggested_goal
            }
            
            encouragement_map = {
                "emergency fund": "Brilliant! Emergency funds are like financial peace of mind in the bank! 🛡️",
                "vacation fund": "How exciting! Life is meant to be explored and enjoyed! 🏖️",
                "new car": "Smart thinking! Reliable transportation opens up so many opportunities! 🚗",
                "house down payment": "Incredible! Homeownership is such an amazing milestone! 🏠",
                "new laptop": "Great choice! Investing in good tech can really boost your possibilities! 💻",
                "new phone": "Nice! Staying connected with great technology is so important! 📱",
                "wedding fund": "How wonderful! Your special day deserves to be magical! 💍",
                "education fund": "Fantastic! The best investment is always in yourself! 🎓"
            }
            
            encouragement = encouragement_map.get(suggested_goal, "Perfect choice! I love helping people achieve their dreams! 🌟")
            
            return f"**{suggested_goal.title()}** - {encouragement}\n\nHow much do you want to save for this goal? Just tell me the target amount - for example:\n• **'5000'** for RM5,000\n• **'1500'** for RM1,500\n\nWhat's your target amount? 💰"
        else:
            # Start goal creation conversation
            st.session_state.goal_conversation = {"stage": "ask_goal_name"}
            return "I absolutely love helping people turn dreams into achievable plans! 🎯✨\n\n**What would you like to save for?** Here are some popular goals I help people with:\n\n💰 **Emergency Fund** - peace of mind money\n🏖️ **Vacation** - create amazing memories\n🚗 **New Car** - reliable transportation\n🏠 **House Down Payment** - your future home\n💻 **Electronics** - that tech you've been wanting\n🎓 **Education** - invest in yourself\n💍 **Wedding** - your special day\n💳 **Debt Payoff** - financial freedom\n\nJust tell me what you're dreaming of! What goal speaks to your heart? 😊"
    
    # Handle goal_contribution intent - ENHANCED VERSION  
    elif intent_tag == "goal_contribution":
        goals = get_user_goals(user_email)
        if not goals:
            return "Hey there! 😊 I don't see any goals set up yet, but that's totally fine!\n\n🎯 **Ready to create your first goal?** It's one of the most powerful ways to turn dreams into reality!\n\nJust say **'set a goal'** and I'll help you set up something amazing! What do you say? ✨"
        
        # Check if they mentioned a specific amount and goal in their message
        input_lower = input_text.lower()
        amount_match = re.search(r"(\d+\.?\d*)", input_text)
        
        if amount_match:
            amount = float(amount_match.group(1))
            
            # Try to find which goal they're referring to
            found_goal = None
            for goal in goals:
                goal_name_words = goal["goal_name"].lower().split()
                if any(word in input_lower for word in goal_name_words):
                    found_goal = goal
                    break
            
            if found_goal:
                # Add the contribution
                success = add_goal_contribution(found_goal["id"], user_email, amount, f"Added via chat on {datetime.now().strftime('%Y-%m-%d')}")
                
                if success:
                    # Get updated progress
                    found_goal["current_amount"] += amount  # Update for immediate feedback
                    progress = get_goal_progress(found_goal)
                    
                    celebration_messages = [
                        "🎉 **Awesome!** You just made progress!",
                        "💪 **Yes!** Another step closer to your goal!",
                        "🌟 **Amazing!** You're building momentum!",
                        "🚀 **Fantastic!** Your future self will thank you!"
                    ]
                    
                    celebration = random.choice(celebration_messages)
                    
                    return f"{celebration}\n\n**RM{amount:.2f} added to '{found_goal['goal_name']}'!**\n\n📈 **Updated Progress:**\n• **Current**: RM{found_goal['current_amount']:.2f} of RM{found_goal['target_amount']:.2f}\n• **Progress**: {progress['progress_percent']:.1f}% complete\n• **Remaining**: RM{progress['remaining_amount']:.2f}\n• **Status**: {progress['status']}\n\n{progress['status_msg']} Keep up the great work! 💫"
                else:
                    return "Oops! I had a small issue adding that contribution. 😅 Could you try again? I want to make sure your progress gets recorded! 💪"
            else:
                # Show available goals for contribution
                goal_list = "\n".join([f"• **{goal['goal_name']}** (RM{goal['current_amount']:.2f} of RM{goal['target_amount']:.2f})" for goal in goals])
                return f"Great! I see you want to add RM{amount:.2f} to a goal! 💰\n\n**Which goal should I add it to?**\n\n{goal_list}\n\nJust tell me which one - for example: 'Add it to my vacation fund' 🎯"
        else:
            # Show available goals
            goal_list = "\n".join([f"• **{goal['goal_name']}** (RM{goal['current_amount']:.2f} of RM{goal['target_amount']:.2f})" for goal in goals])
            return f"I love seeing people make progress on their goals! 💪 This is how dreams become reality!\n\n**Your Current Goals:**\n\n{goal_list}\n\nWhich goal would you like to add money to, and how much? For example:\n• 'Add RM200 to my vacation fund'\n• 'Put RM100 towards emergency fund'\n\nWhat would you like to do? 🎯"
    
    # Get response based on intent for all other intents
    try:
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
    page = st.sidebar.selectbox("Choose a page", ["Home", "Spending Analysis", "Budget Tracking", "Goals", "About"])
    
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