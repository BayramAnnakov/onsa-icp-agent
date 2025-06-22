# Testing Memory Functionality

## Quick Test Steps

### 1. Create Some Data
Start the app and:
- Enter a business URL (e.g., "https://onsa.ai")
- Let it create an ICP
- Continue to prospect finding
- Note down some prospect names

### 2. Stop the App
- Press `Ctrl+C` to stop the web interface
- Run `python test_memory_persistence.py` to verify sessions were saved

### 3. Restart and Test Memory
Start the app again and try these queries:

#### Basic Memory Queries:
```
"What was the last ICP we created?"
"Show me my previous ICP"
"What companies did we analyze?"
```

#### Specific Memory Queries:
```
"What were the ICP criteria we used for company size?"
"Show me the prospects we found in our last session"
"What was the business URL we analyzed?"
```

#### Context Continuation:
```
"Continue from where we left off"
"Show me more prospects based on our previous ICP"
"Refine the ICP we created earlier"
```

## What to Expect

When memory is working correctly:

1. **The agent will use the `load_memory` tool** - You'll see it in the logs
2. **It will reference previous context** - "Based on our previous session..."
3. **It can retrieve specific details** - Company names, ICP criteria, prospects

## Checking the Database

### Using SQLite CLI:
```bash
sqlite3 data/adk_agent_memory.db

# Show all tables
.tables

# Count sessions
SELECT COUNT(*) FROM sessions;

# See recent sessions
SELECT app_name, user_id, id, create_time 
FROM sessions 
ORDER BY create_time DESC 
LIMIT 10;

# Exit
.quit
```

### Using the Test Script:
```bash
python test_memory_persistence.py
```

## Memory Limitations

Currently, the memory system:
- Stores session state in SQLite
- Each session has a unique ID
- Sessions are associated with user IDs
- The agent can query past sessions using semantic search

## Troubleshooting

If memory isn't working:

1. **Check environment variable**:
   ```bash
   echo $USE_DATABASE_MEMORY  # Should be "true"
   ```

2. **Check database file exists**:
   ```bash
   ls -la data/adk_agent_memory.db
   ```

3. **Check logs for memory queries**:
   ```bash
   grep "load_memory" logs/adk_agent_web.log
   ```

4. **Verify agent has memory tools**:
   ```bash
   grep "Added ADK load_memory tool" logs/adk_agent_web.log
   ```