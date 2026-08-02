"""
Password File Processor for Local Auth BFa
Handles various password file formats and optimizes processing
"""

import os
import re
import csv
import json
from typing import List, Generator, Optional
from pathlib import Path
import logging
from config import config

logger = logging.getLogger(__name__)

class PasswordFileProcessor:
    def __init__(self):
        self.upload_folder = config.UPLOAD_FOLDER
        self.allowed_extensions = config.ALLOWED_EXTENSIONS
        
        # Create upload folder if it doesn't exist
        os.makedirs(self.upload_folder, exist_ok=True)
        
    def allowed_file(self, filename: str) -> bool:
        """Check if the file has an allowed extension"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize the filename to prevent directory traversal"""
        # Remove any path information
        filename = os.path.basename(filename)
        # Remove any special characters that could be problematic
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        return filename

    def save_uploaded_file(self, file_storage) -> Optional[str]:
        """Save an uploaded file to the upload folder"""
        if not file_storage:
            return None
            
        filename = self.sanitize_filename(file_storage.filename)
        if not self.allowed_file(filename):
            return None
            
        filepath = os.path.join(self.upload_folder, filename)
        
        try:
            file_storage.save(filepath)
            logger.info(f"File saved: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return None

    def parse_password_file(self, filepath: str) -> List[str]:
        """Parse password file based on its extension"""
        extension = os.path.splitext(filepath)[1].lower()
        
        try:
            if extension == '.txt':
                return self._parse_txt_file(filepath)
            elif extension == '.csv':
                return self._parse_csv_file(filepath)
            elif extension == '.json':
                return self._parse_json_file(filepath)
            else:
                # Try to parse as text file
                return self._parse_txt_file(filepath)
        except Exception as e:
            logger.error(f"Error parsing file {filepath}: {e}")
            raise

    def _parse_txt_file(self, filepath: str) -> List[str]:
        """Parse a text file with various password formats"""
        passwords = []
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                # Handle different formats:
                # - password1
                # - password1,pas2,pas3
                # - user:password
                # - username:password1,pas2,pas3
                
                if ':' in line:
                    # Handle user:password format
                    parts = line.split(':', 1)
                    password_part = parts[1].strip()
                    if ',' in password_part:
                        # Multiple passwords for this user
                        pass_list = [p.strip() for p in password_part.split(',') if p.strip()]
                        passwords.extend(pass_list)
                    else:
                        passwords.append(password_part)
                elif ',' in line:
                    # Handle comma-separated passwords
                    pass_list = [p.strip() for p in line.split(',') if p.strip()]
                    passwords.extend(pass_list)
                else:
                    # Single password
                    passwords.append(line)
        
        return passwords

    def _parse_csv_file(self, filepath: str) -> List[str]:
        """Parse a CSV file with passwords"""
        passwords = []
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            for row_index, row in enumerate(reader):
                if not row:
                    continue
                    
                # Skip header row (first row) if it looks like a header
                if row_index == 0 and len(row) > 0:
                    first_cell = row[0].strip().lower()
                    if first_cell in ['password', 'passwords', 'pass', 'username', 'user']:
                        continue
                    
                for cell in row:
                    cell = cell.strip()
                    if cell and not cell.startswith('#'):
                        passwords.append(cell)
        
        return passwords

    def _parse_json_file(self, filepath: str) -> List[str]:
        """Parse a JSON file with passwords"""
        passwords = []
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
            
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        passwords.append(item)
                    elif isinstance(item, dict):
                        if 'password' in item:
                            passwords.append(item['password'])
                        elif 'pass' in item:
                            passwords.append(item['pass'])
            elif isinstance(data, dict):
                if 'passwords' in data:
                    passwords.extend(data['passwords'])
                elif 'password' in data:
                    passwords.append(data['password'])
        
        return passwords

    def process_password_file(self, filepath: str) -> dict:
        """Process a password file and return structured data"""
        try:
            passwords = self.parse_password_file(filepath)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_passwords = []
            for password in passwords:
                if password and password not in seen:
                    seen.add(password)
                    unique_passwords.append(password)
            
            return {
                'success': True,
                'filepath': filepath,
                'filename': os.path.basename(filepath),
                'password_count': len(unique_passwords),
                'passwords': unique_passwords,
                'error': None
            }
        except Exception as e:
            logger.error(f"Error processing file {filepath}: {e}")
            return {
                'success': False,
                'filepath': filepath,
                'filename': os.path.basename(filepath),
                'password_count': 0,
                'passwords': [],
                'error': str(e)
            }

    def get_password_generator(self, passwords: List[str], batch_size: int = 100) -> Generator[List[str], None, None]:
        """Generate batches of passwords for processing"""
        for i in range(0, len(passwords), batch_size):
            yield passwords[i:i + batch_size]

    def cleanup_file(self, filepath: str) -> bool:
        """Remove a file from the upload folder"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"File removed: {filepath}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing file {filepath}: {e}")
            return False

# Singleton instance
password_processor = PasswordFileProcessor()
