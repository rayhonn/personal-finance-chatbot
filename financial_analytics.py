"""
Advanced Financial Analytics Engine
Comprehensive financial insights, health scoring, and predictive analytics
"""

import sqlite3
import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import statistics

@dataclass
class FinancialHealthScore:
    overall_score: float
    income_score: float
    expense_score: float
    saving_score: float
    goal_score: float
    debt_score: float
    emergency_fund_score: float
    factors: Dict
    recommendations: List[str]

class FinancialAnalytics:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def calculate_financial_health_score(self, user_email: str) -> FinancialHealthScore:
        """Calculate comprehensive financial health score"""
        
        # Get user data
        income_data = self._get_income_metrics(user_email)
        expense_data = self._get_expense_metrics(user_email)
        saving_data = self._get_saving_metrics(user_email)
        goal_data = self._get_goal_metrics(user_email)
        debt_data = self._get_debt_metrics(user_email)
        emergency_data = self._get_emergency_fund_metrics(user_email)
        
        # Calculate individual scores
        income_score = self._calculate_income_score(income_data)
        expense_score = self._calculate_expense_score(expense_data, income_data)
        saving_score = self._calculate_saving_score(saving_data, income_data)
        goal_score = self._calculate_goal_score(goal_data)
        debt_score = self._calculate_debt_score(debt_data, income_data)
        emergency_score = self._calculate_emergency_fund_score(emergency_data, expense_data)
        
        # Calculate weighted overall score
        weights = {
            'income': 0.20,
            'expense': 0.20,
            'saving': 0.25,
            'goal': 0.15,
            'debt': 0.10,
            'emergency': 0.10
        }
        
        overall_score = (
            income_score * weights['income'] +
            expense_score * weights['expense'] +
            saving_score * weights['saving'] +
            goal_score * weights['goal'] +
            debt_score * weights['debt'] +
            emergency_score * weights['emergency']
        )
        
        # Generate factors and recommendations
        factors = {
            'income_stability': income_data.get('stability', 0),
            'expense_control': expense_data.get('variance', 0),
            'saving_rate': saving_data.get('rate', 0),
            'goal_progress': goal_data.get('average_progress', 0),
            'debt_ratio': debt_data.get('ratio', 0),
            'emergency_coverage': emergency_data.get('months_covered', 0)
        }
        
        recommendations = self._generate_health_recommendations(
            income_score, expense_score, saving_score, 
            goal_score, debt_score, emergency_score
        )
        
        # Store the score in history
        self._store_health_score(user_email, FinancialHealthScore(
            overall_score, income_score, expense_score, saving_score,
            goal_score, debt_score, emergency_score, factors, recommendations
        ))
        
        return FinancialHealthScore(
            overall_score, income_score, expense_score, saving_score,
            goal_score, debt_score, emergency_score, factors, recommendations
        )
    
    def _get_income_metrics(self, user_email: str) -> Dict:
        """Get income-related metrics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get total monthly income
            cursor.execute('''
                SELECT SUM(amount), COUNT(*), AVG(tax_rate)
                FROM income_sources 
                WHERE user_email = ? AND is_active = 1
            ''', (user_email,))
            
            result = cursor.fetchone()
            total_income = result[0] or 0
            source_count = result[1] or 0
            avg_tax_rate = result[2] or 0
            
            # Calculate stability (more sources = more stable)
            stability = min(100, 30 + (source_count * 20))
            
            conn.close()
            
            return {
                'total_monthly': total_income,
                'source_count': source_count,
                'stability': stability,
                'avg_tax_rate': avg_tax_rate
            }
            
        except Exception as e:
            print(f"Error getting income metrics: {e}")
            return {'total_monthly': 0, 'source_count': 0, 'stability': 0, 'avg_tax_rate': 0}
    
    def _get_expense_metrics(self, user_email: str) -> Dict:
        """Get expense-related metrics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get last 3 months of expenses
            three_months_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT 
                    DATE(date) as expense_date,
                    SUM(amount) as daily_total
                FROM expenses_enhanced 
                WHERE user_email = ? AND date >= ?
                GROUP BY DATE(date)
                ORDER BY expense_date
            ''', (user_email, three_months_ago))
            
            daily_expenses = cursor.fetchall()
            
            if not daily_expenses:
                return {'monthly_average': 0, 'variance': 100, 'trend': 'stable'}
            
            amounts = [float(exp[1]) for exp in daily_expenses]
            monthly_average = sum(amounts) * 30 / len(amounts)  # Extrapolate to monthly
            
            # Calculate variance (lower is better)
            if len(amounts) > 1:
                variance = statistics.stdev(amounts) / statistics.mean(amounts) * 100
            else:
                variance = 0
            
            # Calculate trend
            if len(amounts) >= 7:
                first_week = statistics.mean(amounts[:7])
                last_week = statistics.mean(amounts[-7:])
                trend_change = (last_week - first_week) / first_week * 100 if first_week > 0 else 0
                
                if trend_change > 10:
                    trend = 'increasing'
                elif trend_change < -10:
                    trend = 'decreasing'
                else:
                    trend = 'stable'
            else:
                trend = 'stable'
            
            conn.close()
            
            return {
                'monthly_average': monthly_average,
                'variance': min(variance, 100),  # Cap at 100
                'trend': trend,
                'data_points': len(amounts)
            }
            
        except Exception as e:
            print(f"Error getting expense metrics: {e}")
            return {'monthly_average': 0, 'variance': 100, 'trend': 'stable'}
    
    def _get_saving_metrics(self, user_email: str) -> Dict:
        """Get saving-related metrics"""
        income_data = self._get_income_metrics(user_email)
        expense_data = self._get_expense_metrics(user_email)
        
        monthly_income = income_data['total_monthly']
        monthly_expenses = expense_data['monthly_average']
        
        if monthly_income > 0:
            saving_amount = monthly_income - monthly_expenses
            saving_rate = max(0, (saving_amount / monthly_income) * 100)
        else:
            saving_amount = 0
            saving_rate = 0
        
        return {
            'monthly_amount': saving_amount,
            'rate': saving_rate,
            'goal': 20  # Target saving rate of 20%
        }
    
    def _get_goal_metrics(self, user_email: str) -> Dict:
        """Get goal-related metrics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_goals,
                    COUNT(CASE WHEN is_achieved = 1 THEN 1 END) as achieved_goals,
                    AVG(completion_percentage) as avg_progress,
                    SUM(target_amount) as total_target,
                    SUM(current_amount) as total_saved
                FROM goals_enhanced 
                WHERE user_email = ? AND is_active = 1
            ''', (user_email,))
            
            result = cursor.fetchone()
            
            total_goals = result[0] or 0
            achieved_goals = result[1] or 0
            avg_progress = result[2] or 0
            total_target = result[3] or 0
            total_saved = result[4] or 0
            
            achievement_rate = (achieved_goals / total_goals * 100) if total_goals > 0 else 0
            
            conn.close()
            
            return {
                'total_goals': total_goals,
                'achieved_goals': achieved_goals,
                'achievement_rate': achievement_rate,
                'average_progress': avg_progress,
                'total_target': total_target,
                'total_saved': total_saved
            }
            
        except Exception as e:
            print(f"Error getting goal metrics: {e}")
            return {
                'total_goals': 0, 'achieved_goals': 0, 'achievement_rate': 0,
                'average_progress': 0, 'total_target': 0, 'total_saved': 0
            }
    
    def _get_debt_metrics(self, user_email: str) -> Dict:
        """Get debt-related metrics (simulated)"""
        # This would integrate with actual debt tracking
        # For now, return default values
        return {
            'total_debt': 0,
            'monthly_payments': 0,
            'ratio': 0,  # Debt-to-income ratio
            'types': []
        }
    
    def _get_emergency_fund_metrics(self, user_email: str) -> Dict:
        """Get emergency fund metrics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Look for emergency fund goals
            cursor.execute('''
                SELECT SUM(current_amount)
                FROM goals_enhanced 
                WHERE user_email = ? AND goal_type = 'emergency_fund' AND is_active = 1
            ''', (user_email,))
            
            result = cursor.fetchone()
            emergency_amount = result[0] or 0
            
            conn.close()
            
            # Calculate months covered
            expense_data = self._get_expense_metrics(user_email)
            monthly_expenses = expense_data['monthly_average']
            
            if monthly_expenses > 0:
                months_covered = emergency_amount / monthly_expenses
            else:
                months_covered = 0
            
            return {
                'amount': emergency_amount,
                'months_covered': months_covered,
                'target_months': 6  # Recommended 6 months
            }
            
        except Exception as e:
            print(f"Error getting emergency fund metrics: {e}")
            return {'amount': 0, 'months_covered': 0, 'target_months': 6}
    
    def _calculate_income_score(self, income_data: Dict) -> float:
        """Calculate income score (0-100)"""
        if income_data['total_monthly'] == 0:
            return 0
        
        score = 0
        
        # Base score for having income
        score += 40
        
        # Stability bonus
        score += min(income_data['stability'] * 0.3, 30)
        
        # Multiple sources bonus
        if income_data['source_count'] > 1:
            score += 20
        elif income_data['source_count'] > 2:
            score += 30
        
        # Income level bonus (Malaysian context)
        if income_data['total_monthly'] > 5000:
            score += 10
        
        return min(score, 100)
    
    def _calculate_expense_score(self, expense_data: Dict, income_data: Dict) -> float:
        """Calculate expense management score (0-100)"""
        score = 50  # Base score
        
        # Expense-to-income ratio
        if income_data['total_monthly'] > 0:
            expense_ratio = expense_data['monthly_average'] / income_data['total_monthly']
            if expense_ratio < 0.5:
                score += 30
            elif expense_ratio < 0.7:
                score += 20
            elif expense_ratio < 0.9:
                score += 10
            else:
                score -= 20
        
        # Low variance bonus (consistent spending)
        if expense_data['variance'] < 20:
            score += 20
        elif expense_data['variance'] < 40:
            score += 10
        
        return max(0, min(score, 100))
    
    def _calculate_saving_score(self, saving_data: Dict, income_data: Dict) -> float:
        """Calculate saving score (0-100)"""
        saving_rate = saving_data['rate']
        
        if saving_rate <= 0:
            return 0
        elif saving_rate < 10:
            return 30
        elif saving_rate < 20:
            return 60
        elif saving_rate < 30:
            return 80
        else:
            return 100
    
    def _calculate_goal_score(self, goal_data: Dict) -> float:
        """Calculate goal achievement score (0-100)"""
        if goal_data['total_goals'] == 0:
            return 50  # Neutral score for no goals
        
        # Base score from average progress
        score = goal_data['average_progress']
        
        # Achievement bonus
        if goal_data['achievement_rate'] > 0:
            score += goal_data['achievement_rate'] * 0.5
        
        # Active goals bonus
        if goal_data['total_goals'] >= 3:
            score += 10
        
        return min(score, 100)
    
    def _calculate_debt_score(self, debt_data: Dict, income_data: Dict) -> float:
        """Calculate debt management score (0-100)"""
        if debt_data['total_debt'] == 0:
            return 100  # Perfect score for no debt
        
        # Calculate debt-to-income ratio
        if income_data['total_monthly'] > 0:
            debt_ratio = debt_data['monthly_payments'] / income_data['total_monthly']
            if debt_ratio < 0.1:
                return 90
            elif debt_ratio < 0.2:
                return 70
            elif debt_ratio < 0.3:
                return 50
            else:
                return 20
        
        return 50
    
    def _calculate_emergency_fund_score(self, emergency_data: Dict, expense_data: Dict) -> float:
        """Calculate emergency fund score (0-100)"""
        months_covered = emergency_data['months_covered']
        
        if months_covered >= 6:
            return 100
        elif months_covered >= 3:
            return 70
        elif months_covered >= 1:
            return 40
        elif months_covered > 0:
            return 20
        else:
            return 0
    
    def _generate_health_recommendations(self, income_score: float, expense_score: float, 
                                       saving_score: float, goal_score: float, 
                                       debt_score: float, emergency_score: float) -> List[str]:
        """Generate personalized recommendations"""
        recommendations = []
        
        if income_score < 60:
            recommendations.append("Focus on stabilizing and diversifying your income sources")
        
        if expense_score < 60:
            recommendations.append("Work on controlling and tracking your expenses more carefully")
        
        if saving_score < 60:
            recommendations.append("Increase your saving rate - aim for at least 20% of income")
        
        if goal_score < 60:
            recommendations.append("Set specific financial goals and track progress regularly")
        
        if debt_score < 60:
            recommendations.append("Focus on debt reduction to improve financial flexibility")
        
        if emergency_score < 60:
            recommendations.append("Build an emergency fund covering 3-6 months of expenses")
        
        if not recommendations:
            recommendations.append("Great job! Continue monitoring and optimizing your finances")
        
        return recommendations
    
    def _store_health_score(self, user_email: str, score: FinancialHealthScore):
        """Store health score in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO health_score_history (
                    user_email, overall_score, income_score, expense_score,
                    saving_score, goal_score, debt_score, emergency_fund_score,
                    score_factors, recommendations, calculated_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_email, score.overall_score, score.income_score, score.expense_score,
                score.saving_score, score.goal_score, score.debt_score, score.emergency_fund_score,
                json.dumps(score.factors), json.dumps(score.recommendations),
                datetime.now().strftime('%Y-%m-%d')
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error storing health score: {e}")
    
    def get_spending_insights(self, user_email: str) -> Dict:
        """Generate advanced spending insights"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get last 30 days of expenses
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT category, SUM(amount) as total, COUNT(*) as count,
                       AVG(amount) as avg_amount
                FROM expenses_enhanced
                WHERE user_email = ? AND date >= ?
                GROUP BY category
                ORDER BY total DESC
            ''', (user_email, thirty_days_ago))
            
            category_data = cursor.fetchall()
            
            # Analyze patterns
            insights = []
            total_spending = sum(row[1] for row in category_data)
            
            for category, amount, count, avg_amount in category_data:
                percentage = (amount / total_spending * 100) if total_spending > 0 else 0
                
                if percentage > 40:
                    insights.append({
                        'type': 'warning',
                        'category': category,
                        'message': f'{category.title()} represents {percentage:.1f}% of your spending',
                        'suggestion': f'Consider reducing {category.lower()} expenses'
                    })
                elif count > 20:
                    insights.append({
                        'type': 'info',
                        'category': category,
                        'message': f'You had {count} {category.lower()} transactions this month',
                        'suggestion': f'Look for patterns in your {category.lower()} spending'
                    })
            
            conn.close()
            
            return {
                'insights': insights,
                'total_spending': total_spending,
                'category_breakdown': [
                    {
                        'category': row[0],
                        'amount': row[1],
                        'count': row[2],
                        'average': row[3],
                        'percentage': (row[1] / total_spending * 100) if total_spending > 0 else 0
                    }
                    for row in category_data
                ]
            }
            
        except Exception as e:
            print(f"Error generating spending insights: {e}")
            return {'insights': [], 'total_spending': 0, 'category_breakdown': []}
    
    def predict_future_expenses(self, user_email: str, months_ahead: int = 3) -> Dict:
        """Predict future expenses based on historical data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get historical monthly spending
            cursor.execute('''
                SELECT 
                    strftime('%Y-%m', date) as month,
                    SUM(amount) as total_amount
                FROM expenses_enhanced
                WHERE user_email = ?
                GROUP BY strftime('%Y-%m', date)
                ORDER BY month DESC
                LIMIT 6
            ''', (user_email,))
            
            historical_data = cursor.fetchall()
            
            if len(historical_data) < 2:
                return {'prediction': [], 'confidence': 'low', 'average_monthly': 0}
            
            # Calculate trend
            amounts = [row[1] for row in reversed(historical_data)]
            average_monthly = statistics.mean(amounts)
            
            # Simple linear trend calculation
            if len(amounts) >= 3:
                recent_trend = (amounts[-1] - amounts[-3]) / 2
            else:
                recent_trend = 0
            
            # Generate predictions
            predictions = []
            current_date = datetime.now()
            
            for i in range(months_ahead):
                future_date = current_date + timedelta(days=30 * (i + 1))
                predicted_amount = average_monthly + (recent_trend * (i + 1))
                predicted_amount = max(0, predicted_amount)  # Ensure non-negative
                
                predictions.append({
                    'month': future_date.strftime('%Y-%m'),
                    'month_name': future_date.strftime('%B %Y'),
                    'predicted_amount': predicted_amount,
                    'confidence': 'medium' if len(amounts) >= 4 else 'low'
                })
            
            conn.close()
            
            return {
                'predictions': predictions,
                'historical_average': average_monthly,
                'trend': 'increasing' if recent_trend > 0 else 'decreasing' if recent_trend < 0 else 'stable',
                'confidence': 'high' if len(amounts) >= 6 else 'medium' if len(amounts) >= 3 else 'low'
            }
            
        except Exception as e:
            print(f"Error predicting expenses: {e}")
            return {'predictions': [], 'confidence': 'low', 'historical_average': 0}
    
    def detect_spending_anomalies(self, user_email: str) -> List[Dict]:
        """Detect unusual spending patterns"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get last 60 days of daily spending
            sixty_days_ago = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT 
                    DATE(date) as expense_date,
                    SUM(amount) as daily_total,
                    category
                FROM expenses_enhanced
                WHERE user_email = ? AND date >= ?
                GROUP BY DATE(date), category
                ORDER BY expense_date DESC
            ''', (user_email, sixty_days_ago))
            
            daily_data = cursor.fetchall()
            
            if len(daily_data) < 10:
                return []
            
            # Group by category for analysis
            category_data = {}
            for date, amount, category in daily_data:
                if category not in category_data:
                    category_data[category] = []
                category_data[category].append(amount)
            
            anomalies = []
            
            for category, amounts in category_data.items():
                if len(amounts) < 5:
                    continue
                
                mean_amount = statistics.mean(amounts)
                std_amount = statistics.stdev(amounts) if len(amounts) > 1 else 0
                
                # Detect outliers (amounts > 2 standard deviations from mean)
                threshold = mean_amount + (2 * std_amount)
                
                for i, amount in enumerate(amounts):
                    if amount > threshold and amount > mean_amount * 1.5:
                        anomalies.append({
                            'category': category,
                            'amount': amount,
                            'average': mean_amount,
                            'deviation': ((amount - mean_amount) / mean_amount * 100),
                            'type': 'high_spending',
                            'severity': 'high' if amount > threshold * 1.5 else 'medium'
                        })
            
            conn.close()
            
            return sorted(anomalies, key=lambda x: x['deviation'], reverse=True)[:5]
            
        except Exception as e:
            print(f"Error detecting anomalies: {e}")
            return []