# Logging Configuration

## Overview
All application logs are centralized in `~/tmp/logs/` with automatic rotation to prevent disk space issues.

## Log Files

### 1. app.log
- **Purpose**: All application logs (INFO level and above)
- **Contains**: 
  - Application startup/shutdown
  - Redis connection status
  - Elasticsearch connection status
  - Cache operations
  - Rate limiting events
  - Business logic events

### 2. error.log
- **Purpose**: Error and critical logs only
- **Contains**:
  - Exceptions and stack traces
  - Critical failures
  - Service connection errors

### 3. access.log
- **Purpose**: HTTP access logs
- **Contains**:
  - All API requests with timestamps
  - Client IP addresses
  - HTTP methods and endpoints
  - Response status codes
- **Format**: `YYYY-MM-DD HH:MM:SS - LEVEL - IP:PORT - "METHOD /endpoint" STATUS`

## Log Rotation
- **Max file size**: 10 MB per file
- **Backup count**: 5 rotated files kept
- **Total disk usage**: ~165 MB maximum (3 files × 10 MB × 6 versions)
- **Rotation behavior**: When a file reaches 10 MB, it's renamed to `.log.1`, and a new `.log` file is created

## Configuration
Logging is configured in `backend/logger_config.py`:
- Uses Python's `RotatingFileHandler`
- Console output for development
- File output for production
- Automatic directory creation if missing

## Monitoring Tips

### View live logs:
```bash
# All logs
tail -f ~/tmp/logs/app.log

# Only errors
tail -f ~/tmp/logs/error.log

# HTTP access
tail -f ~/tmp/logs/access.log
```

### Search logs:
```bash
# Find errors in last hour
grep "ERROR" ~/tmp/logs/app.log | tail -100

# Find specific endpoint access
grep "/api/chat" ~/tmp/logs/access.log

# Count requests by endpoint
grep -o '"GET [^"]*"' ~/tmp/logs/access.log | sort | uniq -c | sort -rn
```

### Check log sizes:
```bash
ls -lh ~/tmp/logs/
```

## Integration with Infrastructure

### Redis Events
- Connection status: `✓ Redis connected`
- Cache hits/misses logged at DEBUG level
- Rate limit violations logged at WARNING level

### Elasticsearch Events
- Connection status: `✓ Elasticsearch connected`
- Index operations logged with elastic_transport
- Search queries logged at DEBUG level

### Rate Limiting
- Exceeded limits logged with client identifier
- Remaining quota logged for monitoring

## Production Best Practices
1. **Monitor error.log** - Set up alerts for new entries
2. **Rotate logs regularly** - Automatic with current config
3. **Backup logs** - Consider archiving to S3 or similar
4. **Aggregate logs** - Use ELK stack for large deployments
5. **Set up metrics** - Use Prometheus for log-based metrics

## Troubleshooting

### Logs not appearing?
```bash
# Check directory permissions
ls -la ~/tmp/logs/

# Check if server is running
lsof -i:8000

# Verify log configuration
grep -A 5 "LOG_DIR" backend/logger_config.py
```

### Access log empty?
- Ensure requests are actually reaching the server
- Check that uvicorn is using the custom log config
- Verify `get_uvicorn_log_config()` is passed to `uvicorn.run()`

### Error log filling up?
- Review and fix recurring errors
- Consider increasing rotation threshold
- Check for exception loops in application code

## Version Control
Log files are excluded from git via `.gitignore`:
```
*.log
logs/
```

This prevents accidental commits of sensitive log data.
