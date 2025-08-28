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

# Create folders to store data
DATA_DIR = Path("finance_data")  # Create a folder path
DATA_DIR.mkdir(exist_ok=True)    # Make the folder if it doesn't exist
USER_DB_FILE = DATA_DIR / "users.json"  # This is where we'll store user info
DB_PATH = DATA_DIR / "finance.db"  # SQLite database for expenses

# Initialize user database if it doesn't exist
if not USER_DB_FILE.exists():
    with open(USER_DB_FILE, 'w') as f:
        json.dump({}, f, indent=4)

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

# Function to add expense with better error handling and return ID
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

# Function to format and save the intents file
def save_intents(intents_data):
    with open('intents.json', 'w') as f:
        json.dump(intents_data, f, indent=4)

# Load intents from the intents.json file
@st.cache_resource
def load_intents():
    try:
        with open('intents.json', 'r') as f:
            intents_data = json.load(f)
            
            # Check if we need to add the category_confirmation intent
            has_category_confirmation = False
            for intent in intents_data["intents"]:
                if intent["tag"] == "category_confirmation":
                    has_category_confirmation = True
                    break
            
            if not has_category_confirmation:
                intents_data["intents"].append({
                    "tag": "category_confirmation",
                    "patterns": [
                        "yes", "yeah", "correct", "that's right", "right", "y",
                        "no", "nope", "incorrect", "wrong", "n", "change category", "change it"
                    ],
                    "responses": [
                        "Great! Your expense has been recorded successfully.",
                        "Perfect! I've saved your expense with that category.",
                        "I've updated your expense with the new category. What would you like to do next?",
                        "Category has been updated. Is there anything else you'd like to do?"
                    ]
                })
                
                # Save the updated intents
                save_intents(intents_data)
            
            return intents_data
    except FileNotFoundError:
        # Create a default intents.json file if it doesn't exist
        default_intents = {
            "intents": [
                {
                    "tag": "fallback",
                    "patterns": [],
                    "responses": ["I'm your personal finance assistant. Type 'help' to see what I can do."]
                },
                {
                    "tag": "category_confirmation",
                    "patterns": [
                        "yes", "yeah", "correct", "that's right", "right", "y",
                        "no", "nope", "incorrect", "wrong", "n", "change category", "change it"
                    ],
                    "responses": [
                        "Great! Your expense has been recorded successfully.",
                        "Perfect! I've saved your expense with that category.",
                        "I've updated your expense with the new category. What would you like to do next?",
                        "Category has been updated. Is there anything else you'd like to do?"
                    ]
                }
            ]
        }
        save_intents(default_intents)
        return default_intents

# Load the intents
intents = load_intents()

# Function to convert a sentence into a bag of words - simplified for compatibility
def bag_of_words(sentence, words):
    # Tokenize the pattern
    sentence_words = clean_up_sentence(sentence)
    # Bag of words - vocabulary matrix
    bag = [0] * len(words)
    for w in sentence_words:
        for i, word in enumerate(words):
            if word == w:
                # Assign 1 if current word is in the vocabulary position
                bag[i] = 1
    return bag

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

# Function to extract entities from text
def extract_entities(text):
    text = text.lower()
    entities = {}
    
    # Expense patterns to extract amount and description
    expense_patterns = [
        r"spent (\$?[\d,.]+) on (.+)",
        r"spent (\$?[\d,.]+) for (.+)",
        r"i spent (\$?[\d,.]+) on (.+)",
        r"i spent (\$?[\d,.]+) for (.+)",
        r"i paid (\$?[\d,.]+) for (.+)",
        r"paid (\$?[\d,.]+) for (.+)",
        r"bought (.+) for (\$?[\d,.]+)",
        r"purchased (.+) for (\$?[\d,.]+)",
        r"(\$?[\d,.]+) for (.+)",
        r"cost me (\$?[\d,.]+) for (.+)",
        r"cost (\$?[\d,.]+) for (.+)"
    ]
    
    for pattern in expense_patterns:
        match = re.search(pattern, text)
        if match:
            # Extract amount and item from the match
            groups = match.groups()
            
            if "bought" in pattern or "purchased" in pattern:
                entities["description"] = groups[0].strip()
                entities["amount"] = groups[1].strip().replace('$', '').replace('RM', '')
            else:
                entities["amount"] = groups[0].strip().replace('$', '').replace('RM', '')
                entities["description"] = groups[1].strip()
            
            try:
                entities["amount"] = float(entities["amount"].replace(',', ''))
            except ValueError:
                pass
            
            break
    
    # If we found an amount and description, extract or determine category
    if "amount" in entities and "description" in entities:
        description = entities["description"]
        
        # Auto-categorize the expense
        category = categorize_expense(description)
        entities["category"] = category
    
    return entities

def categorize_expense(description):
    description = description.lower()
    
    categories = {
        "food": ["grocery", "groceries", "restaurant", "lunch", "dinner", "breakfast", "food", "meal", "coffee", 
                 "snack", "eat", "eating", "dining", "dine", "cafe", "cafeteria", "fastfood", "fast food", 
                 "takeout", "take-out", "takeaway", "take-away", "pizza", "burger", "sushi"],
        
        "transport": ["gas", "fuel", "bus", "train", "taxi", "grab", "uber", "lyft", "fare", "ticket", "transport",
                      "transportation", "commute", "travel", "subway", "mrt", "lrt", "petrol", "diesel", "car", 
                      "ride", "toll", "parking"],
        
        "entertainment": ["movie", "cinema", "ktv", "karaoke", "game", "concert", "show", "entertainment", "fun", 
                         "leisure", "theater", "theatre", "park", "ticket", "streaming", "subscription", "netflix", 
                         "spotify", "disney"],
        
        "shopping": ["clothes", "clothing", "shoes", "shirt", "dress", "pants", "fashion", "mall", "shop", 
                    "shopping", "boutique", "store", "retail", "buy", "purchase", "merchandise", "apparel", 
                    "accessories", "jewelry", "gift"],
        
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
    
    # If no match found, return "other"
    return "other"

# Function to format responses with actual data - improved formatting
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
    
    # Replace expense placeholder with actual expense data - improved formatting
    if "{expenses}" in response:
        expenses = get_expenses(user_email, limit=5)
        if expenses:
            expenses_text = ""
            for exp in expenses:
                # Format each expense on its own line with better spacing
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
                    "• Meal prep at home instead of eating out",
                    "• Use grocery store loyalty programs and coupons",
                    "• Make a shopping list and stick to it",
                    "• Buy non-perishable items in bulk when on sale"
                ],
                "transport": [
                    "• Consider carpooling or public transportation",
                    "• Combine errands to reduce trips",
                    "• Shop around for better car insurance rates",
                    "• Keep up with regular vehicle maintenance to avoid costly repairs"
                ],
                "entertainment": [
                    "• Look for free or low-cost events in your area",
                    "• Share streaming subscriptions with family or friends",
                    "• Check your library for free books, movies, and games",
                    "• Take advantage of discounts and happy hours"
                ],
                "shopping": [
                    "• Wait 24 hours before making non-essential purchases",
                    "• Shop during sales or with discount codes",
                    "• Consider buying second-hand for certain items",
                    "• Unsubscribe from retailer emails to avoid temptation"
                ]
            }
            
            # Generic tips for categories not in our predefined list
            generic_tips = [
                "• Create a specific budget for this category",
                "• Track every expense to identify unnecessary spending",
                "• Look for more affordable alternatives",
                "• Consider if each purchase is a need or a want"
            ]
            
            # Get tips for the highest spending category or use generic tips
            tips = category_tips.get(highest_category, generic_tips)
            tips_text = "\n".join(tips)
            
            response = response.replace("{tips}", tips_text)
        else:
            generic_tips = [
                "• Create a budget for each spending category",
                "• Track all your expenses to identify patterns",
                "• Prioritize needs over wants",
                "• Build an emergency fund for unexpected expenses"
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
    
    # Find the intent in the intents list
    for intent in intents["intents"]:
        if intent["tag"] == intent_tag:
            # Get a random response from the intent
            response = random.choice(intent["responses"])
            # Format the response with actual data
            return format_response(response, entities, user_email)
    
    # If no matching intent found, use fallback
    for intent in intents["intents"]:
        if intent["tag"] == "fallback":
            response = random.choice(intent["responses"])
            return format_response(response, entities, user_email)
    
    # Default response if no fallback is found
    return "I'm your personal finance assistant. You can ask me to record expenses, check your budget, or provide spending summaries. Type 'help' to see all the things I can do!"

# Function to process user input with yes/no handling for category confirmation
def process_user_input(input_text, user_email):
    # Check if this is a response to a category confirmation question
    if (st.session_state.messages and len(st.session_state.messages) >= 2):
        last_assistant_msg = st.session_state.messages[-1]["content"].lower()
        
        # Check if the last message was asking about category confirmation
        is_category_question = ("category" in last_assistant_msg and "?" in last_assistant_msg)
        
        if is_category_question:
            input_lower = input_text.lower().strip()
            
            # Handle affirmative responses
            if input_lower in ["yes", "y", "yeah", "correct", "right", "yep", "yup", "sure"]:
                # Clear the pending expense since it's confirmed
                if "pending_expense" in st.session_state:
                    del st.session_state.pending_expense
                return "Great! Your expense has been recorded successfully. What else can I help you with today?"
            
            # Handle negative responses
            elif input_lower in ["no", "n", "nope", "incorrect", "wrong", "change", "change category", "nah"]:
                # Check if we have a pending expense to update
                if "pending_expense" not in st.session_state:
                    return "I don't have an expense to update. Please tell me about a new expense."
                
                return "What category would you like to use instead? Choose from: Food, Transport, Entertainment, Shopping, Utilities, Housing, Healthcare, Education, or Other."
            
            # Check if user is providing a new category
            categories = ["food", "transport", "entertainment", "shopping", "utilities", 
                          "housing", "healthcare", "education", "other"]
            
            if input_lower in categories and "pending_expense" in st.session_state:
                # Update the category in the database
                expense = st.session_state.pending_expense
                try:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("UPDATE expenses SET category = ? WHERE id = ?", 
                             (input_lower, expense["id"]))
                    conn.commit()
                    conn.close()
                    
                    # Clear the pending expense
                    del st.session_state.pending_expense
                    
                    return f"I've updated the category to {input_lower}. Your expense has been recorded successfully."
                except Exception as e:
                    return f"Sorry, I couldn't update the category. Error: {str(e)}"
    
    # Continue with regular intent processing for non-confirmation inputs
    intent_tag, confidence = predict_intent(input_text, intents)
    
    # Extract entities from the input to check if it's an expense
    entities = extract_entities(input_text)
    
    # If it looks like an expense but the intent wasn't detected correctly
    if "amount" in entities and "description" in entities and intent_tag != "expense_add":
        intent_tag = "expense_add"  # Override the intent
    
    response = get_response(intent_tag, input_text, user_email)
    
    return response

# Initialize session state variables
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

# Add a header
st.title("Personal Finance Chatbot")

# Display current date and time - fixed to show correct date/time
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.write(f"Current date & time: {current_time}")

# Add a sidebar
st.sidebar.title("Navigation")

# Only show page selection if authenticated
if st.session_state.authenticated:
    page = st.sidebar.selectbox("Choose a page", ["Home", "Spending Analysis", "Budget Tracking", "About"])
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
elif page == "Home":
    # Get user name safely with a fallback
    user_info = load_users().get(st.session_state.current_user, {})
    user_name = user_info.get("name", "User")
    
    st.header(f"Welcome, {user_name}!")
    
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
    
    # Get user's expense data from database
    user_email = st.session_state.current_user
    current_month = datetime.now().strftime("%B")
    current_year = datetime.now().year
    
    # Get spending by category
    spending_data = get_spending_by_category(user_email)
    
    # Create tabs for different views
    analysis_tab1, analysis_tab2, analysis_tab3 = st.tabs(["Overview", "Categories", "Transactions"])
    
    with analysis_tab1:
        st.subheader("Monthly Spending Overview")
        
        if spending_data:
            # Calculate total spending
            total_spending = sum(spending_data.values())
            
            # Display total spending with a metric
            st.metric(
                label="Total Spending This Month", 
                value=f"RM{total_spending:.2f}"
            )
            
            # Create a bar chart for spending by category
            st.subheader("Spending by Category")
            
            # Sort categories by amount spent
            sorted_categories = sorted(spending_data.items(), key=lambda x: x[1], reverse=True)
            categories = [cat.title() for cat, _ in sorted_categories]
            amounts = [amt for _, amt in sorted_categories]
            
            # Create a DataFrame for the chart
            chart_data = pd.DataFrame({
                'Category': categories,
                'Amount': amounts
            })
            
            # Display the bar chart
            st.bar_chart(chart_data.set_index('Category'))
        else:
            st.info("No spending data available yet. Start recording your expenses to see visualizations.")
            
            # Display sample data for demonstration
            st.subheader("Sample Data (For Demonstration)")
            sample_data = {
                'Food': 250.0,
                'Transport': 150.0,
                'Entertainment': 100.0,
                'Shopping': 200.0,
                'Utilities': 120.0
            }
            
            # Create a bar chart with sample data
            sample_chart = pd.DataFrame({
                'Category': list(sample_data.keys()),
                'Amount': list(sample_data.values())
            })
            
            st.bar_chart(sample_chart.set_index('Category'))
            
            st.write("This is sample data. Your actual spending will be displayed here once you start recording expenses.")
    
    with analysis_tab2:
        st.subheader("Spending by Category")
        
        if spending_data:
            # Create a pie chart for category breakdown
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Calculate percentages for pie chart
            total = sum(spending_data.values())
            labels = [f"{cat.title()} (RM{amt:.2f})" for cat, amt in spending_data.items()]
            sizes = [amt for amt in spending_data.values()]
            
            # Create the pie chart
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
            ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
            
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
        else:
            st.info("No spending data available yet. Start recording expenses to see category breakdowns.")
    
    with analysis_tab3:
        st.subheader("Recent Transactions")
        
        # Get recent expenses
        expenses = get_expenses(user_email, limit=20)
        
        if expenses:
            # Create a DataFrame for display
            exp_df = pd.DataFrame(expenses)
            
            # Format the DataFrame for display
            formatted_df = pd.DataFrame({
                "Date": exp_df["date"],
                "Description": exp_df["description"],
                "Category": exp_df["category"].apply(lambda x: x.title()),
                "Amount": exp_df["amount"].apply(lambda x: f"RM{x:.2f}")
            })
            
            st.dataframe(formatted_df, use_container_width=True)
            
            # Add a download button for the data
            csv = exp_df.to_csv(index=False)
            st.download_button(
                label="Download Transactions CSV",
                data=csv,
                file_name=f"transactions_{current_month.lower()}_{current_year}.csv",
                mime="text/csv"
            )
        else:
            st.info("No transactions recorded yet. Start recording your expenses through the chatbot.")

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
