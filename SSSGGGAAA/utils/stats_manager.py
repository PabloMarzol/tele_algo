import csv
import os
from datetime import datetime

class StatsManager:
    def __init__(self, shared_context):
        """Initialize StatsManager"""

        # REFERENCIAS PRINCIPALES
        self.giveaway_system = shared_context['giveaway_system']
        self.logger = shared_context['logger']
        self.giveaway_type = shared_context['giveaway_type']
        
        # ACCESO A CONFIGURACIONES
        self.GIVEAWAY_CONFIGS = self.giveaway_system.GIVEAWAY_CONFIGS
        
        # 🔗 REFERENCIAS A OTROS MÓDULOS (inicializadas como None)
        self._file_manager = None
        
        self.logger.info(f"StatsManager initialized for {self.giveaway_type}")
    
    def set_module_references(self, file_manager):
        """
        Establecer referencias a otros módulos después de inicialización
        
        Args:
            file_manager (FileManager): Para leer archivos de historial y estadísticas
        """
        self._file_manager = file_manager
        
        self.logger.info(f"StatsManager: Module references set for {self.giveaway_type}")
    
    def _validate_references(self):
        """Validar que las referencias estén configuradas antes de usar"""
        if self._file_manager is None:
            raise RuntimeError("FileManager reference not set. Call set_module_references() first.")
    
    # ============================================================================
    # 🔧 FUNCIONES QUE LLAMAN AL CORE (ga_manager.py)
    # ============================================================================
    
    def get_all_giveaway_types(self):
        """Get list of all available giveaway types - DELEGATE TO CORE"""
        return self.giveaway_system.get_all_giveaway_types()
    
    def get_prize_amount(self, giveaway_type=None):
        """Get prize amount for specific type - DELEGATE TO CORE"""
        return self.giveaway_system.get_prize_amount(giveaway_type)
    
    def get_file_paths(self, giveaway_type=None):
        """Get file paths for specific giveaway type - DELEGATE TO CORE"""
        return self.giveaway_system.get_file_paths(giveaway_type)

    #============================================================================= 
    def get_stats(self, giveaway_type=None):
        """Get statistics for specific type or current type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # ✅ USAR FUNCIONES DEL CORE via giveaway_system
            # Count today's participants for this type
            if giveaway_type == self.giveaway_type:
                # Para el tipo actual, usar método directo
                today_participants = self.giveaway_system._get_period_participants_count()
            else:
                # Para otros tipos, necesitamos acceder a su archivo
                today_participants = self._count_participants_for_type(giveaway_type)
            
            # Count total winners for this type
            total_winners = 0
            file_paths = self.get_file_paths(giveaway_type)
            winners_file = file_paths['winners']
            
            if os.path.exists(winners_file):
                with open(winners_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    total_winners = sum(1 for row in reader)
            
            # Count unique historical users for this type
            unique_users = set()
            history_file = file_paths['history']
            
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['telegram_id'] != 'NO_PARTICIPANTS':
                            unique_users.add(row['telegram_id'])
            
            prize = self.get_prize_amount(giveaway_type)
            
            return {
                'giveaway_type': giveaway_type,
                'today_participants': today_participants,
                'total_participants': len(unique_users),
                'total_winners': total_winners,
                'total_prize_distributed': total_winners * prize,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} statistics: {e}")
            return {}

    def _count_participants_for_type(self, giveaway_type):
        """Helper to count participants for different giveaway type"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            count = 0
            
            file_paths = self.get_file_paths(giveaway_type)
            participants_file = file_paths['participants']
            
            if os.path.exists(participants_file):
                with open(participants_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if (row['registration_date'].startswith(today) and 
                            row['status'] == 'active'):
                            count += 1
            return count
        except Exception as e:
            self.logger.error(f"Error counting participants for {giveaway_type}: {e}")
            return 0
        
    def get_stats_all_types(self):
        """Get combined statistics for all giveaway types"""
        try:
            all_stats = {}
            combined_stats = {
                'total_participants_all': 0,
                'total_winners_all': 0,
                'total_prize_distributed_all': 0,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            for giveaway_type in self.get_all_giveaway_types():
                stats = self.get_stats(giveaway_type)
                all_stats[giveaway_type] = stats
                
                # Add to combined totals
                combined_stats['total_participants_all'] += stats.get('total_participants', 0)
                combined_stats['total_winners_all'] += stats.get('total_winners', 0)
                combined_stats['total_prize_distributed_all'] += stats.get('total_prize_distributed', 0)
            
            return {
                'by_type': all_stats,
                'combined': combined_stats
            }
            
        except Exception as e:
            self.logger.error(f"Error getting all types statistics: {e}")
            return {}

    def get_user_multi_type_stats(self, user_id):
        """Get user statistics across all giveaway types"""
        try:
            multi_stats = {}
            
            for giveaway_type in self.get_all_giveaway_types():
                stats = self.get_user_participation_stats(user_id, giveaway_type)
                multi_stats[giveaway_type] = stats
            
            # Calculate combined stats
            combined = {
                'total_participations_all': sum(stats['total_participations'] for stats in multi_stats.values()),
                'total_wins_all': sum(stats['total_wins'] for stats in multi_stats.values()),
                'total_prize_won_all': sum(stats['total_prize_won'] for stats in multi_stats.values()),
                'unique_accounts_all': len(set().union(*[stats['accounts_used'] for stats in multi_stats.values()])),
                'active_types': [gt for gt, stats in multi_stats.items() if stats['total_participations'] > 0]
            }
            
            return {
                'by_type': multi_stats,
                'combined': combined
            }
            
        except Exception as e:
            self.logger.error(f"Error getting multi-type user stats: {e}")
            return {}
        
    def get_user_participation_stats(self, user_id, giveaway_type=None):
        """Get participation stats for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            complete_history = self.get_user_complete_history(user_id, giveaway_type)
            
            if not complete_history:
                return {
                    'giveaway_type': giveaway_type,
                    'total_participations': 0,
                    'unique_accounts': 0,
                    'total_wins': 0,
                    'total_prize_won': 0,
                    'first_participation': None,
                    'last_participation': None,
                    'accounts_used': [],
                    'win_rate': 0,
                    'average_balance': 0
                }
            
            unique_accounts = list(set(entry['mt5_account'] for entry in complete_history))
            total_wins = sum(1 for entry in complete_history if entry['won_prize'])
            total_prize = sum(entry['prize_amount'] for entry in complete_history)
            win_rate = (total_wins / len(complete_history)) * 100 if complete_history else 0
            
            # Calculate average balance
            balances = [float(entry['balance']) for entry in complete_history if entry['balance']]
            average_balance = sum(balances) / len(balances) if balances else 0
            
            return {
                'giveaway_type': giveaway_type,
                'total_participations': len(complete_history),
                'unique_accounts': len(unique_accounts),
                'total_wins': total_wins,
                'total_prize_won': total_prize,
                'first_participation': complete_history[-1]['date'],  # Oldest
                'last_participation': complete_history[0]['date'],   # Most recent
                'accounts_used': unique_accounts,
                'win_rate': round(win_rate, 2),
                'average_balance': round(average_balance, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} participation stats: {e}")
            return None
        
    def get_user_complete_history(self, user_id, giveaway_type=None):
        """Get complete user history for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            user_history = []
            file_paths = self.get_file_paths(giveaway_type)
            history_file = file_paths['history']
            
            if not os.path.exists(history_file):
                return user_history
            
            with open(history_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row['telegram_id'] == str(user_id) and 
                        row['telegram_id'] != 'NO_PARTICIPANTS'):
                        user_history.append({
                            'date': row['date'],
                            'mt5_account': row['mt5_account'],
                            'balance': row['balance'],
                            'won_prize': row['won_prize'].lower() == 'true',
                            'prize_amount': float(row['prize_amount']) if row['prize_amount'] else 0,
                            'giveaway_type': row.get('giveaway_type', giveaway_type)
                        })
            
            # Sort by date (most recent first)
            user_history.sort(key=lambda x: x['date'], reverse=True)
            return user_history
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} complete history: {e}")
            return []

    def get_user_account_history(self, user_id, giveaway_type=None):
        """🔄 MODIFIED: Get user account history for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            complete_history = self.get_user_complete_history(user_id, giveaway_type)
            
            account_history = []
            for entry in complete_history:
                account_history.append({
                    'mt5_account': entry['mt5_account'],
                    'date': entry['date'],
                    'balance': entry['balance'],
                    'giveaway_type': entry['giveaway_type']
                })
            
            return account_history
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} user account history: {e}")
            return [] 

    def get_cross_type_analytics(self):
        """Compare performance across all giveaway types"""
        try:
            comparison = {}
            
            for giveaway_type in self.get_all_giveaway_types():
                stats = self.get_stats(giveaway_type)
                comparison[giveaway_type] = {
                    'participants': stats.get('total_participants', 0),
                    'winners': stats.get('total_winners', 0),
                    'prizes_distributed': stats.get('total_prize_distributed', 0),
                    'conversion_rate': (stats.get('total_winners', 0) / max(stats.get('total_participants', 1), 1)) * 100
                }
            
            return comparison
            
        except Exception as e:
            self.logger.error(f"Error getting cross-type analytics: {e}")
            return {}
        
    def get_type_comparison_report(self):
        """Generate comparison report between giveaway types"""
        try:
            all_stats = self.get_stats_all_types()
            cross_analytics = self.get_cross_type_analytics()
            
            return {
                'stats_summary': all_stats,
                'performance_comparison': cross_analytics,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            self.logger.error(f"Error generating type comparison report: {e}")
            return {}  
        
    def get_giveaway_analytics(self, days_back=30, giveaway_type=None):
        """🔄 MODIFIED: Get analytics for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        # Note: This would be a complex function requiring detailed implementation
        # For now, returning basic structure
        try:
            return {
                'giveaway_type': giveaway_type,
                'period_days': days_back,
                'message': 'Advanced analytics implementation needed'
            }
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} analytics: {e}")
            return {}
        
    def get_account_ownership_report(self, giveaway_type=None):
        """🔄 MODIFIED: Get account ownership report for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        # Note: Complex function requiring detailed implementation
        try:
            return {
                'giveaway_type': giveaway_type,
                'message': 'Account ownership report implementation needed'
            }
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} account report: {e}")
            return {}

    def get_top_participants_report(self, limit=10, giveaway_type=None):
        """🔄 MODIFIED: Get top participants for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        # Note: Complex function requiring detailed implementation
        try:
            return {
                'giveaway_type': giveaway_type,
                'limit': limit,
                'message': 'Top participants report implementation needed'
            }
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} top participants: {e}")
            return []

    def get_revenue_impact_analysis(self, giveaway_type=None):
        """🔄 MODIFIED: Get revenue analysis for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        # Note: Complex function requiring detailed implementation
        try:
            return {
                'giveaway_type': giveaway_type,
                'message': 'Revenue impact analysis implementation needed'
            }
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} revenue analysis: {e}")
            return {}
    
        
