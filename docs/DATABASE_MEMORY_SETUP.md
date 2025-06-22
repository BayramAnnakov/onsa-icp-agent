# SQLite Database Memory Setup

This guide explains how to use SQLite database for persistent memory storage instead of VertexAI.

## Overview

The ADK agents can use SQLite for local persistent memory storage through Google ADK's `DatabaseSessionService`. This provides:

- **Persistent memory** across application restarts
- **No cloud dependencies** - works entirely offline
- **Easy setup** - just set an environment variable
- **Full compatibility** with existing ADK patterns

## Quick Setup

1. **Run the setup script**:
   ```bash
   ./scripts/setup_database_memory.sh
   ```

2. **Set environment variables**:
   ```bash
   export USE_DATABASE_MEMORY=true
   export DATABASE_URL=sqlite:///./data/adk_agent_memory.db
   ```

3. **Or add to `.env` file**:
   ```env
   USE_DATABASE_MEMORY=true
   DATABASE_URL=sqlite:///./data/adk_agent_memory.db
   ```

4. **Start the application**:
   ```bash
   python web_interface.py
   ```

## How It Works

When `USE_DATABASE_MEMORY=true`, the system:

1. Uses `DatabaseSessionService` from Google ADK
2. Creates a SQLite database at `./data/adk_agent_memory.db`
3. Persists all sessions and memory to the database
4. Automatically creates tables on first use

## Testing

Run the test script to verify the setup:

```bash
python test_database_memory.py
```

This will:
- Create a test database
- Create sessions
- Store and retrieve memories
- Verify persistence

## Database Location

By default, the database is stored at:
```
./data/adk_agent_memory.db
```

You can change this by setting the `DATABASE_URL` environment variable to any valid SQLite URL.

## Advantages Over VertexAI

1. **No GCP Setup Required** - Works immediately without any cloud configuration
2. **Free** - No cloud costs
3. **Local Development** - Perfect for development and testing
4. **Data Privacy** - All data stays on your machine
5. **Easy Backup** - Just copy the `.db` file

## Switching Between Memory Backends

The system supports multiple memory backends with this priority:

1. **SQLite Database** (if `USE_DATABASE_MEMORY=true`)
2. **Mock Memory** (if `USE_MOCK_MEMORY=true`)
3. **VertexAI** (if `VERTEX_AI_ENABLED=true`)
4. **In-Memory** (fallback, no persistence)

## Troubleshooting

### Database not persisting?
- Check that `USE_DATABASE_MEMORY=true` is set
- Verify the `data/` directory exists and is writable
- Check logs for any database initialization errors

### Performance issues?
- SQLite is suitable for development and moderate usage
- For high-volume production, consider VertexAI or PostgreSQL

### Want to reset the database?
```bash
rm data/adk_agent_memory.db
```

The database will be recreated on next run.