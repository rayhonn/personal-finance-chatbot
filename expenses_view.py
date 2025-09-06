"""
Expense viewing functions for the personal finance chatbot.
These functions provide flexible options for viewing expenses:
- By specific month
- By specific week
- By specific day
"""

import sqlite3
from datetime import datetime, timedelta
import re

# Function to extract month from user input
def parse_month_from_input(input_text):
    """
    Extract month name or number from user input
    Returns tuple of (month_name, month_num, year)
    """
    input_lower = input_text.lower()
    
    # List of month names and their corresponding numbers
    months = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12
    }
    
    # Default to current month and year
    current_date = datetime.now()
    month_num = current_date.month
    year = current_date.year
    month_name = current_date.strftime("%B")
    
    # Check for "last month" or "previous month"
    if "last month" in input_lower or "previous month" in input_lower:
        # Go back one month
        if month_num == 1:
            month_num = 12
            year -= 1
        else:
            month_num -= 1
        # Update month name
        month_date = datetime(year, month_num, 1)
        month_name = month_date.strftime("%B")
        return (month_name, month_num, year)
    
    # Check for specific month name
    for name, num in months.items():
        if name in input_lower:
            month_num = num
            month_name = datetime(year, month_num, 1).strftime("%B")
            break
    
    # Check for specific year
    year_match = re.search(r'20(\d{2})', input_lower)
    if year_match:
        year = int("20" + year_match.group(1))
    
    return (month_name, month_num, year)

# Function to extract month from user input
def parse_month_from_input(input_text):
    """
    Extract month name or number from user input
    Returns tuple of (month_name, month_num, year)
    """
    input_lower = input_text.lower()
    
    # List of month names and their corresponding numbers
    months = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12
    }
    
    # Default to current month and year
    current_date = datetime.now()
    month_num = current_date.month
    year = current_date.year
    month_name = current_date.strftime("%B")
    
    # Check for "last month" or "previous month"
    if "last month" in input_lower or "previous month" in input_lower:
        # Go back one month
        if month_num == 1:
            month_num = 12
            year -= 1
        else:
            month_num -= 1
        # Update month name
        month_date = datetime(year, month_num, 1)
        month_name = month_date.strftime("%B")
        return (month_name, month_num, year)
    
    # Check for specific month name
    for name, num in months.items():
        if name in input_lower:
            month_num = num
            month_name = datetime(year, month_num, 1).strftime("%B")
            break
    
    # Check for specific year
    year_match = re.search(r'20(\d{2})', input_lower)
    if year_match:
        year = int("20" + year_match.group(1))
    
    return (month_name, month_num, year)

# Function to parse week reference from input
def parse_week_from_input(input_text):
    """
    Extract week reference from user input
    Returns tuple of (start_date, end_date, description)
    """
    input_lower = input_text.lower()
    today = datetime.now()
    
    # This week (default)
    if "this week" in input_lower or "current week" in input_lower:
        # Find the start of this week (Monday)
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        return (start_date, end_date, "This Week")
    
    # Last week
    elif "last week" in input_lower or "previous week" in input_lower:
        # Go back to last week's Monday
        start_date = today - timedelta(days=today.weekday() + 7)
        end_date = start_date + timedelta(days=6)
        return (start_date, end_date, "Last Week")
    
    # Last X weeks
    last_weeks_match = re.search(r'last (\d+) weeks?', input_lower)
    if last_weeks_match:
        num_weeks = int(last_weeks_match.group(1))
        if num_weeks > 10:  # Limit to reasonable number
            num_weeks = 10
        start_date = today - timedelta(days=num_weeks * 7)
        return (start_date, today, f"Last {num_weeks} Weeks")
    
    # Default to current week
    start_date = today - timedelta(days=today.weekday())
    end_date = start_date + timedelta(days=6)
    return (start_date, end_date, "This Week")

# Function to parse day reference from input
def parse_day_from_input(input_text):
    """
    Extract day reference from user input
    Returns tuple of (date, description)
    """
    input_lower = input_text.lower()
    today = datetime.now()
    
    # Today (default)
    if "today" in input_lower:
        return (today, "Today")
    
    # Yesterday
    elif "yesterday" in input_lower:
        yesterday = today - timedelta(days=1)
        return (yesterday, "Yesterday")
    
    # Specific days ago
    days_ago_match = re.search(r'(\d+) days? ago', input_lower)
    if days_ago_match:
        days = int(days_ago_match.group(1))
        if days > 30:  # Limit to reasonable number
            days = 30
        date = today - timedelta(days=days)
        return (date, f"{days} Days Ago")
    
    # Specific day of the week with clarifiers
    days_of_week = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6
    }
    
    # Check for "this [day]" pattern
    this_day_match = re.search(r'this (mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)', input_lower)
    if this_day_match:
        day_name = this_day_match.group(1)
        for key, day_index in days_of_week.items():
            if day_name in key or key in day_name:  # Flexible matching
                # Get the start of the current week (Monday)
                start_of_week = today - timedelta(days=today.weekday())
                # Calculate the date for the requested day in this week
                date = start_of_week + timedelta(days=day_index)
                return (date, f"This {key.title()}")
    
    # Check for "last [day]" or "previous [day]" pattern
    last_day_match = re.search(r'(last|previous) (mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)', input_lower)
    if last_day_match:
        day_name = last_day_match.group(2)
        for key, day_index in days_of_week.items():
            if day_name in key or key in day_name:  # Flexible matching
                # Get the start of the previous week (last Monday)
                start_of_last_week = today - timedelta(days=today.weekday() + 7)
                # Calculate the date for the requested day in the previous week
                date = start_of_last_week + timedelta(days=day_index)
                return (date, f"Last {key.title()}")
    
    # If just a day name without this/last qualifier, default to last occurrence
    for day_name, day_index in days_of_week.items():
        if day_name in input_lower:
            # Determine if the day is in the current week or already passed
            current_weekday = today.weekday()
            
            # Get the start of the current week (Monday)
            start_of_week = today - timedelta(days=current_weekday)
            
            # Calculate date for the requested day in this week
            this_week_date = start_of_week + timedelta(days=day_index)
            
            # If the day has already passed this week, return "Last [day]"
            # Otherwise return "This [day]"
            if this_week_date <= today:
                return (this_week_date, f"This {day_name.title()}")
            else:
                # Get the day from previous week
                last_week_date = this_week_date - timedelta(days=7)
                return (last_week_date, f"Last {day_name.title()}")
    
    # Default to today
    return (today, "Today")

# Function to show expenses for a specific month
def show_specific_month_expenses(user_email, input_text, DB_PATH):
    """
    Show expenses for a specific month with proper formatting
    """
    # Parse month from input
    month_name, month_num, year = parse_month_from_input(input_text)
    
    # Get month start and end dates
    month_start = datetime(year, month_num, 1).strftime("%Y-%m-%d")
    
    # Calculate end date (start of next month)
    if month_num == 12:
        next_month = datetime(year + 1, 1, 1).strftime("%Y-%m-%d")
    else:
        next_month = datetime(year, month_num + 1, 1).strftime("%Y-%m-%d")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get month's expenses
        c.execute("""
            SELECT amount, description, category, date
            FROM expenses 
            WHERE user_email = ? AND date >= ? AND date < ?
            ORDER BY date DESC, id DESC
        """, (user_email, month_start, next_month))
        
        monthly_expenses = c.fetchall()
        conn.close()
        
    except Exception as e:
        return f"❌ **Error retrieving {month_name} {year} expenses:** {str(e)}"
    
    response = f"📅 **{month_name} {year} Expenses**\n\n"
    
    if not monthly_expenses:
        response += f"No expenses recorded for {month_name} {year}! 💸\n\n"
        response += "Try viewing a different month or start tracking your expenses! 😊\n\n"
        response += "**👆 Viewing Options:**\n"
        response += "\n• 'Show **[month e.g. aug, september]** expenses' - View specific month\n\n"
        response += "• 'Show **[week e.g. this week, last week]** expenses' - View weekly expenses\n\n"
        response += "• 'Show **[day e.g. today, yesterday, mon-sun]** expenses' - View specific day spending\n\n"
        response += "  Note: Please use 'this' or 'last' with days of week (mon-sun) for clarity\n"
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
    response += "💰 **Category Breakdown:**\n\n"
    for category, total in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        percentage = (total / monthly_total) * 100
        response += f"• {category.title()}: RM{total:.2f} ({percentage:.1f}%)\n\n"
    
    # Show daily totals in chronological order
    response += "📅 **Daily Spending (Chronological):**\n\n"
    # Sort by date (chronologically)
    sorted_days = sorted(daily_totals.items())
    for date, total in sorted_days:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%a, %b %d")
            response += f"• {formatted_date}: RM{total:.2f}\n\n"
        except:
            response += f"• {date}: RM{total:.2f}\n\n"
    
    # Add a section to show top spending days too
    response += "💸 **Top Spending Days:**\n\n"
    # Sort by amount (highest to lowest)
    top_days = sorted(daily_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    for date, total in top_days:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%a, %b %d")
            response += f"• {formatted_date}: RM{total:.2f}\n\n"
        except:
            response += f"• {date}: RM{total:.2f}\n\n"
    
    response += "\n"
    response += "**👆 Viewing Options:**\n"
    response += "\n• 'Show **[month e.g. aug, september]** expenses' - View specific month\n\n"
    response += "• 'Show **[week e.g. this week, last week]** expenses' - View weekly expenses\n\n"
    response += "• 'Show **[day e.g. today, yesterday, mon-sun]** expenses' - View specific day spending\n\n"
    response += "  Note: Please use 'this' or 'last' with days of week (mon-sun) for clarity"
    
    return response

# Function to show expenses for a specific week
def show_specific_week_expenses(user_email, input_text, DB_PATH):
    """
    Show expenses for a specific week with proper formatting
    """
    # Parse week from input
    start_date, end_date, week_description = parse_week_from_input(input_text)
    
    # Format dates for database query
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get week's expenses
        c.execute("""
            SELECT amount, description, category, date
            FROM expenses 
            WHERE user_email = ? AND date >= ? AND date <= ?
            ORDER BY date DESC, id DESC
        """, (user_email, start_date_str, end_date_str))
        
        weekly_expenses = c.fetchall()
        conn.close()
        
    except Exception as e:
        return f"❌ **Error retrieving {week_description} expenses:** {str(e)}"
    
    # Date range for display
    date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    response = f"📅 **{week_description} ({date_range})**\n\n"
    
    if not weekly_expenses:
        response += f"No expenses recorded for {week_description}! 💸\n\n"
        response += "Try viewing a different time period or start tracking your expenses! 😊\n\n"
        response += "**👆 Viewing Options:**\n"
        response += "\n• 'Show **[month e.g. aug, september]** expenses' - View specific month\n\n"
        response += "• 'Show **[week e.g. this week, last week]** expenses' - View weekly expenses\n\n"
        response += "• 'Show **[day e.g. today, yesterday, mon-sun]** expenses' - View specific day spending\n\n"
        response += "  Note: Please use 'this' or 'last' with days of week (mon-sun) for clarity\n"
        return response
    
    # Calculate weekly total
    weekly_total = sum(float(exp[0]) for exp in weekly_expenses)
    response += f"**Week Total: RM{weekly_total:.2f}**\n\n"
    
    # Group by category and day
    category_totals = {}
    daily_totals = {}
    
    for expense in weekly_expenses:
        amount = float(expense[0])
        description = expense[1]
        category = expense[2]
        date = expense[3]
        
        # Category totals
        if category not in category_totals:
            category_totals[category] = 0
        category_totals[category] += amount
        
        # Daily totals
        if date not in daily_totals:
            daily_totals[date] = {
                "total": 0,
                "expenses": []
            }
        daily_totals[date]["total"] += amount
        daily_totals[date]["expenses"].append({
            "amount": amount,
            "description": description,
            "category": category
        })
    
    # Show daily breakdown (all days in the week)
    response += "📊 **Daily Breakdown:**\n\n"
    
    # Sort dates in chronological order
    sorted_dates = sorted(daily_totals.items(), key=lambda x: x[0])
    
    for date, data in sorted_dates:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%a, %b %d")
            response += f"**{formatted_date}:** RM{data['total']:.2f}\n\n"
            
            # List top 3 expenses for each day with line breaks
            top_expenses = sorted(data["expenses"], key=lambda x: x["amount"], reverse=True)[:3]
            for exp in top_expenses:
                response += f"  • RM{exp['amount']:.2f} for **{exp['description']}** ({exp['category'].title()})\n\n"
            
            response += "\n"
        except:
            continue
    
    response += "**👆 Viewing Options:**\n"
    response += "\n• 'Show **[month e.g. aug, september]** expenses' - View specific month\n\n"
    response += "• 'Show **[week e.g. this week, last week]** expenses' - View weekly expenses\n\n"
    response += "• 'Show **[day e.g. today, yesterday, mon-sun]** expenses' - View specific day spending\n\n"
    response += "  Note: Please use 'this' or 'last' with days of week (mon-sun) for clarity"
    
    return response

# Function to show expenses for a specific day
def show_specific_day_expenses(user_email, input_text, DB_PATH):
    """
    Show expenses for a specific day with proper formatting
    """
    # Parse day from input
    date_obj, day_description = parse_day_from_input(input_text)
    
    # Format date for database query
    date_str = date_obj.strftime("%Y-%m-%d")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get day's expenses
        c.execute("""
            SELECT amount, description, category, date, id
            FROM expenses 
            WHERE user_email = ? AND date = ?
            ORDER BY id DESC
        """, (user_email, date_str))
        
        daily_expenses = c.fetchall()
        
        # Get week's context (last 7 days including selected day)
        week_start = (date_obj - timedelta(days=6)).strftime("%Y-%m-%d")
        week_end = date_str
        
        c.execute("""
            SELECT amount, date
            FROM expenses 
            WHERE user_email = ? AND date >= ? AND date <= ?
            ORDER BY date DESC
        """, (user_email, week_start, week_end))
        
        week_context = c.fetchall()
        conn.close()
        
    except Exception as e:
        return f"❌ **Error retrieving {day_description} expenses:** {str(e)}"
    
    # Format full date for display
    formatted_full_date = date_obj.strftime("%A, %B %d, %Y")
    response = f"📅 **{day_description} ({formatted_full_date})**\n\n"
    
    if not daily_expenses:
        response += f"No expenses recorded for {day_description}! 💸\n\n"
        response += "Try viewing a different day or start tracking your expenses! 😊\n\n"
        response += "**👆 Viewing Options:**\n"
        response += "\n• 'Show **[month e.g. aug, september]** expenses' - View specific month\n\n"
        response += "• 'Show **[week e.g. this week, last week]** expenses' - View weekly expenses\n\n"
        response += "• 'Show **[day e.g. today, yesterday, mon-sun]** expenses' - View specific day spending\n\n"
        response += "  Note: Please use 'this' or 'last' with days of week (mon-sun) for clarity\n"
        return response
    
    # Calculate daily total
    daily_total = sum(float(exp[0]) for exp in daily_expenses)
    response += f"**Daily Total: RM{daily_total:.2f}**\n\n"
    
    # Group by category
    category_totals = {}
    
    # List all expenses in detail with proper line breaks
    response += "💳 **Expenses:**\n\n"
    for expense in daily_expenses:
        amount = float(expense[0])
        description = expense[1]
        category = expense[2]
        
        # Add to category totals
        if category not in category_totals:
            category_totals[category] = 0
        category_totals[category] += amount
        
        # Format individual expense with line break
        response += f"• RM{amount:.2f} for **{description}** ({category.title()})\n\n"
    
    response += "\n\n"
    response += "**👆 Viewing Options:**\n"
    response += "\n• 'Show **[month e.g. aug, september]** expenses' - View specific month\n\n"
    response += "• 'Show **[week e.g. this week, last week]** expenses' - View weekly expenses\n\n"
    response += "• 'Show **[day e.g. today, yesterday, mon-sun]** expenses' - View specific day spending\n\n"
    response += "  Note: Please use 'this' or 'last' with days of week (mon-sun) for clarity\n"
    
    return response

# Function to detect expense viewing type from user input
def detect_expense_view_type(input_text):
    """
    Determine what type of expense view the user is requesting
    Returns: "day", "week", "month", "specific_date", or None
    """
    input_lower = input_text.lower()
    
    # Check for specific date format (e.g., 5/9, 05/09, 5-9, etc.)
    date_patterns = [
        r'\d{1,2}/\d{1,2}',         # 5/9, 05/09
        r'\d{1,2}-\d{1,2}',          # 5-9, 05-09
        r'\d{1,2} (?:of )?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', # 5 of Jan, 5 Feb
    ]
    
    for pattern in date_patterns:
        if re.search(pattern, input_lower):
            return "specific_date"
    
    # Keywords for day view
    day_keywords = ["today", "yesterday", "day", "daily", "days ago", "monday", "tuesday", 
                    "wednesday", "thursday", "friday", "saturday", "sunday", "mon", "tue", 
                    "wed", "thu", "fri", "sat", "sun"]
    
    # Keywords for week view  
    week_keywords = ["week", "weekly", "last week", "this week", "current week", "past week", "weeks"]
    
    # Keywords for month view
    month_keywords = ["month", "monthly", "january", "february", "march", "april", "may", "june",
                     "july", "august", "september", "october", "november", "december",
                     "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"]
    
    # Check for month view
    for keyword in month_keywords:
        if keyword in input_lower:
            return "month"
        
    # Check for day view
    for keyword in day_keywords:
        if keyword in input_lower:
            return "day"
    
    # Check for week view
    for keyword in week_keywords:
        if keyword in input_lower:
            return "week"
    
    # If "show expenses" but no time specification, default to month view
    if "show expenses" in input_lower or "view expenses" in input_lower:
        return "month"
    
    return None
