import csv
import os
from datetime import datetime
import shutil

class FileManager:
    def __init__(self, shared_context):
        """
        Initialize FileManager
        
        Args:
            shared_context: Diccionario con referencias compartidas
        """
        # ✅ REFERENCIAS PRINCIPALES
        self.giveaway_system = shared_context['giveaway_system']
        self.logger = shared_context['logger']
        self.giveaway_type = shared_context['giveaway_type']
        self.data_dir = shared_context['data_dir']
        self.file_lock = shared_context['file_lock']
        
        # ✅ RUTAS DE ARCHIVOS
        self.participants_file = f"{self.data_dir}/participants.csv"
        self.winners_file = f"{self.data_dir}/winners.csv"
        self.history_file = f"{self.data_dir}/history.csv"
        self.pending_winners_file = f"{self.data_dir}/pending_winners.csv"
        
        self.logger.info(f"FileManager initialized for {self.giveaway_type}")
            
    def initialize_files(self):
        """🔄 MODIFIED: Create type-specific files and directories"""
        """Create type-specific files and directories"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Participants file
        if not os.path.exists(self.participants_file):
            with open(self.participants_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'registration_date', 'status'])
        
        # Winners file
        if not os.path.exists(self.winners_file):
            with open(self.winners_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'telegram_id', 'username', 'mt5_account', 'prize', 'giveaway_type'])
        
        # History file
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'won_prize', 'prize_amount', 'giveaway_type'])
        
        # Pending winners file
        if not os.path.exists(self.pending_winners_file):
            with open(self.pending_winners_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'telegram_id', 'username', 'first_name', 'mt5_account', 'prize', 'status', 'selected_time', 'confirmed_time', 'confirmed_by', 'giveaway_type'])
        
        self.logger.info(f"Files initialized for {self.giveaway_type}")

    # def get_file_paths(self, giveaway_type=None):
    #     """Get file paths for specific giveaway type"""
    #     if giveaway_type is None:
    #         giveaway_type = self.giveaway_type
        
    #     base_dir = f"./System_giveaway/data/{giveaway_type}"
    #     return {
    #         'participants': f"{base_dir}/participants.csv",
    #         'winners': f"{base_dir}/winners.csv",
    #         'history': f"{base_dir}/history.csv",
    #         'pending_winners': f"{base_dir}/pending_winners.csv"
    #     }  
    def get_file_paths(self, giveaway_type=None):
        """DELEGATE TO: Core ga_manager.py"""
        return self.giveaway_system.get_file_paths(giveaway_type)
    
    def get_prize_amount(self, giveaway_type=None):
        """Delegar configuración de premio al core"""
        return self.giveaway_system.get_prize_amount(giveaway_type)

    def get_all_giveaway_types(self):
        """Delegar lista de tipos al core"""
        return self.giveaway_system.get_all_giveaway_types()
    
    def get_pending_winners(self, giveaway_type=None):
        """Get pending winners for specific type - DELEGATE TO CORE"""
        return self.giveaway_system.get_pending_winners(giveaway_type)
    
    def _prepare_for_next_period(self, giveaway_type=None):
        """🔄 MODIFIED: Clean participants file for next period"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            participants_file = self.get_file_paths(giveaway_type)['participants']
            
            # Recreate empty participants file
            with open(participants_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'registration_date', 'status'])
            
            period_names = {
                'daily': 'next day',
                'weekly': 'next week', 
                'monthly': 'next month'
            }
            
            period_name = period_names.get(giveaway_type, 'next period')
            self.logger.info(f"{giveaway_type.title()} participants file prepared for {period_name}")
            
            print(f"🧹 DEBUG: {giveaway_type.title()} participants cleaned")
            print(f"📁 DEBUG: File {participants_file} is now empty")
            
        except Exception as e:
            self.logger.error(f"Error preparing {giveaway_type} file for next period: {e}")

    # 🆕 NEW: Multi-type cleanup function
    def cleanup_old_participants(self, giveaway_type=None, days=1):
        """Clean old participants for specific type or all types"""
        try:
            if giveaway_type is None:
                # Clean all types
                for gt in self.get_all_giveaway_types():
                    self._prepare_for_next_period(gt)
                self.logger.info("All giveaway types cleaned")
            else:
                self._prepare_for_next_period(giveaway_type)
                self.logger.info(f"{giveaway_type.title()} participants cleaned")
            
        except Exception as e:
            self.logger.error(f"Error in cleanup: {e}")

    def backup_history_file(self, giveaway_type=None):
        """🔄 MODIFIED: Create backup for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            history_file = self.get_file_paths(giveaway_type)['history']
            
            if not os.path.exists(history_file):
                return False
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{history_file}.backup_{timestamp}"
            
            import shutil
            shutil.copy2(history_file, backup_name)
            
            self.logger.info(f"{giveaway_type.title()} history backup created: {backup_name}")
            return backup_name
            
        except Exception as e:
            self.logger.error(f"Error creating {giveaway_type} backup: {e}")
            return False
        
    def debug_participant_cleanup(self, giveaway_type=None):
        """🔄 MODIFIED: Debug cleanup for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            print(f"🔍 DEBUG: Verifying {giveaway_type} file status...")
            
            file_paths = self.get_file_paths(giveaway_type)
            
            # Count current participants
            current_participants = 0
            if os.path.exists(file_paths['participants']):
                with open(file_paths['participants'], 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    current_participants = len(list(reader))
            
            # Count history
            total_history = 0
            if os.path.exists(file_paths['history']):
                with open(file_paths['history'], 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    total_history = len(list(reader))
            
            # Count pending
            pending_count = len(self.get_pending_winners(giveaway_type))
            
            print(f"📊 DEBUG: {giveaway_type.title()} status:")
            print(f"   Current participants: {current_participants}")
            print(f"   Total history: {total_history}")
            print(f"   Pending winners: {pending_count}")
            
            return {
                'giveaway_type': giveaway_type,
                'current_participants': current_participants,
                'total_history': total_history,
                'pending_winners': pending_count
            }
            
        except Exception as e:
            print(f"❌ DEBUG: Error verifying {giveaway_type} files: {e}")
            return None
        
    async def _save_empty_period_to_history(self, giveaway_type=None):
        """🔄 MODIFIED: Save empty period for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            history_file = self.get_file_paths(giveaway_type)['history']
            
            with open(history_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    today,
                    'NO_PARTICIPANTS',
                    'NO_PARTICIPANTS', 
                    'NO_PARTICIPANTS',
                    'NO_PARTICIPANTS',
                    0,
                    False,
                    0,
                    f'{giveaway_type}_empty'
                ])
            
            self.logger.info(f"{giveaway_type.title()} period without participants saved to history")
            
        except Exception as e:
            self.logger.error(f"Error saving empty {giveaway_type} period: {e}")

    async def _save_period_results_to_history(self, winner_data, giveaway_type=None):
        """🔄 MODIFIED: Save period results for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            winner_id = winner_data['telegram_id'] if winner_data else None
            
            participants_file = self.get_file_paths(giveaway_type)['participants']
            history_file = self.get_file_paths(giveaway_type)['history']
            
            # Read all participants for this period
            period_participants = []
            if os.path.exists(participants_file):
                with open(participants_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['status'] == 'active':
                            period_participants.append(row)
            
            if not period_participants:
                self.logger.info(f"No {giveaway_type} participants to save to history")
                return
            
            # Save each participant to permanent history
            prize = self.get_prize_amount(giveaway_type)
            
            with open(history_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                for participant in period_participants:
                    # Determine if won
                    won_prize = participant['telegram_id'] == winner_id
                    prize_amount = prize if won_prize else 0
                    
                    writer.writerow([
                        today,  # date
                        participant['telegram_id'],
                        participant['username'],
                        participant['first_name'],
                        participant['mt5_account'],
                        participant['balance'],
                        won_prize,  # won_prize (True/False)
                        prize_amount,  # prize_amount
                        giveaway_type  # giveaway_type
                    ])
            
            self.logger.info(f"Saved {len(period_participants)} {giveaway_type} participants to permanent history")
            
        except Exception as e:
            self.logger.error(f"Error saving {giveaway_type} period results to history: {e}")

    def _save_participant(self, participant_data, giveaway_type=None):
        """Save participant to type-specific file"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        with self.file_lock:
            try:
                participants_file = self.get_file_paths(giveaway_type)['participants']

                # Create directory if doesn't exist
                directory = os.path.dirname(participants_file)
                if not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
                
                # Create file with headers if doesn't exist
                file_exists = os.path.exists(participants_file)
                if not file_exists:
                    with open(participants_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(['telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'registration_date', 'status'])
                
                # Append participant data
                with open(participants_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        participant_data['telegram_id'],
                        participant_data['username'],
                        participant_data['first_name'],
                        participant_data['mt5_account'],
                        participant_data['balance'],
                        participant_data['registration_date'],
                        participant_data['status']
                    ])

                self.logger.info(f"{giveaway_type.title()} participant {participant_data['telegram_id']} saved")
                
            except Exception as e:
                self.logger.error(f"Error saving {giveaway_type} participant: {e}")

    def _save_confirmed_winner(self, winner_data, giveaway_type=None):
        """Save confirmed winner to type-specific file"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        with self.file_lock:
            try:
                today = datetime.now().strftime('%Y-%m-%d')
                winners_file = self.get_file_paths(giveaway_type)['winners']
                prize = self.get_prize_amount(giveaway_type)

                # Check if winner already exists
                if os.path.exists(winners_file):
                    with open(winners_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if (row['telegram_id'] == winner_data['telegram_id'] and 
                                row['date'] == today and
                                row.get('giveaway_type', giveaway_type) == giveaway_type):
                                self.logger.warning(f"Winner {winner_data['telegram_id']} already exists in {giveaway_type} winners file")
                                return
                
                # Save winner
                with open(winners_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        today,
                        winner_data['telegram_id'],
                        winner_data['username'],
                        winner_data['mt5_account'],
                        prize,
                        giveaway_type
                    ])
                    
                self.logger.info(f"{giveaway_type.title()} confirmed winner saved: {winner_data['telegram_id']}")
                
            except Exception as e:
                self.logger.error(f"Error saving {giveaway_type} confirmed winner: {e}")