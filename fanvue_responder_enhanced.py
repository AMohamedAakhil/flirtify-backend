import requests
import json
import os
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from database import FanvueAccount

class EnhancedFanvueAutoResponder:
    def __init__(self, account: FanvueAccount, llm_config: dict):
        """
        Initialize the Enhanced Fanvue Auto Responder for a specific account
        
        Args:
            account: FanvueAccount object containing API key and system prompt
            llm_config: Dictionary containing LLM configuration
        """
        self.account = account
        self.api_key = account.api_key
        self.system_prompt = account.system_prompt or self.get_default_system_prompt()
        
        self.headers = {
            "X-Fanvue-API-Key": self.api_key,
            "X-Fanvue-API-Version": "2025-06-26"
        }
        
        # LLM configuration
        self.llm_config = llm_config
        
        # Storage for tracking message states
        self.last_message_timestamps: Dict[str, str] = {}
        self.processed_messages: Set[str] = set()
        self.state_file = f"message_state_{account.id}.json"
        
        # Load previous state
        self.load_state()
        
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

    def save_state(self):
        """Save current message state to file"""
        try:
            data = {
                'last_timestamps': self.last_message_timestamps,
                'processed_messages': list(self.processed_messages)
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
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

    async def generate_response_with_llm(self, user_message: str, user_handle: str, context: str = "") -> str:
        """Generate an AI response using the account's custom system prompt"""
        try:
            # Use the custom system prompt from the database
            prompt = f"""{self.system_prompt}

Recent message from {user_handle}: "{user_message}"

Context: {context}

Response:"""

            # Prepare the request to your LLM endpoint
            llm_headers = {
                "Authorization": f"Bearer {self.llm_config['api_key']}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.llm_config["model"],
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": self.llm_config["temperature"],
                "max_tokens": 150
            }
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    f"{self.llm_config['base_url']}/chat/completions",
                    headers=llm_headers,
                    json=payload,
                    timeout=30
                )
            )
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            print(f"❌ Error generating AI response for account {self.account.id}: {e}")
            return f"Thank you for your message, {user_handle}! I appreciate you reaching out. How are you doing today? 💕"

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
        
        unanswered_messages = []
        
        # Find messages from subscriber that don't have a response from us after them
        for i, message in enumerate(messages):
            message_id = message.get("uuid", "")
            sender_uuid = message.get("sender", {}).get("uuid", "")
            message_timestamp = message.get("sentAt", "")
            
            # Skip if it's our own message or already processed
            if sender_uuid == my_uuid or message_id in self.processed_messages:
                continue
            
            # Check if this subscriber message has been answered
            is_answered = False
            
            # Look for any message from us after this subscriber message
            for j in range(i + 1, len(messages)):
                later_message = messages[j]
                later_sender_uuid = later_message.get("sender", {}).get("uuid", "")
                later_timestamp = later_message.get("sentAt", "")
                
                # If we sent a message after this subscriber message, it's answered
                if later_sender_uuid == my_uuid and later_timestamp > message_timestamp:
                    is_answered = True
                    break
            
            # If not answered, add to unanswered list
            if not is_answered:
                unanswered_messages.append(message)
                self.processed_messages.add(message_id)
        
        # Update last timestamp with the newest message timestamp
        if messages:
            newest_timestamp = max(msg.get("sentAt", "") for msg in messages)
            self.last_message_timestamps[user_uuid] = newest_timestamp
        
        if unanswered_messages:
            print(f"💬 Found {len(unanswered_messages)} unanswered message(s) from {user_handle} (Account: {self.account.id})")
        
        return unanswered_messages

    async def respond_to_messages(self, subscriber: dict, new_messages: List[dict]):
        """Generate and send responses to new messages"""
        user_uuid = subscriber["uuid"]
        user_handle = subscriber.get("handle", "Unknown")
        
        for message in new_messages:
            message_text = message.get("text", "")
            
            if not message_text:
                continue
            
            print(f"📨 New message from {user_handle}: \"{message_text}\" (Account: {self.account.id})")
            
            # Generate AI response
            response_text = await self.generate_response_with_llm(message_text, user_handle)
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
