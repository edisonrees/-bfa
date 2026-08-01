#!/usr/bin/env python3
"""
Test suite for Instagram BFa application
"""

import unittest
import tempfile
import os
import time
from app import app
from instagram_api import instagram_handler, LoginResult
from file_processor import password_processor
from models import BFaTask, BFaResult, task_manager
from config import config

class TestInstagramBFa(unittest.TestCase):
    
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Create test upload directory
        os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
        
        # Clean up any existing tasks and files
        self._cleanup()
    
    def tearDown(self):
        self._cleanup()
    
    def _cleanup(self):
        # Clean up any test files
        if os.path.exists(config.UPLOAD_FOLDER):
            for filename in os.listdir(config.UPLOAD_FOLDER):
                filepath = os.path.join(config.UPLOAD_FOLDER, filename)
                try:
                    if os.path.isfile(filepath):
                        os.unlink(filepath)
                except:
                    pass
        
        # Clean up any test tasks
        all_tasks = task_manager.get_all_tasks()
        for task in all_tasks:
            try:
                task_manager.delete_task(task.task_id)
            except:
                pass
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('replica_id', data)
        self.assertIn('timestamp', data)
    
    def test_main_page(self):
        """Test main page loads"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Instagram BFa Tool', response.data)
    
    def test_tasks_endpoint_empty(self):
        """Test tasks endpoint with no tasks"""
        response = self.client.get('/api/tasks')
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 0)
        self.assertEqual(len(data['tasks']), 0)
    
    def test_file_preview_txt(self):
        """Test file preview with text file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('password1\npassword2\npassword3')
            temp_file = f.name
        
        try:
            with open(temp_file, 'rb') as f:
                response = self.client.post('/api/preview', data={'passwordFile': (f, 'test.txt')})
            
            self.assertEqual(response.status_code, 200)
            data = response.json
            self.assertTrue(data['success'])
            self.assertEqual(data['password_count'], 3)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_file_preview_csv(self):
        """Test file preview with CSV file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write('password\npass1\npass2\npass3')
            temp_file = f.name
        
        try:
            with open(temp_file, 'rb') as f:
                response = self.client.post('/api/preview', data={'passwordFile': (f, 'test.csv')})
            
            self.assertEqual(response.status_code, 200)
            data = response.json
            self.assertTrue(data['success'])
            # Should skip the header row, so 3 passwords
            self.assertEqual(data['password_count'], 3)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_file_preview_json(self):
        """Test file preview with JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"passwords": ["pass1", "pass2", "pass3"]}')
            temp_file = f.name
        
        try:
            with open(temp_file, 'rb') as f:
                response = self.client.post('/api/preview', data={'passwordFile': (f, 'test.json')})
            
            self.assertEqual(response.status_code, 200)
            data = response.json
            self.assertTrue(data['success'])
            self.assertEqual(data['password_count'], 3)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_file_processor_text_formats(self):
        """Test various text file formats"""
        # Test comma-separated
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('pass1,pass2,pass3')
            temp_file = f.name
        
        try:
            result = password_processor.process_password_file(temp_file)
            self.assertTrue(result['success'])
            self.assertEqual(result['password_count'], 3)
            self.assertIn('pass1', result['passwords'])
            self.assertIn('pass2', result['passwords'])
            self.assertIn('pass3', result['passwords'])
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        
        # Test user:password format
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('user1:pass1,pass2\nuser2:pass3')
            temp_file = f.name
        
        try:
            result = password_processor.process_password_file(temp_file)
            self.assertTrue(result['success'])
            self.assertEqual(result['password_count'], 3)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_rate_limiter(self):
        """Test rate limiter functionality"""
        # Test that rate limiter enforces minimum interval
        start_time = time.time()
        for i in range(5):
            instagram_handler.rate_limiter.wait()
        end_time = time.time()
        
        # With rate limit of 60/min, minimum interval is 1 second
        # 5 requests should take at least 4 seconds (1 second between each)
        elapsed = end_time - start_time
        self.assertGreaterEqual(elapsed, 4.0)
    
    def test_session_creation(self):
        """Test Instagram session creation"""
        session = instagram_handler.create_session()
        self.assertIsNotNone(session)
        self.assertEqual(type(session).__name__, 'Instaloader')
    
    def test_task_creation(self):
        """Test task creation and management"""
        task = BFaTask(
            username="testuser",
            usernames=["testuser"],
            password_file="test.txt",
            passwords=["pass1", "pass2", "pass3"]
        )
        
        self.assertEqual(task.username, "testuser")
        self.assertEqual(len(task.usernames), 1)
        self.assertEqual(len(task.passwords), 3)
        self.assertEqual(task.status, "pending")
        
        # Test task to dict
        task_dict = task.to_dict()
        self.assertIn('task_id', task_dict)
        self.assertIn('username', task_dict)
        self.assertIn('password_count', task_dict)
    
    def test_task_manager(self):
        """Test task manager functionality"""
        # Create a task
        task = task_manager.create_task(
            username="testuser",
            passwords=["pass1", "pass2"]
        )
        
        self.assertIsNotNone(task.task_id)
        
        # Get the task
        retrieved_task = task_manager.get_task(task.task_id)
        self.assertIsNotNone(retrieved_task)
        self.assertEqual(retrieved_task.username, "testuser")
        
        # Get all tasks
        all_tasks = task_manager.get_all_tasks()
        self.assertGreaterEqual(len(all_tasks), 1)
        
        # Delete the task
        result = task_manager.delete_task(task.task_id)
        self.assertTrue(result)
        
        # Verify deletion
        deleted_task = task_manager.get_task(task.task_id)
        self.assertIsNone(deleted_task)
    
    def test_multiple_usernames(self):
        """Test task creation with multiple usernames"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('pass1\npass2\npass3')
            temp_file = f.name
        
        try:
            with open(temp_file, 'rb') as f:
                response = self.client.post('/api/tasks', data={
                    'passwordFile': (f, 'passwords.txt'),
                    'usernames': 'user1,user2,user3'
                })
            
            self.assertEqual(response.status_code, 200)
            data = response.json
            self.assertTrue(data['success'])
            self.assertIn('task_id', data)
            
            # Check that the task was created
            tasks_response = self.client.get('/api/tasks')
            tasks_data = tasks_response.json
            self.assertEqual(tasks_data['count'], 1)
            
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

if __name__ == '__main__':
    unittest.main()
