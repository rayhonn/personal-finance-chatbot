"""
Advanced Income Management System
Comprehensive income tracking, forecasting, and analysis
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import calendar

class IncomeManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def add_income_source(self, user_email: str, source_data: Dict) -> bool:
        """Add a new income source"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO income_sources (
                    user_email, source_name, source_type, amount, frequency,
                    start_date, end_date, is_recurring, tax_rate, description,
                    category, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_email,
                source_data['source_name'],
                source_data['source_type'],
                source_data['amount'],
                source_data['frequency'],
                source_data['start_date'],
                source_data.get('end_date'),
                source_data.get('is_recurring', True),
                source_data.get('tax_rate', 0.0),
                source_data.get('description', ''),
                source_data.get('category', 'primary'),
                json.dumps(source_data.get('metadata', {}))
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error adding income source: {e}")
            return False
    
    def get_user_income_sources(self, user_email: str, active_only: bool = True) -> List[Dict]:
        """Get all income sources for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = '''
                SELECT * FROM income_sources 
                WHERE user_email = ?
            '''
            params = [user_email]
            
            if active_only:
                query += ' AND is_active = 1'
            
            query += ' ORDER BY created_at DESC'
            
            cursor.execute(query, params)
            sources = cursor.fetchall()
            conn.close()
            
            # Convert to list of dictionaries
            income_sources = []
            for source in sources:
                income_sources.append({
                    'id': source[0],
                    'user_email': source[1],
                    'source_name': source[2],
                    'source_type': source[3],
                    'amount': source[4],
                    'frequency': source[5],
                    'start_date': source[6],
                    'end_date': source[7],
                    'is_active': source[8],
                    'is_recurring': source[9],
                    'tax_rate': source[10],
                    'description': source[11],
                    'category': source[12],
                    'metadata': json.loads(source[13]) if source[13] else {},
                    'created_at': source[14],
                    'updated_at': source[15]
                })
            
            return income_sources
            
        except Exception as e:
            print(f"Error getting income sources: {e}")
            return []
    
    def calculate_monthly_income(self, user_email: str) -> Dict:
        """Calculate total monthly income from all sources"""
        sources = self.get_user_income_sources(user_email)
        
        total_monthly = 0.0
        breakdown = {
            'salary': 0.0,
            'freelance': 0.0,
            'investment': 0.0,
            'business': 0.0,
            'other': 0.0
        }
        
        for source in sources:
            monthly_amount = self._convert_to_monthly(source['amount'], source['frequency'])
            total_monthly += monthly_amount
            
            source_type = source['source_type']
            if source_type in breakdown:
                breakdown[source_type] += monthly_amount
            else:
                breakdown['other'] += monthly_amount
        
        return {
            'total_monthly': total_monthly,
            'breakdown': breakdown,
            'source_count': len(sources)
        }
    
    def _convert_to_monthly(self, amount: float, frequency: str) -> float:
        """Convert any frequency to monthly amount"""
        conversions = {
            'monthly': 1.0,
            'weekly': 4.33,  # Average weeks per month
            'bi-weekly': 2.17,  # 26 payments per year / 12 months
            'yearly': 1/12,
            'daily': 30.44,  # Average days per month
            'one-time': 0.0  # Don't count one-time in monthly calculations
        }
        
        return amount * conversions.get(frequency, 1.0)
    
    def get_income_forecast(self, user_email: str, months_ahead: int = 12) -> Dict:
        """Generate income forecast for specified months"""
        sources = self.get_user_income_sources(user_email)
        
        forecast = []
        current_date = datetime.now().date()
        
        for month in range(months_ahead):
            target_date = current_date + timedelta(days=30 * month)
            monthly_income = 0.0
            
            for source in sources:
                start_date = datetime.strptime(source['start_date'], '%Y-%m-%d').date()
                end_date = None
                if source['end_date']:
                    end_date = datetime.strptime(source['end_date'], '%Y-%m-%d').date()
                
                # Check if source is active during target month
                if start_date <= target_date and (not end_date or end_date >= target_date):
                    monthly_amount = self._convert_to_monthly(source['amount'], source['frequency'])
                    monthly_income += monthly_amount
            
            forecast.append({
                'month': target_date.strftime('%Y-%m'),
                'month_name': target_date.strftime('%B %Y'),
                'projected_income': monthly_income
            })
        
        return {
            'forecast': forecast,
            'total_projected': sum(f['projected_income'] for f in forecast),
            'average_monthly': sum(f['projected_income'] for f in forecast) / months_ahead if months_ahead > 0 else 0
        }
    
    def calculate_tax_estimates(self, user_email: str) -> Dict:
        """Calculate tax estimates based on income and tax rates"""
        monthly_income = self.calculate_monthly_income(user_email)
        sources = self.get_user_income_sources(user_email)
        
        total_gross_yearly = monthly_income['total_monthly'] * 12
        total_tax_yearly = 0.0
        
        # Calculate taxes by source
        tax_breakdown = {}
        for source in sources:
            yearly_income = self._convert_to_monthly(source['amount'], source['frequency']) * 12
            source_tax = yearly_income * (source['tax_rate'] / 100)
            total_tax_yearly += source_tax
            
            tax_breakdown[source['source_name']] = {
                'gross_income': yearly_income,
                'tax_rate': source['tax_rate'],
                'estimated_tax': source_tax,
                'net_income': yearly_income - source_tax
            }
        
        total_net_yearly = total_gross_yearly - total_tax_yearly
        
        return {
            'yearly': {
                'gross_income': total_gross_yearly,
                'estimated_tax': total_tax_yearly,
                'net_income': total_net_yearly,
                'effective_tax_rate': (total_tax_yearly / total_gross_yearly * 100) if total_gross_yearly > 0 else 0
            },
            'monthly': {
                'gross_income': total_gross_yearly / 12,
                'estimated_tax': total_tax_yearly / 12,
                'net_income': total_net_yearly / 12
            },
            'source_breakdown': tax_breakdown
        }
    
    def track_income_growth(self, user_email: str) -> Dict:
        """Track income growth over time"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get historical income data (simulated with creation dates)
            cursor.execute('''
                SELECT 
                    DATE(created_at) as date,
                    SUM(amount) as total_amount,
                    COUNT(*) as source_count
                FROM income_sources
                WHERE user_email = ? AND is_active = 1
                GROUP BY DATE(created_at)
                ORDER BY date
            ''', (user_email,))
            
            history = cursor.fetchall()
            conn.close()
            
            if not history:
                return {'growth_data': [], 'growth_rate': 0.0, 'trend': 'stable'}
            
            growth_data = []
            for record in history:
                growth_data.append({
                    'date': record[0],
                    'income': record[1],
                    'source_count': record[2]
                })
            
            # Calculate growth rate
            if len(growth_data) >= 2:
                first_income = growth_data[0]['income']
                last_income = growth_data[-1]['income']
                growth_rate = ((last_income - first_income) / first_income * 100) if first_income > 0 else 0
                
                if growth_rate > 5:
                    trend = 'increasing'
                elif growth_rate < -5:
                    trend = 'decreasing'
                else:
                    trend = 'stable'
            else:
                growth_rate = 0.0
                trend = 'stable'
            
            return {
                'growth_data': growth_data,
                'growth_rate': growth_rate,
                'trend': trend,
                'total_sources': len(growth_data)
            }
            
        except Exception as e:
            print(f"Error tracking income growth: {e}")
            return {'growth_data': [], 'growth_rate': 0.0, 'trend': 'stable'}
    
    def get_income_insights(self, user_email: str) -> Dict:
        """Generate intelligent insights about income"""
        monthly_income = self.calculate_monthly_income(user_email)
        tax_info = self.calculate_tax_estimates(user_email)
        growth_info = self.track_income_growth(user_email)
        
        insights = []
        
        # Income diversity insight
        active_sources = len([s for s in self.get_user_income_sources(user_email) if s['is_active']])
        if active_sources == 1:
            insights.append({
                'type': 'warning',
                'title': 'Income Diversification',
                'message': 'Consider diversifying your income sources to reduce financial risk.',
                'action': 'Add additional income streams'
            })
        elif active_sources >= 3:
            insights.append({
                'type': 'success',
                'title': 'Well Diversified',
                'message': f'Great job maintaining {active_sources} income sources!',
                'action': 'Keep monitoring and optimizing'
            })
        
        # Tax efficiency insight
        effective_tax_rate = tax_info['yearly']['effective_tax_rate']
        if effective_tax_rate > 25:
            insights.append({
                'type': 'warning',
                'title': 'Tax Optimization',
                'message': f'Your effective tax rate is {effective_tax_rate:.1f}%. Consider tax optimization strategies.',
                'action': 'Consult a tax professional'
            })
        
        # Growth insight
        if growth_info['trend'] == 'increasing':
            insights.append({
                'type': 'success',
                'title': 'Income Growth',
                'message': f'Your income is growing at {growth_info["growth_rate"]:.1f}%!',
                'action': 'Consider increasing savings rate'
            })
        elif growth_info['trend'] == 'decreasing':
            insights.append({
                'type': 'warning',
                'title': 'Income Decline',
                'message': 'Your income has decreased recently. Focus on stability.',
                'action': 'Review and stabilize income sources'
            })
        
        return {
            'insights': insights,
            'income_stability_score': self._calculate_stability_score(user_email),
            'recommendations': self._generate_income_recommendations(user_email)
        }
    
    def _calculate_stability_score(self, user_email: str) -> float:
        """Calculate income stability score (0-100)"""
        sources = self.get_user_income_sources(user_email)
        
        if not sources:
            return 0.0
        
        score = 50.0  # Base score
        
        # Diversity bonus
        score += min(len(sources) * 10, 30)
        
        # Recurring income bonus
        recurring_sources = [s for s in sources if s['is_recurring']]
        if recurring_sources:
            score += 20 * (len(recurring_sources) / len(sources))
        
        # Primary income stability
        primary_sources = [s for s in sources if s['category'] == 'primary']
        if primary_sources:
            score += 10
        
        return min(score, 100.0)
    
    def _generate_income_recommendations(self, user_email: str) -> List[str]:
        """Generate personalized income recommendations"""
        sources = self.get_user_income_sources(user_email)
        monthly_income = self.calculate_monthly_income(user_email)
        
        recommendations = []
        
        if not sources:
            recommendations.append("Start by adding your primary income source")
            return recommendations
        
        # Check for missing income types
        source_types = {s['source_type'] for s in sources}
        
        if 'salary' not in source_types and 'freelance' not in source_types:
            recommendations.append("Consider adding employment or freelance income")
        
        if 'investment' not in source_types and monthly_income['total_monthly'] > 3000:
            recommendations.append("With good income, consider investment opportunities")
        
        if len(sources) == 1:
            recommendations.append("Diversify with additional income streams for stability")
        
        # Tax optimization
        total_tax_rate = sum(s['tax_rate'] for s in sources) / len(sources)
        if total_tax_rate > 20:
            recommendations.append("Explore tax-efficient income strategies")
        
        return recommendations
    
    def has_sufficient_income_for_budget(self, user_email: str, budget_amount: float) -> Tuple[bool, str]:
        """Check if user has sufficient income for a budget"""
        monthly_income = self.calculate_monthly_income(user_email)
        
        if monthly_income['total_monthly'] == 0:
            return False, "Please set up your income sources before creating budgets."
        
        if budget_amount > monthly_income['total_monthly'] * 0.5:
            return False, f"Budget amount (RM{budget_amount:.2f}) exceeds 50% of your monthly income (RM{monthly_income['total_monthly']:.2f}). Consider a smaller budget."
        
        return True, "Budget amount is reasonable based on your income."
    
    def has_sufficient_income_for_goal(self, user_email: str, goal_amount: float, target_months: int) -> Tuple[bool, str]:
        """Check if user has sufficient income for a goal"""
        monthly_income = self.calculate_monthly_income(user_email)
        
        if monthly_income['total_monthly'] == 0:
            return False, "Please set up your income sources before setting financial goals."
        
        required_monthly = goal_amount / target_months if target_months > 0 else goal_amount
        
        if required_monthly > monthly_income['total_monthly'] * 0.3:
            return False, f"This goal requires RM{required_monthly:.2f} per month, which is over 30% of your income. Consider adjusting the amount or timeline."
        
        return True, f"This goal is achievable with your current income of RM{monthly_income['total_monthly']:.2f} per month."