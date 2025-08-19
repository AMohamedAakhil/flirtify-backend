# Multi-Account Fanvue Auto Responder System

An advanced auto-responder system that manages multiple Fanvue accounts simultaneously, each with custom AI personalities and system prompts stored in a PostgreSQL database.

## Features

- 🔀 **Multi-Account Support**: Monitors unlimited Fanvue accounts concurrently
- 🗄️ **Database-Driven**: Automatically loads accounts from PostgreSQL database  
- 🎭 **Custom AI Personalities**: Each account uses its own system prompt for personalized responses
- ⚡ **Continuous Monitoring**: Checks for new messages instantly without delays
- 🔍 **Auto-Discovery**: Automatically detects new accounts added to database
- 🛡️ **Graceful Shutdown**: Handles interruptions properly and saves state
- 🔄 **Error Recovery**: Continues running even if individual accounts encounter errors
- 💾 **State Persistence**: Tracks which messages have been processed to avoid duplicates
- 📊 **Comprehensive Logging**: Detailed console output for monitoring all account activity

## Database Schema

The system expects a `FanvueAccount` table with this structure:

```sql
CREATE TABLE "FanvueAccount" (
    id String PRIMARY KEY DEFAULT cuid(),
    "apiKey" String UNIQUE NOT NULL,
    "systemPrompt" String,
    "expiresAt" TIMESTAMP NOT NULL,
    "createdAt" TIMESTAMP DEFAULT NOW(),
    "updatedAt" TIMESTAMP DEFAULT NOW(),
    "userId" String NOT NULL
);
```

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Database**:
   - Update `DATABASE_URL` in `database.py` with your PostgreSQL connection string
   - Ensure your database contains the `FanvueAccount` table with active accounts

3. **Update LLM Configuration**:
   - Edit `LLM_CONFIG` in `multi_account_manager.py` with your AI service details

4. **Run the Multi-Account System**:
   ```bash
   python run_multi_account_system.py
   ```

## How It Works

1. **Database Connection**: Connects to PostgreSQL and loads all active accounts
2. **Account Monitoring**: Creates separate monitoring tasks for each account
3. **Message Processing**: 
   - Checks for new messages continuously (no delays)
   - Uses account-specific system prompt for AI responses
   - Sends personalized replies using the account's API key
4. **State Management**: Tracks processed messages to avoid duplicates
5. **Auto-Refresh**: Checks for new accounts every 5 minutes
6. **Smart Filtering**: Only responds to messages from subscribers (not your own messages)

## Configuration

The system is pre-configured with your provided LLM settings:
- **Model**: Sao10K/L3-8B-Stheno-v3.2
- **Base URL**: https://c40shf7xpyl0ky-8000.proxy.runpod.net/v1
- **Temperature**: 0.5

## File Structure

- `fanvue_auto_responder.py` - Main auto responder class and script
- `requirements.txt` - Python dependencies
- `setup_and_run.py` - Setup and installation script
- `message_state.json` - Persistent state file (created automatically)
- `messages/` - Directory for storing message history (from your existing code)

## Usage Example

```python
from fanvue_auto_responder import FanvueAutoResponder

# Configuration
FANVUE_API_KEY = "your_fanvue_api_key"
LLM_CONFIG = {
    "api_key": "your_llm_api_key",
    "model": "Sao10K/L3-8B-Stheno-v3.2",
    "base_url": "https://c40shf7xpyl0ky-8000.proxy.runpod.net/v1",
    "temperature": 0.5
}

# Initialize and start monitoring
responder = FanvueAutoResponder(FANVUE_API_KEY, LLM_CONFIG)
responder.monitor_and_respond(check_interval=60)  # Check every 60 seconds
```

## Safety Features

- **Duplicate Prevention**: Tracks processed messages to avoid sending multiple responses
- **Error Handling**: Graceful error handling for API failures
- **Rate Limiting**: Built-in delays between API calls
- **State Persistence**: Saves progress to prevent data loss on restart

## Stopping the System

Press `Ctrl+C` to safely stop the monitoring system. The current state will be saved automatically.

## Customization

You can customize the AI responses by modifying the prompt in the `generate_response` method. The current prompt generates:
- Friendly and engaging responses
- Personalized acknowledgments
- Conversation-continuing questions
- Professional but warm tone

## Troubleshooting

1. **API Key Issues**: Ensure your Fanvue API key is valid and has the necessary permissions
2. **LLM Connection**: Verify your LLM endpoint is accessible and credentials are correct
3. **Rate Limiting**: If you get rate limit errors, increase the `check_interval` parameter
4. **No Subscribers**: The system will wait if no subscribers are found
5. **Permission Errors**: Make sure the script has write permissions for creating state files

## Notes

- The system only responds to messages from subscribers, not your own messages
- Messages are processed in chronological order
- The AI generates contextual responses based on the subscriber's message content
- All activity is logged to the console for monitoring
