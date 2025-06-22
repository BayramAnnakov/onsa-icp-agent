# VertexAI Memory Service Setup Guide

This guide walks through setting up persistent memory for the ADK Multi-Agent Sales System using Google Cloud's Vertex AI.

## Overview

The VertexAI Memory Service provides:
- **Persistent Memory**: Conversations and context persist across sessions
- **Semantic Search**: Find relevant past interactions using natural language
- **Scalable Storage**: Leverage Google Cloud infrastructure
- **Enhanced Context**: Agents can build on previous interactions

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Google Cloud CLI** installed and configured
3. **Service Account** with appropriate permissions

## Setup Instructions

### 1. Enable Required APIs

```bash
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage.googleapis.com
```

### 2. Create Service Account

This has already been done in your setup:
```bash
gcloud iam service-accounts create adk-agent-memory \
    --display-name="ADK Agent Memory Service"
```

### 3. Configure Storage Bucket

The deployment script automatically creates the storage bucket:
```bash
gcloud storage buckets create gs://bayram-adk-hack-adk-sessions \
    --location=us-central1 \
    --project=bayram-adk-hack
```

### 4. Grant Permissions

The deployment script automatically grants required permissions:
```bash
# Storage permissions
gcloud storage buckets add-iam-policy-binding gs://bayram-adk-hack-adk-sessions \
    --member=serviceAccount:adk-agent-memory@bayram-adk-hack.iam.gserviceaccount.com \
    --role=roles/storage.objectUser

# Vertex AI permissions
gcloud projects add-iam-policy-binding bayram-adk-hack \
    --member=serviceAccount:adk-agent-memory@bayram-adk-hack.iam.gserviceaccount.com \
    --role=roles/aiplatform.user
```

### 5. Environment Configuration

Add to your `.env` file:
```bash
GOOGLE_CLOUD_PROJECT=bayram-adk-hack
GOOGLE_CLOUD_LOCATION=us-central1
VERTEX_AI_ENABLED=true
```

### 6. Configuration File

Your `config.yaml` should include:
```yaml
vertexai:
    project_id: ${GOOGLE_CLOUD_PROJECT}
    location: ${GOOGLE_CLOUD_LOCATION}
    rag_corpus_name: adk-agent-memory
    session_bucket_name: ${GOOGLE_CLOUD_PROJECT}-adk-sessions
```

## Usage

### Local Development

1. **Run with memory enabled**:
   ```bash
   export VERTEX_AI_ENABLED=true
   python web_interface.py
   ```

2. **Test memory functionality**:
   - Start a conversation and provide ICP information
   - End the session
   - Start a new conversation and ask about previous ICPs
   - The agent should recall information from the previous session

### Cloud Run Deployment

The deployment script handles all VertexAI setup automatically:
```bash
./deploy-cloud-run.sh
```

### Memory-Enhanced Conversations

With VertexAI memory enabled, agents can:

1. **Remember Previous ICPs**:
   ```
   User: "What ICPs have we created before?"
   Agent: *Retrieves and summarizes previous ICP definitions*
   ```

2. **Build on Past Research**:
   ```
   User: "Use the research we did last week on SaaS companies"
   Agent: *Recalls previous research and builds upon it*
   ```

3. **Track Prospect History**:
   ```
   User: "Which prospects did we identify for the fintech ICP?"
   Agent: *Retrieves previously identified prospects*
   ```

## Architecture

### Memory Flow

1. **Query Processing**:
   - User message → Memory query for relevant context
   - Enhanced message with memory context → Agent processing
   - Response generation

2. **Memory Ingestion**:
   - After each interaction, the conversation is ingested into memory
   - Metadata includes agent name, timestamp, and user ID

3. **Session Management**:
   - Sessions are persisted to Cloud Storage
   - Each user has isolated memory space
   - Sessions can be resumed across different instances

### Components

- **VertexMemoryManager**: Main class managing memory and session services
- **RAG Corpus**: Stores and indexes conversation memories
- **Cloud Storage**: Persists session state
- **ADK Agents**: Enhanced with memory-aware instructions

## Best Practices

1. **Memory Hygiene**:
   - Periodically review and clean old memories
   - Use meaningful session IDs for easier tracking

2. **Cost Management**:
   - Monitor RAG corpus usage
   - Set appropriate TTLs for cached results
   - Use memory queries judiciously

3. **Privacy**:
   - Each user's memories are isolated
   - Implement data retention policies
   - Consider GDPR compliance for user data

## Troubleshooting

### Common Issues

1. **Permission Denied**:
   - Ensure service account has correct IAM roles
   - Check if APIs are enabled

2. **Memory Not Working**:
   - Verify `VERTEX_AI_ENABLED=true` is set
   - Check logs for initialization errors
   - Ensure bucket exists and is accessible

3. **Slow Performance**:
   - Memory queries add latency
   - Consider reducing `similarity_top_k`
   - Enable caching for frequent queries

### Debug Commands

```bash
# Check service account permissions
gcloud projects get-iam-policy bayram-adk-hack \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:adk-agent-memory@bayram-adk-hack.iam.gserviceaccount.com"

# Verify bucket access
gsutil ls gs://bayram-adk-hack-adk-sessions/

# Check Vertex AI setup
gcloud ai models list --region=us-central1
```

## Advanced Configuration

### Custom RAG Corpus

To use an existing RAG corpus:
```yaml
vertexai:
    rag_corpus_id: "your-existing-corpus-id"
```

### Memory Parameters

Tune memory behavior:
```yaml
vertexai:
    memory_chunk_size: 1000      # Size of text chunks
    memory_overlap: 200          # Overlap between chunks
    similarity_top_k: 5          # Number of memories to retrieve
```

### Multi-Region Setup

For global deployment:
1. Create buckets in multiple regions
2. Use regional Vertex AI endpoints
3. Configure region-based routing

## Monitoring

### Metrics to Track

1. **Memory Query Latency**
2. **Ingestion Success Rate**
3. **Storage Usage**
4. **API Call Volume**

### Logging

Enable detailed logging:
```python
import structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

## Future Enhancements

1. **Memory Summarization**: Periodically summarize old memories
2. **Memory Scoring**: Weight memories by relevance and recency
3. **Cross-Agent Memory**: Share memories between agents
4. **Memory Export**: Allow users to export their conversation history

## Support

For issues or questions:
1. Check the logs in Cloud Console
2. Review the [Google ADK documentation](https://google.github.io/adk-docs/)
3. Contact your system administrator