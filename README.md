# Instagram BFa Tool for Railway

A high-performance Instagram Brute Force Attack tool with web interface, designed for Railway deployment with replica support.

## Features

- **Web Interface**: Clean, responsive UI on port 8080
- **Password File Upload**: Supports `.txt`, `.csv`, and `.json` formats
- **Multiple Username Support**: Test against single or multiple usernames
- **Railway Optimized**: Works with Railway replicas and scaling
- **Error Resistant**: Comprehensive error handling and retry logic
- **Fast Performance**: Concurrent password checking with rate limiting
- **Real-time Progress**: Live updates on task status and results
- **Instagram API Integration**: Uses instaloader for reliable Instagram access

## Password File Formats

The tool supports various password file formats:

### Text Files (.txt)
```
password1
password2
password3
```

Or comma-separated:
```
password1,password2,password3
```

Or with usernames:
```
username1:password1,password2
username2:password3,password4
```

### CSV Files (.csv)
```csv
password
password1
password2
password3
```

### JSON Files (.json)
```json
{
  "passwords": ["password1", "password2", "password3"]
}
```

Or:
```json
["password1", "password2", "password3"]
```

## Quick Start

### Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd instagram-bfa
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy and configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

5. Run the application:
```bash
python app.py
```

6. Open your browser to `http://localhost:8080`

### Railway Deployment

1. Push your code to a GitHub repository

2. Import the project in Railway:
   - Go to Railway.app
   - Click "New Project" -> "Deploy from GitHub repo"
   - Select your repository

3. Configure environment variables in Railway:
   - `PORT`: 8080
   - `SECRET_KEY`: Your secret key
   - `INSTAGRAM_RATE_LIMIT`: 60 (requests per minute)
   - `MAX_CONCURRENT_CHECKS`: 10
   - `REPLICA_ID`: Will be set automatically by Railway

4. Deploy!

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | Port to expose the web interface |
| `HOST` | 0.0.0.0 | Host to bind the server |
| `DEBUG` | False | Enable Flask debug mode |
| `SECRET_KEY` | - | Flask secret key (REQUIRED) |
| `INSTAGRAM_RATE_LIMIT` | 60 | Requests per minute to Instagram |
| `INSTAGRAM_TIMEOUT` | 30 | Timeout for Instagram requests (seconds) |
| `MAX_RETRIES` | 3 | Maximum retry attempts |
| `RETRY_DELAY` | 5 | Delay between retries (seconds) |
| `MAX_CONCURRENT_CHECKS` | 10 | Concurrent password checks |
| `BATCH_SIZE` | 100 | Password batch size |
| `MAX_FILE_SIZE` | 10485760 | Maximum upload file size (bytes) |
| `REPLICA_ID` | 0 | Current replica ID |
| `TOTAL_REPLICAS` | 1 | Total number of replicas |
| `WORKER_COUNT` | 4 | Gunicorn worker count |
| `GEVENT_WORKERS` | 10 | Gevent worker count |

### Railway-Specific Configuration

The tool is optimized for Railway with:

- **Automatic Replica Detection**: Uses Railway's `REPLICA_ID` environment variable
- **Health Checks**: Built-in `/health` endpoint for Railway health monitoring
- **Concurrency**: Configurable worker counts for optimal performance
- **Scaling**: Works seamlessly with Railway's auto-scaling

## API Endpoints

### Web Interface
- `GET /` - Main web interface
- `GET /health` - Health check endpoint

### REST API
- `GET /api/tasks` - List all tasks
- `POST /api/tasks` - Create a new BFa task
- `GET /api/tasks/<task_id>` - Get task details
- `DELETE /api/tasks/<task_id>` - Delete a task
- `POST /api/preview` - Preview password file

## Usage

1. **Upload Password File**: Select a file containing passwords
2. **Enter Usernames**: Comma-separated list of usernames to test
3. **Start Attack**: Click "Start BFa Attack"
4. **Monitor Progress**: Watch real-time progress and results

## Performance Optimization

The tool includes several performance optimizations:

- **Concurrent Processing**: Multiple passwords checked simultaneously
- **Rate Limiting**: Prevents Instagram from blocking requests
- **Batch Processing**: Processes passwords in configurable batches
- **Error Recovery**: Automatic retries for failed requests
- **Memory Efficiency**: Processes files in streams to handle large files

## Error Handling

The tool handles various error scenarios:

- **Invalid Credentials**: Properly identifies invalid usernames/passwords
- **Rate Limiting**: Respects Instagram's rate limits
- **Connection Issues**: Automatic retries for network problems
- **File Parsing**: Handles malformed password files gracefully
- **Memory Limits**: Processes large files without loading everything into memory

## Security Considerations

⚠️ **IMPORTANT**: This tool is for educational and testing purposes only. Unauthorized access to Instagram accounts is against Instagram's Terms of Service and may be illegal in your jurisdiction.

- Use only on accounts you own or have permission to test
- Respect Instagram's rate limits to avoid IP bans
- Do not use for malicious purposes
- Consider using proxy rotation for production use

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is provided as-is for educational purposes only.

## Support

For issues or questions, please open a GitHub issue.

---

**Built with ❤️ for Railway and Python**
