"""
Advanced Expense Categorization and Intelligence System
AI-powered expense categorization, duplicate detection, and trend analysis
"""

import sqlite3
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import difflib

@dataclass
class ExpenseInsight:
    category: str
    confidence: float
    reasoning: str
    suggestions: List[str]

class ExpenseIntelligence:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.category_keywords = {
            'food': [
                'restaurant', 'cafe', 'coffee', 'lunch', 'dinner', 'breakfast',
                'mcd', 'mcdonalds', 'kfc', 'pizza', 'burger', 'food court',
                'groceries', 'supermarket', 'tesco', 'giant', 'jaya grocer',
                'mamak', 'nasi', 'mee', 'char kuey teow', 'roti', 'dim sum',
                'steamboat', 'hotpot', 'sushi', 'korean bbq', 'italian',
                'food delivery', 'grab food', 'foodpanda', 'eating', 'meal'
            ],
            'transport': [
                'grab', 'taxi', 'bus', 'train', 'lrt', 'mrt', 'fuel', 'petrol',
                'gas', 'parking', 'toll', 'plus', 'car wash', 'mechanic',
                'service', 'tyre', 'battery', 'oil change', 'roadtax',
                'insurance', 'uber', 'transport', 'travel', 'flight',
                'hotel', 'airbnb', 'booking', 'trip', 'vacation'
            ],
            'entertainment': [
                'cinema', 'movie', 'netflix', 'spotify', 'youtube', 'gaming',
                'steam', 'playstation', 'xbox', 'concert', 'show', 'theatre',
                'karaoke', 'bowling', 'pool', 'arcade', 'theme park',
                'entertainment', 'fun', 'leisure', 'hobby', 'book', 'magazine'
            ],
            'shopping': [
                'shopping', 'mall', 'online', 'shopee', 'lazada', 'amazon',
                'clothes', 'fashion', 'shoes', 'bag', 'accessories', 'jewelry',
                'electronics', 'gadget', 'phone', 'laptop', 'furniture',
                'home', 'decoration', 'beauty', 'cosmetics', 'perfume',
                'pharmacy', 'guardian', 'watson', 'gifts', 'presents'
            ],
            'utilities': [
                'electricity', 'water', 'gas', 'internet', 'wifi', 'phone bill',
                'mobile', 'telco', 'maxis', 'celcom', 'digi', 'unifi',
                'astro', 'tv', 'cable', 'subscription', 'utility', 'bill'
            ],
            'housing': [
                'rent', 'mortgage', 'loan', 'house', 'apartment', 'condo',
                'maintenance', 'repair', 'renovation', 'furniture',
                'household', 'cleaning', 'laundry', 'property', 'real estate'
            ],
            'healthcare': [
                'doctor', 'clinic', 'hospital', 'medicine', 'pharmacy',
                'dental', 'dentist', 'eye', 'optometrist', 'health',
                'medical', 'insurance', 'supplement', 'vitamin', 'treatment'
            ],
            'education': [
                'school', 'university', 'college', 'course', 'class',
                'tuition', 'book', 'stationery', 'education', 'learning',
                'training', 'certification', 'exam', 'fee', 'student'
            ]
        }
        
        self.merchant_patterns = {
            'food': [
                r'mcd|mcdonalds?', r'kfc', r'pizza hut', r'dominos?',
                r'starbucks?', r'coffee bean', r'old town', r'toast box',
                r'kopitiam', r'food court', r'mamak', r'restoran?',
                r'cafe', r'bistro', r'deli', r'bakery'
            ],
            'transport': [
                r'grab', r'shell', r'petronas', r'esso', r'bhp',
                r'parking', r'toll', r'plus', r'touch n go',
                r'rapidkl', r'prasarana', r'mrt', r'lrt'
            ],
            'shopping': [
                r'shopee', r'lazada', r'amazon', r'zalora',
                r'uniqlo', r'h&m', r'zara', r'nike', r'adidas',
                r'guardian', r'watson', r'7-eleven', r'family mart'
            ],
            'utilities': [
                r'tnb|tenaga', r'syabas', r'air selangor', r'indah water',
                r'maxis', r'celcom', r'digi', r'unifi', r'astro'
            ]
        }
    
    def categorize_expense(self, description: str, amount: float, 
                          user_email: str = None) -> ExpenseInsight:
        """Advanced AI-powered expense categorization"""
        
        description_lower = description.lower()
        
        # Initialize scoring
        category_scores = {category: 0.0 for category in self.category_keywords.keys()}
        
        # 1. Keyword matching with weights
        for category, keywords in self.category_keywords.items():
            for keyword in keywords:
                if keyword in description_lower:
                    # Exact match gets higher score
                    if keyword == description_lower:
                        category_scores[category] += 3.0
                    # Whole word match
                    elif re.search(r'\b' + re.escape(keyword) + r'\b', description_lower):
                        category_scores[category] += 2.0
                    # Partial match
                    else:
                        category_scores[category] += 1.0
        
        # 2. Merchant pattern matching
        for category, patterns in self.merchant_patterns.items():
            for pattern in patterns:
                if re.search(pattern, description_lower, re.IGNORECASE):
                    category_scores[category] += 4.0
                    break
        
        # 3. Amount-based heuristics
        self._apply_amount_heuristics(category_scores, amount)
        
        # 4. Historical learning (if user provided)
        if user_email:
            self._apply_historical_learning(category_scores, description, user_email)
        
        # 5. Context-aware adjustments
        self._apply_context_adjustments(category_scores, description_lower)
        
        # Determine best category
        best_category = max(category_scores, key=category_scores.get)
        confidence = self._calculate_confidence(category_scores, best_category)
        
        # Generate reasoning and suggestions
        reasoning = self._generate_reasoning(description, best_category, category_scores)
        suggestions = self._generate_suggestions(best_category, amount, description)
        
        return ExpenseInsight(
            category=best_category,
            confidence=confidence,
            reasoning=reasoning,
            suggestions=suggestions
        )
    
    def _apply_amount_heuristics(self, scores: Dict, amount: float):
        """Apply amount-based categorization heuristics"""
        
        # Small amounts often food/transport
        if amount < 20:
            scores['food'] += 1.0
            scores['transport'] += 0.5
        
        # Medium amounts could be shopping/entertainment
        elif 20 <= amount < 100:
            scores['shopping'] += 0.5
            scores['entertainment'] += 0.5
        
        # Large amounts often housing/utilities
        elif amount >= 500:
            scores['housing'] += 1.0
            scores['utilities'] += 0.5
        
        # Very large amounts might be housing/education
        elif amount >= 1000:
            scores['housing'] += 2.0
            scores['education'] += 1.0
    
    def _apply_historical_learning(self, scores: Dict, description: str, user_email: str):
        """Learn from user's historical categorization patterns"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Find similar descriptions that user has categorized
            cursor.execute('''
                SELECT category, description, COUNT(*) as frequency
                FROM expenses_enhanced
                WHERE user_email = ? AND reviewed = 1
                GROUP BY category, description
                ORDER BY frequency DESC
                LIMIT 50
            ''', (user_email,))
            
            historical_data = cursor.fetchall()
            
            for category, hist_desc, frequency in historical_data:
                # Calculate similarity
                similarity = difflib.SequenceMatcher(None, description.lower(), 
                                                   hist_desc.lower()).ratio()
                
                if similarity > 0.7:  # High similarity threshold
                    scores[category] += frequency * similarity * 2.0
                elif similarity > 0.5:  # Medium similarity
                    scores[category] += frequency * similarity
            
            conn.close()
            
        except Exception as e:
            print(f"Error in historical learning: {e}")
    
    def _apply_context_adjustments(self, scores: Dict, description: str):
        """Apply context-aware adjustments"""
        
        # Time-based context
        current_hour = datetime.now().hour
        
        if 6 <= current_hour <= 10:  # Morning
            scores['food'] += 0.5  # Breakfast
        elif 11 <= current_hour <= 14:  # Lunch time
            scores['food'] += 1.0
        elif 18 <= current_hour <= 22:  # Dinner time
            scores['food'] += 1.0
        elif 22 <= current_hour or current_hour <= 2:  # Night
            scores['entertainment'] += 0.5
        
        # Day of week context
        weekday = datetime.now().weekday()
        if weekday >= 5:  # Weekend
            scores['entertainment'] += 0.5
            scores['shopping'] += 0.5
        
        # Currency or payment method context
        if any(word in description for word in ['cash', 'card', 'online']):
            scores['shopping'] += 0.3
    
    def _calculate_confidence(self, scores: Dict, best_category: str) -> float:
        """Calculate confidence score for categorization"""
        
        best_score = scores[best_category]
        total_score = sum(scores.values())
        
        if total_score == 0:
            return 0.3  # Low confidence for no matches
        
        # Confidence based on relative score strength
        relative_strength = best_score / total_score
        
        # Second best score for comparison
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) > 1:
            second_best = sorted_scores[1]
            gap = best_score - second_best
            gap_factor = min(gap / best_score, 1.0) if best_score > 0 else 0
        else:
            gap_factor = 1.0
        
        # Combine factors
        confidence = (relative_strength * 0.7) + (gap_factor * 0.3)
        
        # Scale to 0-1 range with some adjustments
        if best_score == 0:
            return 0.3
        elif best_score >= 3:
            return min(0.95, confidence + 0.2)
        else:
            return max(0.4, confidence)
    
    def _generate_reasoning(self, description: str, category: str, scores: Dict) -> str:
        """Generate human-readable reasoning for categorization"""
        
        reasons = []
        
        # Check for keyword matches
        matched_keywords = []
        for keyword in self.category_keywords.get(category, []):
            if keyword in description.lower():
                matched_keywords.append(keyword)
        
        if matched_keywords:
            reasons.append(f"Keywords found: {', '.join(matched_keywords[:3])}")
        
        # Check for merchant patterns
        for pattern in self.merchant_patterns.get(category, []):
            if re.search(pattern, description.lower(), re.IGNORECASE):
                reasons.append("Recognized merchant pattern")
                break
        
        # Score comparison
        best_score = scores[category]
        if best_score > 2:
            reasons.append("Strong keyword/pattern match")
        elif best_score > 1:
            reasons.append("Good keyword match")
        else:
            reasons.append("Best available match")
        
        return "; ".join(reasons) if reasons else "General categorization"
    
    def _generate_suggestions(self, category: str, amount: float, description: str) -> List[str]:
        """Generate helpful suggestions for the expense"""
        
        suggestions = []
        
        category_tips = {
            'food': [
                "Consider meal planning to reduce food costs",
                "Look for restaurant promotions and discounts",
                "Try cooking at home more often"
            ],
            'transport': [
                "Consider carpooling or public transport",
                "Track fuel efficiency and driving habits",
                "Look into transport apps for better deals"
            ],
            'shopping': [
                "Compare prices before purchasing",
                "Wait for sales and promotions",
                "Consider if this purchase is necessary"
            ],
            'entertainment': [
                "Look for free or low-cost entertainment options",
                "Set a monthly entertainment budget",
                "Consider sharing subscriptions with family"
            ],
            'utilities': [
                "Monitor usage to reduce bills",
                "Compare service providers",
                "Consider energy-efficient appliances"
            ]
        }
        
        # Add category-specific suggestions
        suggestions.extend(category_tips.get(category, [])[:2])
        
        # Amount-based suggestions
        if amount > 100:
            suggestions.append("Consider if this large expense fits your budget")
        
        return suggestions
    
    def detect_recurring_expenses(self, user_email: str) -> List[Dict]:
        """Detect recurring expense patterns"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get expenses from last 3 months
            three_months_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT description, amount, category, COUNT(*) as frequency,
                       AVG(amount) as avg_amount,
                       MIN(date) as first_date,
                       MAX(date) as last_date
                FROM expenses_enhanced
                WHERE user_email = ? AND date >= ?
                GROUP BY LOWER(description), category
                HAVING frequency >= 2
                ORDER BY frequency DESC, avg_amount DESC
            ''', (user_email, three_months_ago))
            
            recurring_data = cursor.fetchall()
            
            recurring_expenses = []
            for desc, amount, category, freq, avg_amt, first, last in recurring_data:
                
                # Calculate pattern strength
                amount_variance = abs(amount - avg_amt) / avg_amt if avg_amt > 0 else 0
                
                # Determine likely frequency
                first_date = datetime.strptime(first, '%Y-%m-%d')
                last_date = datetime.strptime(last, '%Y-%m-%d')
                days_span = (last_date - first_date).days
                
                if days_span > 0:
                    avg_days_between = days_span / (freq - 1) if freq > 1 else 0
                    
                    if 25 <= avg_days_between <= 35:
                        likely_frequency = "Monthly"
                    elif 6 <= avg_days_between <= 8:
                        likely_frequency = "Weekly"
                    elif 85 <= avg_days_between <= 95:
                        likely_frequency = "Quarterly"
                    else:
                        likely_frequency = "Irregular"
                else:
                    likely_frequency = "Unknown"
                
                recurring_expenses.append({
                    'description': desc,
                    'category': category,
                    'frequency': freq,
                    'average_amount': avg_amt,
                    'likely_frequency': likely_frequency,
                    'amount_variance': amount_variance,
                    'is_subscription': self._is_likely_subscription(desc, category),
                    'first_occurrence': first,
                    'last_occurrence': last
                })
            
            conn.close()
            return recurring_expenses
            
        except Exception as e:
            print(f"Error detecting recurring expenses: {e}")
            return []
    
    def _is_likely_subscription(self, description: str, category: str) -> bool:
        """Determine if expense is likely a subscription"""
        subscription_keywords = [
            'netflix', 'spotify', 'youtube', 'subscription', 'monthly',
            'premium', 'pro', 'plus', 'membership', 'astro', 'unifi'
        ]
        
        return (any(keyword in description.lower() for keyword in subscription_keywords) 
                or category in ['utilities', 'entertainment'])
    
    def detect_duplicate_expenses(self, user_email: str, days_back: int = 7) -> List[Dict]:
        """Detect potential duplicate expense entries"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get recent expenses
            date_threshold = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT id, description, amount, category, date, created_at
                FROM expenses_enhanced
                WHERE user_email = ? AND date >= ?
                ORDER BY created_at DESC
            ''', (user_email, date_threshold))
            
            expenses = cursor.fetchall()
            
            duplicates = []
            checked_pairs = set()
            
            for i, exp1 in enumerate(expenses):
                for j, exp2 in enumerate(expenses[i+1:], i+1):
                    
                    pair_key = tuple(sorted([exp1[0], exp2[0]]))
                    if pair_key in checked_pairs:
                        continue
                    checked_pairs.add(pair_key)
                    
                    # Check for duplicates
                    if self._are_likely_duplicates(exp1, exp2):
                        duplicates.append({
                            'expense1': {
                                'id': exp1[0],
                                'description': exp1[1],
                                'amount': exp1[2],
                                'category': exp1[3],
                                'date': exp1[4]
                            },
                            'expense2': {
                                'id': exp2[0],
                                'description': exp2[1],
                                'amount': exp2[2],
                                'category': exp2[3],
                                'date': exp2[4]
                            },
                            'similarity_score': self._calculate_similarity(exp1, exp2)
                        })
            
            conn.close()
            return duplicates
            
        except Exception as e:
            print(f"Error detecting duplicates: {e}")
            return []
    
    def _are_likely_duplicates(self, exp1: Tuple, exp2: Tuple) -> bool:
        """Check if two expenses are likely duplicates"""
        
        # Exact amount match
        if exp1[2] != exp2[2]:  # amount
            return False
        
        # Description similarity
        desc_similarity = difflib.SequenceMatcher(None, exp1[1].lower(), exp2[1].lower()).ratio()
        if desc_similarity < 0.8:
            return False
        
        # Date proximity (within 1 day)
        date1 = datetime.strptime(exp1[4], '%Y-%m-%d')
        date2 = datetime.strptime(exp2[4], '%Y-%m-%d')
        if abs((date1 - date2).days) > 1:
            return False
        
        # Same category
        if exp1[3] != exp2[3]:  # category
            return False
        
        return True
    
    def _calculate_similarity(self, exp1: Tuple, exp2: Tuple) -> float:
        """Calculate similarity score between two expenses"""
        
        desc_sim = difflib.SequenceMatcher(None, exp1[1].lower(), exp2[1].lower()).ratio()
        amount_sim = 1.0 if exp1[2] == exp2[2] else 0.0
        category_sim = 1.0 if exp1[3] == exp2[3] else 0.0
        
        date1 = datetime.strptime(exp1[4], '%Y-%m-%d')
        date2 = datetime.strptime(exp2[4], '%Y-%m-%d')
        date_diff = abs((date1 - date2).days)
        date_sim = max(0, 1.0 - (date_diff / 7.0))  # Similarity decreases over a week
        
        # Weighted average
        return (desc_sim * 0.4 + amount_sim * 0.3 + category_sim * 0.2 + date_sim * 0.1)
    
    def analyze_spending_trends(self, user_email: str, category: str = None) -> Dict:
        """Analyze spending trends for a user or category"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build query based on category filter
            if category:
                query = '''
                    SELECT 
                        DATE(date) as expense_date,
                        SUM(amount) as daily_total,
                        COUNT(*) as transaction_count
                    FROM expenses_enhanced
                    WHERE user_email = ? AND category = ?
                    GROUP BY DATE(date)
                    ORDER BY expense_date DESC
                    LIMIT 30
                '''
                params = (user_email, category)
            else:
                query = '''
                    SELECT 
                        DATE(date) as expense_date,
                        SUM(amount) as daily_total,
                        COUNT(*) as transaction_count
                    FROM expenses_enhanced
                    WHERE user_email = ?
                    GROUP BY DATE(date)
                    ORDER BY expense_date DESC
                    LIMIT 30
                '''
                params = (user_email,)
            
            cursor.execute(query, params)
            daily_data = cursor.fetchall()
            
            if not daily_data:
                return {'trend': 'no_data', 'insights': []}
            
            # Analyze trend
            amounts = [float(row[1]) for row in daily_data]
            
            # Simple trend analysis
            if len(amounts) >= 7:
                recent_avg = sum(amounts[:7]) / 7
                older_avg = sum(amounts[7:14]) / 7 if len(amounts) >= 14 else recent_avg
                
                if recent_avg > older_avg * 1.1:
                    trend = 'increasing'
                elif recent_avg < older_avg * 0.9:
                    trend = 'decreasing'
                else:
                    trend = 'stable'
            else:
                trend = 'insufficient_data'
            
            # Generate insights
            insights = []
            
            # Peak spending days
            max_amount = max(amounts)
            avg_amount = sum(amounts) / len(amounts)
            
            if max_amount > avg_amount * 2:
                insights.append({
                    'type': 'peak_spending',
                    'message': f'Highest daily spending was RM{max_amount:.2f}, significantly above average'
                })
            
            # Spending consistency
            import statistics
            if len(amounts) > 1:
                std_dev = statistics.stdev(amounts)
                cv = std_dev / avg_amount if avg_amount > 0 else 0
                
                if cv > 0.5:
                    insights.append({
                        'type': 'high_variance',
                        'message': 'Your spending varies significantly day to day'
                    })
                elif cv < 0.2:
                    insights.append({
                        'type': 'consistent_spending',
                        'message': 'Your spending is very consistent'
                    })
            
            conn.close()
            
            return {
                'trend': trend,
                'daily_data': [
                    {
                        'date': row[0],
                        'amount': row[1],
                        'transactions': row[2]
                    }
                    for row in daily_data
                ],
                'insights': insights,
                'average_daily': avg_amount,
                'total_days': len(daily_data)
            }
            
        except Exception as e:
            print(f"Error analyzing spending trends: {e}")
            return {'trend': 'error', 'insights': []}