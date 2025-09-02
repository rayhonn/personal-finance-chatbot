"""
Enhanced Database Schema for Advanced Personal Finance Chatbot
Comprehensive database design supporting all advanced features
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_enhanced_database()
    
    def init_enhanced_database(self):
        """Initialize comprehensive database schema with all required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enhanced Users table with profile information
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users_enhanced (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                joined_date TEXT NOT NULL,
                last_login TEXT,
                profile_completion_score INTEGER DEFAULT 0,
                financial_health_score REAL DEFAULT 0.0,
                preferences TEXT DEFAULT '{}',
                security_settings TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Income Management System
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS income_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL,  -- salary, freelance, investment, business, other
                amount REAL NOT NULL,
                frequency TEXT NOT NULL,  -- monthly, weekly, bi-weekly, yearly, one-time
                start_date TEXT NOT NULL,
                end_date TEXT,
                is_active BOOLEAN DEFAULT 1,
                is_recurring BOOLEAN DEFAULT 1,
                tax_rate REAL DEFAULT 0.0,
                description TEXT,
                category TEXT DEFAULT 'primary',
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # Enhanced Expenses with AI categorization
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses_enhanced (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT,
                auto_categorized BOOLEAN DEFAULT 0,
                confidence_score REAL DEFAULT 0.0,
                date TEXT NOT NULL,
                location TEXT,
                payment_method TEXT,
                receipt_data TEXT,
                tags TEXT DEFAULT '[]',
                notes TEXT,
                is_recurring BOOLEAN DEFAULT 0,
                recurring_pattern TEXT,
                business_expense BOOLEAN DEFAULT 0,
                tax_deductible BOOLEAN DEFAULT 0,
                reviewed BOOLEAN DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # Advanced Budget Management
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budgets_enhanced (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT,
                amount REAL NOT NULL,
                period TEXT NOT NULL,  -- monthly, weekly, yearly
                budget_type TEXT DEFAULT 'standard',  -- standard, zero-based, envelope
                start_date TEXT NOT NULL,
                end_date TEXT,
                rollover_enabled BOOLEAN DEFAULT 0,
                rollover_limit REAL DEFAULT 0.0,
                alert_threshold REAL DEFAULT 80.0,
                is_active BOOLEAN DEFAULT 1,
                priority INTEGER DEFAULT 1,
                tags TEXT DEFAULT '[]',
                notes TEXT,
                template_id INTEGER,
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # SMART Goals Framework
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS goals_enhanced (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                goal_type TEXT NOT NULL,
                target_amount REAL NOT NULL,
                current_amount REAL DEFAULT 0.0,
                target_date TEXT NOT NULL,
                start_date TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                difficulty_level TEXT DEFAULT 'medium',
                feasibility_score REAL DEFAULT 0.0,
                completion_percentage REAL DEFAULT 0.0,
                is_achieved BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                milestone_count INTEGER DEFAULT 0,
                celebration_triggers TEXT DEFAULT '[]',
                risk_assessment TEXT DEFAULT '{}',
                dependencies TEXT DEFAULT '[]',
                smart_criteria TEXT DEFAULT '{}',
                auto_funding_rules TEXT DEFAULT '{}',
                tags TEXT DEFAULT '[]',
                notes TEXT,
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                achieved_at TEXT,
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # Goal Milestones and Progress Tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS goal_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                target_amount REAL NOT NULL,
                target_date TEXT NOT NULL,
                is_achieved BOOLEAN DEFAULT 0,
                achievement_date TEXT,
                celebration_message TEXT,
                reward TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (goal_id) REFERENCES goals_enhanced (id)
            )
        ''')
        
        # Enhanced Goal Contributions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS goal_contributions_enhanced (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                user_email TEXT NOT NULL,
                amount REAL NOT NULL,
                contribution_date TEXT NOT NULL,
                contribution_type TEXT DEFAULT 'manual',  -- manual, automatic, bonus
                source TEXT,
                note TEXT,
                milestone_achieved BOOLEAN DEFAULT 0,
                transaction_reference TEXT,
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (goal_id) REFERENCES goals_enhanced (id),
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # Financial Analytics and Insights
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS financial_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metric_date TEXT NOT NULL,
                metric_period TEXT NOT NULL,  -- daily, weekly, monthly, yearly
                category TEXT,
                subcategory TEXT,
                comparison_period TEXT,
                trend_direction TEXT,  -- up, down, stable
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # Smart Financial Rules and Automation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS financial_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                rule_type TEXT NOT NULL,  -- round_up, percentage_saving, bill_reminder, auto_categorize
                rule_criteria TEXT NOT NULL,  -- JSON with conditions
                rule_actions TEXT NOT NULL,  -- JSON with actions to take
                is_active BOOLEAN DEFAULT 1,
                last_executed TEXT,
                execution_count INTEGER DEFAULT 0,
                priority INTEGER DEFAULT 1,
                tags TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # Subscription and Bill Tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                service_name TEXT NOT NULL,
                amount REAL NOT NULL,
                billing_cycle TEXT NOT NULL,  -- monthly, yearly, weekly
                next_billing_date TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT DEFAULT 'active',  -- active, cancelled, paused
                auto_renew BOOLEAN DEFAULT 1,
                cancellation_difficulty TEXT DEFAULT 'easy',
                value_rating INTEGER DEFAULT 3,
                last_price_change REAL DEFAULT 0.0,
                reminder_days INTEGER DEFAULT 3,
                tags TEXT DEFAULT '[]',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # Chatbot Conversation History and Context
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                session_id TEXT NOT NULL,
                message_type TEXT NOT NULL,  -- user, assistant, system
                message_content TEXT NOT NULL,
                intent_detected TEXT,
                entities_extracted TEXT DEFAULT '{}',
                context_data TEXT DEFAULT '{}',
                confidence_score REAL DEFAULT 0.0,
                response_time REAL DEFAULT 0.0,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # Security and Audit Logging
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                action_type TEXT NOT NULL,
                action_description TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                session_id TEXT,
                table_affected TEXT,
                record_id TEXT,
                old_values TEXT,
                new_values TEXT,
                success BOOLEAN DEFAULT 1,
                error_message TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Financial Health Scoring History
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS health_score_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                overall_score REAL NOT NULL,
                income_score REAL DEFAULT 0.0,
                expense_score REAL DEFAULT 0.0,
                saving_score REAL DEFAULT 0.0,
                goal_score REAL DEFAULT 0.0,
                debt_score REAL DEFAULT 0.0,
                emergency_fund_score REAL DEFAULT 0.0,
                score_factors TEXT DEFAULT '{}',
                recommendations TEXT DEFAULT '[]',
                calculated_date TEXT NOT NULL,
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # Investment Tracking (Basic)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS investments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                investment_name TEXT NOT NULL,
                investment_type TEXT NOT NULL,  -- stocks, bonds, mutual_funds, crypto, real_estate
                symbol TEXT,
                quantity REAL DEFAULT 0.0,
                purchase_price REAL NOT NULL,
                current_price REAL DEFAULT 0.0,
                purchase_date TEXT NOT NULL,
                platform TEXT,
                is_active BOOLEAN DEFAULT 1,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # Notification and Alert System
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                notification_type TEXT NOT NULL,  -- budget_alert, goal_milestone, bill_reminder, insight
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                priority TEXT DEFAULT 'medium',  -- low, medium, high, urgent
                is_read BOOLEAN DEFAULT 0,
                action_required BOOLEAN DEFAULT 0,
                action_url TEXT,
                metadata TEXT DEFAULT '{}',
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                read_at TEXT,
                FOREIGN KEY (user_email) REFERENCES users_enhanced (email)
            )
        ''')
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses_enhanced(user_email, date)",
            "CREATE INDEX IF NOT EXISTS idx_income_user_active ON income_sources(user_email, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_budgets_user_active ON budgets_enhanced(user_email, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_goals_user_active ON goals_enhanced(user_email, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_analytics_user_date ON financial_analytics(user_email, metric_date)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_session ON conversation_history(user_email, session_id)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_email, is_read)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_time ON audit_logs(user_email, timestamp)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        conn.commit()
        conn.close()
        print("Enhanced database schema initialized successfully!")
    
    def migrate_existing_data(self):
        """Migrate data from old tables to new enhanced tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Migrate existing expenses
            cursor.execute("SELECT * FROM expenses")
            old_expenses = cursor.fetchall()
            
            for expense in old_expenses:
                cursor.execute('''
                    INSERT OR IGNORE INTO expenses_enhanced 
                    (user_email, amount, description, category, date, auto_categorized)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (expense[1], expense[2], expense[3], expense[4], expense[5], 0))
            
            # Migrate existing goals
            cursor.execute("SELECT * FROM goals")
            old_goals = cursor.fetchall()
            
            for goal in old_goals:
                cursor.execute('''
                    INSERT OR IGNORE INTO goals_enhanced 
                    (user_email, title, goal_type, target_amount, current_amount, target_date, start_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (goal[1], goal[2], goal[3], goal[4], goal[5], goal[6], goal[7] if len(goal) > 7 else goal[6]))
            
            # Migrate existing budgets
            cursor.execute("SELECT * FROM budgets")
            old_budgets = cursor.fetchall()
            
            for budget in old_budgets:
                cursor.execute('''
                    INSERT OR IGNORE INTO budgets_enhanced 
                    (user_email, name, category, amount, period, start_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (budget[1], budget[2], budget[2], budget[3], budget[4], budget[5]))
            
            conn.commit()
            print("Data migration completed successfully!")
            
        except Exception as e:
            print(f"Migration warning: {e} (This is expected if running for the first time)")
        
        finally:
            conn.close()

if __name__ == "__main__":
    # Initialize the enhanced database
    db_path = Path("finance_data/finance.db")
    db_manager = DatabaseManager(db_path)
    db_manager.migrate_existing_data()