# Operations Manual

## Deployment

### Docker Compose
The entire stack can be deployed using Docker Compose:
```bash
docker-compose up -d --build
```

### Environment Variables
Create a `.env` file in the root directory:
- `FLASK_SECRET_KEY`: Secure random string.
- `DATABASE_URL`: PostgreSQL connection string.
- `OPENROUTER_API_KEY`: For AI analysis.
- `LOG_LEVEL`: INFO/DEBUG.

## Maintenance

### Cleaning Up
Use the `start.ps1` script for maintenance:
- **Clean Logs/Temp**: `./start.ps1 -Mode Clean`
- **Wipe Data**: `./start.ps1 -Mode Wipeout` (Caution: Deletes DB and Results)

### Backup
- **Database**: Backup the `instance/app.db` (SQLite) or dump PostgreSQL.
- **Results**: Archive the `results/` directory.
- **Generated Apps**: Archive `generated/apps/`.

## Troubleshooting

### Common Issues

1.  **Service Not Starting**:
    - Check logs: `./start.ps1 -Mode Logs`
    - Check ports: Ensure 5000, 2001-2004 are free.
    - Check Docker: `docker ps`

2.  **Analysis Stuck**:
    - Check `TaskExecutionService` logs.
    - Restart services: `./start.ps1 -Mode Reload`.
    - Manually fix status: `python scripts/fix_task_statuses.py`.

3.  **Database Locked**:
    - Stop all python processes.
    - Delete `instance/app.db` (if using SQLite and data loss is acceptable).

## Monitoring

- **Health Check**: `./start.ps1 -Mode Health`
- **Status Dashboard**: `./start.ps1 -Mode Status`
- **API Health Endpoint**: `GET /api/health`
