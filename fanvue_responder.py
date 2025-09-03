import requests
import json
import os
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from database import FanvueAccount, DatabaseManager

class EnhancedFanvueAutoResponder:
    def __init__(self, account: FanvueAccount, llm_config: dict, db_manager: DatabaseManager):
        """
        Initialize the Enhanced Fanvue Auto Responder for a specific account
        
        Args:
            account: FanvueAccount object containing API key and system prompt
            llm_config: Dictionary containing LLM configuration
            db_manager: DatabaseManager instance for fetching latest account settings
        """
        self.account = account
        self.api_key = account.api_key
        self.system_prompt = account.system_prompt or self.get_default_system_prompt()
        
        self.headers = {
            "X-Fanvue-API-Key": self.api_key,
            "X-Fanvue-API-Version": "2025-06-26"
        }
        
        # LLM configuration and database manager
        self.llm_config = llm_config
        self.db_manager = db_manager
        
        # Storage for tracking message states
        self.last_message_timestamps: Dict[str, str] = {}
        self.processed_messages: Set[str] = set()
        self.state_file = f"message_state_{account.id}.json"
        
        # Load previous state
        self.load_state()
        
        # Clean up old processed messages (keep only recent ones to prevent memory bloat)
        self.cleanup_old_processed_messages()
        
        print(f"✅ Enhanced Auto Responder initialized for account {account.id}")

    def get_default_system_prompt(self) -> str:
        """Get default system prompt if none provided"""
        return """You are responding to messages from subscribers on Fanvue (a creator platform).

Generate friendly, engaging, and personalized responses that:
- Acknowledge their message
- Show genuine interest in them  
- Keep the conversation going
- Maintain a warm but professional tone
- Are concise (1-3 sentences)

Be authentic, flirty when appropriate, and make each subscriber feel special."""

    def load_state(self):
        """Load previous message state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.last_message_timestamps = data.get('last_timestamps', {})
                    self.processed_messages = set(data.get('processed_messages', []))
                print(f"📁 Loaded state for {len(self.last_message_timestamps)} subscribers (Account: {self.account.id})")
        except Exception as e:
            print(f"⚠️  Could not load previous state for account {self.account.id}: {e}")

    def cleanup_old_processed_messages(self):
        """Clean up old processed messages to prevent memory bloat (keep last 1000)"""
        try:
            if len(self.processed_messages) > 1000:
                # Convert to list, sort, and keep only the most recent 1000
                # Since message IDs are UUIDs, we can't sort by them meaningfully
                # So we'll just keep a random subset of 1000
                processed_list = list(self.processed_messages)
                # Keep the last 1000 (assuming they were added in chronological order)
                self.processed_messages = set(processed_list[-1000:])
                print(f"🧹 Cleaned up old processed messages, kept {len(self.processed_messages)} recent ones (Account: {self.account.id})")
        except Exception as e:
            print(f"⚠️  Error cleaning up processed messages for account {self.account.id}: {e}")

    def save_state(self):
        """Save current message state to file"""
        try:
            data = {
                'last_timestamps': self.last_message_timestamps,
                'processed_messages': list(self.processed_messages)
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"💾 Saved state: {len(self.processed_messages)} processed messages, {len(self.last_message_timestamps)} timestamps (Account: {self.account.id})")
        except Exception as e:
            print(f"⚠️  Could not save state for account {self.account.id}: {e}")

    async def get_current_user(self) -> dict:
        """Get current user information"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.get("https://api.fanvue.com/users/me", headers=self.headers)
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Error getting current user for account {self.account.id}: {e}")
            return {}

    async def get_subscribers(self) -> List[dict]:
        """Get all subscribers with rate limit handling"""
        try:
            all_subscribers = []
            page = 1
            loop = asyncio.get_event_loop()
            
            while True:
                try:
                    response = await loop.run_in_executor(
                        None,
                        lambda p=page: requests.get(f"https://api.fanvue.com/subscribers?page={p}", headers=self.headers)
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    subscribers = data.get("data", [])
                    all_subscribers.extend(subscribers)
                    
                    # Check if there are more pages
                    pagination = data.get("pagination", {})
                    if not pagination.get("hasMore", False):
                        break
                        
                    page += 1
                    
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        print(f"⏳ Rate limit hit for account {self.account.id}, waiting 60 seconds...")
                        await asyncio.sleep(60)
                        continue  # Retry the same page
                    else:
                        raise  # Re-raise non-429 errors
            
            print(f"👥 Found {len(all_subscribers)} subscribers (Account: {self.account.id})")
            return all_subscribers
            
        except Exception as e:
            print(f"❌ Error getting subscribers for account {self.account.id}: {e}")
            return []

    async def get_chat_messages(self, user_uuid: str, limit: int = 20) -> List[dict]:
        """Get recent messages from a chat with rate limit handling"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(
                        f"https://api.fanvue.com/chats/{user_uuid}/messages?page=1&limit={limit}", 
                        headers=self.headers
                    )
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    retry_count += 1
                    print(f"⏳ Rate limit hit getting messages for {user_uuid} (Account: {self.account.id}), waiting 60 seconds... (Retry {retry_count}/{max_retries})")
                    await asyncio.sleep(60)
                    continue
                else:
                    print(f"❌ Error getting messages for {user_uuid} (Account: {self.account.id}): {e}")
                    return []
            except Exception as e:
                print(f"❌ Error getting messages for {user_uuid} (Account: {self.account.id}): {e}")
                return []
        
        print(f"❌ Max retries exceeded for getting messages for {user_uuid} (Account: {self.account.id})")
        return []

    async def send_message(self, user_uuid: str, text: str) -> bool:
        """Send a message to a user with rate limit handling"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        f"https://api.fanvue.com/chats/{user_uuid}/message",
                        headers=self.headers,
                        json={"text": text}
                    )
                )
                response.raise_for_status()
                print(f"📤 Sent message to {user_uuid} (Account: {self.account.id})")
                return True
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    retry_count += 1
                    print(f"⏳ Rate limit hit sending message to {user_uuid} (Account: {self.account.id}), waiting 60 seconds... (Retry {retry_count}/{max_retries})")
                    await asyncio.sleep(60)
                    continue
                else:
                    print(f"❌ Error sending message to {user_uuid} (Account: {self.account.id}): {e}")
                    return False
            except Exception as e:
                print(f"❌ Error sending message to {user_uuid} (Account: {self.account.id}): {e}")
                return False
        
        print(f"❌ Max retries exceeded for sending message to {user_uuid} (Account: {self.account.id})")
        return False

    async def build_conversation_context(self, chat_history: List[dict], user_handle: str) -> str:
        """Build conversation context from chat history"""
        try:
            if not chat_history:
                return "This is the start of your conversation."
            
            # Get current user info to identify our messages
            current_user = await self.get_current_user()
            my_uuid = current_user.get("uuid", "")
            
            # Sort messages by timestamp (oldest first)
            sorted_messages = sorted(chat_history, key=lambda x: x.get("sentAt", ""))
            
            # Build conversation context (limit to last 20 messages to avoid token limits)
            conversation_lines = []
            recent_messages = sorted_messages[-20:] if len(sorted_messages) > 20 else sorted_messages
            
            for msg in recent_messages:
                sender_uuid = msg.get("sender", {}).get("uuid", "")
                text = msg.get("text", "").strip()
                timestamp = msg.get("sentAt", "")
                
                if not text:
                    continue
                
                if sender_uuid == my_uuid:
                    conversation_lines.append(f"You: {text}")
                else:
                    conversation_lines.append(f"{user_handle}: {text}")
            
            if conversation_lines:
                context = f"Conversation history:\n" + "\n".join(conversation_lines)
                return context
            else:
                return "This is the start of your conversation."
                
        except Exception as e:
            print(f"⚠️ Error building conversation context for account {self.account.id}: {e}")
            return "Previous conversation context unavailable."

    async def generate_response_with_llm(self, user_message: str, user_handle: str, context: str = "") -> str:
        """Generate an AI response using either Fal AI or OpenAI API based on the model"""
        try:
            # Fetch latest account settings from database to get current LLM model
            latest_account = await self.db_manager.get_fanvue_account_by_id(self.account.id)
            
            if latest_account:
                # Use the latest LLM setting from database, otherwise use default
                model = latest_account.llm if latest_account.llm else "google/gemini-2.0-flash-001"
                # Also update system prompt if it was changed
                current_system_prompt = latest_account.system_prompt or self.get_default_system_prompt()
            else:
                # Fallback to cached account data if database fetch fails
                model = self.account.llm if self.account.llm else "google/gemini-2.0-flash-001"
                current_system_prompt = self.system_prompt
                print(f"⚠️ Could not fetch latest account settings, using cached data (Account: {self.account.id})")
            
            print(f"🤖 Using LLM model: {model} (Account: {self.account.id})")
            
            # Prepare the prompt using the conversation context
            if context and context != "This is the start of your conversation.":
                user_prompt = f"""{context}

{user_handle}'s latest message: "{user_message}"

Please respond naturally as if continuing this conversation:"""
            else:
                user_prompt = f"""This is the start of your conversation with {user_handle}.

{user_handle} just sent: "{user_message}"

Please respond in a friendly, engaging way:"""

            # Check if we should use stheno-nsfw (OpenAI API) or Fal AI
            if model == "stheno-nsfw":
                return await self.generate_response_with_openai(user_prompt, current_system_prompt)
            else:
                return await self.generate_response_with_fal_ai(user_prompt, current_system_prompt, model)
            
        except Exception as e:
            print(f"❌ Error generating AI response for account {self.account.id}: {e}")
            return f"Thank you for your message, {user_handle}! I appreciate you reaching out. How are you doing today? 💕"

    async def generate_response_with_openai(self, user_prompt: str, system_prompt: str) -> str:
        """Generate response using OpenAI API for stheno-nsfw model"""
        try:
            stheno_config = self.llm_config.get("stheno_nsfw", {})
            
            headers = {
                "Authorization": f"Bearer {stheno_config['api_key']}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": stheno_config["model"],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 150,
                "temperature": 0.8
            }
            
            loop = asyncio.get_event_loop()
            
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    f"{stheno_config['base_url']}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
            )
            response.raise_for_status()
            
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            else:
                raise Exception("No response content from stheno-nsfw API")
                
        except Exception as e:
            print(f"❌ Error with stheno-nsfw API for account {self.account.id}: {e}")
            raise

    async def generate_response_with_fal_ai(self, user_prompt: str, system_prompt: str, model: str) -> str:
        """Generate response using Fal AI API"""
        try:
            # Prepare the request to Fal AI
            fal_headers = {
                "Authorization": f"Key {self.llm_config['fal_api_key']}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "prompt": user_prompt,
                "system_prompt": system_prompt,
                "model": model,
                "reasoning": False
            }
            
            loop = asyncio.get_event_loop()
            
            # Submit request to Fal AI queue
            submit_response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    "https://queue.fal.run/fal-ai/any-llm",
                    headers=fal_headers,
                    json=payload,
                    timeout=30
                )
            )
            submit_response.raise_for_status()
            
            submit_result = submit_response.json()
            request_id = submit_result["request_id"]
            
            # Poll for completion
            max_wait_time = 60  # Maximum wait time in seconds
            poll_interval = 2   # Poll every 2 seconds
            waited_time = 0
            
            while waited_time < max_wait_time:
                status_response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(
                        f"https://queue.fal.run/fal-ai/any-llm/requests/{request_id}/status",
                        headers=fal_headers,
                        timeout=10
                    )
                )
                status_response.raise_for_status()
                status_result = status_response.json()
                
                if status_result["status"] == "COMPLETED":
                    # Get the final result
                    result_response = await loop.run_in_executor(
                        None,
                        lambda: requests.get(
                            f"https://queue.fal.run/fal-ai/any-llm/requests/{request_id}",
                            headers=fal_headers,
                            timeout=10
                        )
                    )
                    result_response.raise_for_status()
                    final_result = result_response.json()
                    
                    if final_result.get("error"):
                        raise Exception(f"Fal AI error: {final_result['error']}")
                    
                    return final_result["output"].strip()
                
                elif status_result["status"] == "FAILED":
                    raise Exception("Fal AI request failed")
                
                # Wait before polling again
                await asyncio.sleep(poll_interval)
                waited_time += poll_interval
            
            # If we reach here, the request timed out
            raise Exception("Fal AI request timed out")
            
        except Exception as e:
            print(f"❌ Error with Fal AI for account {self.account.id}: {e}")
            raise

    async def check_for_unanswered_messages(self, subscriber: dict) -> List[dict]:
        """Check for unanswered messages from a subscriber"""
        user_uuid = subscriber["uuid"]
        user_handle = subscriber.get("handle", "Unknown")
        
        # Get recent messages
        messages = await self.get_chat_messages(user_uuid, limit=20)
        
        if not messages:
            return []

        # Filter for unanswered messages from the subscriber
        current_user = await self.get_current_user()
        my_uuid = current_user.get("uuid", "")
        
        # Sort messages by timestamp to process in chronological order
        messages.sort(key=lambda x: x.get("sentAt", ""))
        
        # CRITICAL: Check if the most recent message is from us
        # If so, don't respond until the subscriber sends a new message
        if messages:
            most_recent_message = messages[-1]  # Last message after sorting
            most_recent_sender = most_recent_message.get("sender", {}).get("uuid", "")
            
            if most_recent_sender == my_uuid:
                print(f"🔇 Last message in conversation with {user_handle} is from us, skipping response (Account: {self.account.id})")
                return []
        
        # Get the last timestamp we processed for this user
        last_processed_timestamp = self.last_message_timestamps.get(user_uuid, "")
        
        unanswered_messages = []
        new_subscriber_messages = []
        
        # First, collect only NEW messages from the subscriber (messages we haven't seen before)
        for message in messages:
            message_id = message.get("uuid", "")
            sender_uuid = message.get("sender", {}).get("uuid", "")
            message_timestamp = message.get("sentAt", "")
            message_text = message.get("text", "").strip()
            
            # Skip if it's our own message, empty message, or already processed
            if sender_uuid == my_uuid or not message_text or message_id in self.processed_messages:
                continue
            
            # Skip if this message is older than or equal to our last processed timestamp
            if last_processed_timestamp and message_timestamp <= last_processed_timestamp:
                continue
                
            # This is a new message from the subscriber
            new_subscriber_messages.append(message)
            print(f"📥 New message from {user_handle} (timestamp: {message_timestamp}): \"{message_text[:50]}...\" (Account: {self.account.id})")
        
        # Only respond to the most recent NEW message from the subscriber to avoid spam
        # This ensures we respond once per "conversation turn" from the subscriber
        if new_subscriber_messages:
            # Sort by timestamp and take only the most recent message
            new_subscriber_messages.sort(key=lambda x: x.get("sentAt", ""))
            latest_new_message = new_subscriber_messages[-1]
            
            # Mark this message as processed
            message_id = latest_new_message.get("uuid", "")
            self.processed_messages.add(message_id)
            
            unanswered_messages = [latest_new_message]
            print(f"✅ Will respond to latest new message from {user_handle} (Account: {self.account.id})")
        else:
            print(f"ℹ️ No new messages from {user_handle} to respond to (Account: {self.account.id})")
        
        # Update last timestamp with the newest message timestamp (including our own messages)
        if messages:
            newest_timestamp = max(msg.get("sentAt", "") for msg in messages)
            self.last_message_timestamps[user_uuid] = newest_timestamp
        
        return unanswered_messages

    async def respond_to_messages(self, subscriber: dict, new_messages: List[dict]):
        """Generate and send responses to new messages"""
        user_uuid = subscriber["uuid"]
        user_handle = subscriber.get("handle", "Unknown")
        
        # Get chat history for context
        chat_history = await self.get_chat_messages(user_uuid, limit=50)  # Get more history for context
        
        for message in new_messages:
            message_text = message.get("text", "")
            
            if not message_text:
                continue
            
            print(f"📨 New message from {user_handle}: \"{message_text}\" (Account: {self.account.id})")
            
            # Build conversation context from chat history
            conversation_context = await self.build_conversation_context(chat_history, user_handle)
            
            # Generate AI response with full conversation context
            response_text = await self.generate_response_with_llm(message_text, user_handle, conversation_context)
            print(f"🤖 Generated response: \"{response_text}\" (Account: {self.account.id})")
            
            # Send the response
            if await self.send_message(user_uuid, response_text):
                print(f"✅ Successfully responded to {user_handle} (Account: {self.account.id})")
            else:
                print(f"❌ Failed to respond to {user_handle} (Account: {self.account.id})")
            
            # Small delay between responses to avoid rate limiting
            await asyncio.sleep(1)

    async def monitor_single_cycle(self) -> int:
        """Single monitoring cycle - returns number of unanswered messages processed"""
        try:
            # Get all subscribers
            subscribers = await self.get_subscribers()
            
            if not subscribers:
                return 0
            
            unanswered_message_count = 0
            
            # Check each subscriber for unanswered messages
            for subscriber in subscribers:
                try:
                    unanswered_messages = await self.check_for_unanswered_messages(subscriber)
                    
                    if unanswered_messages:
                        unanswered_message_count += len(unanswered_messages)
                        await self.respond_to_messages(subscriber, unanswered_messages)
                        
                except Exception as e:
                    print(f"❌ Error processing subscriber {subscriber.get('handle', 'Unknown')} (Account: {self.account.id}): {e}")
                    continue
            
            # Save state after each check
            self.save_state()
            
            return unanswered_message_count
            
        except Exception as e:
            print(f"❌ Error in monitoring cycle for account {self.account.id}: {e}")
            return 0
