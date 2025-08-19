import requests
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from langchain_openai import ChatOpenAI

class FanvueAutoResponder:
    def __init__(self, api_key: str, llm_config: dict):
        """
        Initialize the Fanvue Auto Responder
        
        Args:
            api_key: Fanvue API key
            llm_config: Dictionary containing LLM configuration
        """
        self.api_key = api_key
        self.headers = {
            "X-Fanvue-API-Key": api_key,
            "X-Fanvue-API-Version": "2025-06-26"
        }
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            openai_api_key=llm_config["api_key"],
            model_name=llm_config["model"],
            openai_api_base=llm_config["base_url"],
            temperature=llm_config["temperature"]
        )
        
        # Storage for tracking message states
        self.last_message_timestamps: Dict[str, str] = {}
        self.processed_messages: Set[str] = set()
        self.state_file = "message_state.json"
        
        # Load previous state
        self.load_state()
        
        print("✅ Fanvue Auto Responder initialized successfully!")

    def load_state(self):
        """Load previous message state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.last_message_timestamps = data.get('last_timestamps', {})
                    self.processed_messages = set(data.get('processed_messages', []))
                print(f"📁 Loaded state for {len(self.last_message_timestamps)} subscribers")
        except Exception as e:
            print(f"⚠️  Could not load previous state: {e}")

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
            print(f"⚠️  Could not save state: {e}")

    def get_current_user(self) -> dict:
        """Get current user information"""
        try:
            response = requests.get("https://api.fanvue.com/users/me", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Error getting current user: {e}")
            return {}

    def get_subscribers(self) -> List[dict]:
        """Get all subscribers"""
        try:
            all_subscribers = []
            page = 1
            
            while True:
                response = requests.get(f"https://api.fanvue.com/subscribers?page={page}", headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                subscribers = data.get("data", [])
                all_subscribers.extend(subscribers)
                
                # Check if there are more pages
                pagination = data.get("pagination", {})
                if not pagination.get("hasMore", False):
                    break
                    
                page += 1
            
            print(f"👥 Found {len(all_subscribers)} subscribers")
            return all_subscribers
            
        except Exception as e:
            print(f"❌ Error getting subscribers: {e}")
            return []

    def get_chat_messages(self, user_uuid: str, limit: int = 20) -> List[dict]:
        """Get recent messages from a chat"""
        try:
            response = requests.get(
                f"https://api.fanvue.com/chats/{user_uuid}/messages?page=1&limit={limit}", 
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            print(f"❌ Error getting messages for {user_uuid}: {e}")
            return []

    def send_message(self, user_uuid: str, text: str) -> bool:
        """Send a message to a user"""
        try:
            response = requests.post(
                f"https://api.fanvue.com/chats/{user_uuid}/message",
                headers=self.headers,
                json={"text": text}
            )
            response.raise_for_status()
            print(f"📤 Sent message to {user_uuid}")
            return True
        except Exception as e:
            print(f"❌ Error sending message to {user_uuid}: {e}")
            return False

    def generate_response(self, user_message: str, user_handle: str, context: str = "") -> str:
        """Generate an AI response to a user message"""
        try:
            prompt = f"""You are responding to a message from a subscriber named {user_handle} on Fanvue (a creator platform).

Recent message from {user_handle}: "{user_message}"

Context: {context}

Generate a friendly, engaging, and personalized response that:
- Acknowledges their message
- Shows genuine interest in them
- Keeps the conversation going
- Maintains a warm but professional tone
- Is concise (1-3 sentences)

Response:"""

            response = self.llm.invoke(prompt)
            return response.content.strip()
            
        except Exception as e:
            print(f"❌ Error generating AI response: {e}")
            return f"Thank you for your message, {user_handle}! I appreciate you reaching out. How are you doing today? 💕"

    def check_for_new_messages(self, subscriber: dict) -> List[dict]:
        """Check for new messages from a subscriber that need responses"""
        user_uuid = subscriber["uuid"]
        user_handle = subscriber.get("handle", "Unknown")
        
        # Get recent messages
        messages = self.get_chat_messages(user_uuid, limit=20)
        
        if not messages:
            return []

        # Sort messages by timestamp (newest first)
        messages.sort(key=lambda x: x.get('sentAt', ''), reverse=True)
        
        current_user = self.get_current_user()
        my_uuid = current_user.get("uuid", "")
        
        # Find the most recent message from the subscriber that doesn't have a response yet
        unanswered_messages = []
        
        # Look for consecutive messages from the subscriber at the top (most recent)
        for message in messages:
            sender_uuid = message.get("sender", {}).get("uuid", "")
            message_id = message.get("uuid", "")
            
            # If this is our message, stop looking (they already got a response)
            if sender_uuid == my_uuid:
                break
                
            # If this is from the subscriber and we haven't processed it
            if sender_uuid != my_uuid and message_id not in self.processed_messages:
                unanswered_messages.append(message)
            else:
                # If we've already processed this message, stop
                break
        
        # Reverse to get chronological order (oldest unanswered first)
        unanswered_messages.reverse()
        
        # Mark these messages as processed
        for message in unanswered_messages:
            self.processed_messages.add(message.get("uuid", ""))
        
        # Update last timestamp with the newest message timestamp
        if messages:
            newest_timestamp = max(msg.get("sentAt", "") for msg in messages)
            self.last_message_timestamps[user_uuid] = newest_timestamp
        
        if unanswered_messages:
            print(f"💬 Found {len(unanswered_messages)} unanswered message(s) from {user_handle}")
        
        return unanswered_messages

    def respond_to_messages(self, subscriber: dict, unanswered_messages: List[dict]):
        """Generate and send responses to unanswered messages"""
        user_uuid = subscriber["uuid"]
        user_handle = subscriber.get("handle", "Unknown")
        
        if not unanswered_messages:
            return
        
        # If there are multiple unanswered messages, combine them for context
        if len(unanswered_messages) > 1:
            # Get the most recent message to respond to
            latest_message = unanswered_messages[-1]
            message_text = latest_message.get("text", "")
            
            # Create context from previous messages
            context_messages = [msg.get("text", "") for msg in unanswered_messages[:-1]]
            context = f"Previous messages: {' | '.join(context_messages)}" if context_messages else ""
            
            print(f"📨 Multiple messages from {user_handle}. Latest: \"{message_text}\"")
            
            # Generate AI response with context
            response_text = self.generate_response(message_text, user_handle, context)
            print(f"🤖 Generated response: \"{response_text}\"")
            
            # Send one response addressing the latest message
            if self.send_message(user_uuid, response_text):
                print(f"✅ Successfully responded to {user_handle} (addressed {len(unanswered_messages)} messages)")
            else:
                print(f"❌ Failed to respond to {user_handle}")
        
        else:
            # Single message - respond normally
            message = unanswered_messages[0]
            message_text = message.get("text", "")
            
            if not message_text:
                return
            
            print(f"📨 New message from {user_handle}: \"{message_text}\"")
            
            # Generate AI response
            response_text = self.generate_response(message_text, user_handle)
            print(f"🤖 Generated response: \"{response_text}\"")
            
            # Send the response
            if self.send_message(user_uuid, response_text):
                print(f"✅ Successfully responded to {user_handle}")
            else:
                print(f"❌ Failed to respond to {user_handle}")
        
        # Small delay to avoid rate limiting
        time.sleep(2)

    def monitor_and_respond(self, check_interval: int = 60):
        """Main monitoring loop"""
        print(f"🔄 Starting message monitoring (checking every {check_interval} seconds)")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Checking for new messages...")
                
                # Get all subscribers
                subscribers = self.get_subscribers()
                
                if not subscribers:
                    print("No subscribers found, waiting...")
                    time.sleep(check_interval)
                    continue
                
                new_message_count = 0
                
                # Check each subscriber for new messages
                for subscriber in subscribers:
                    try:
                        new_messages = self.check_for_new_messages(subscriber)
                        
                        if new_messages:
                            new_message_count += len(new_messages)
                            self.respond_to_messages(subscriber, new_messages)
                            
                    except Exception as e:
                        print(f"❌ Error processing subscriber {subscriber.get('handle', 'Unknown')}: {e}")
                        continue
                
                # Save state after each check
                self.save_state()
                
                if new_message_count > 0:
                    print(f"✅ Processed {new_message_count} new message(s)")
                else:
                    print("📭 No new messages found")
                
                print(f"😴 Waiting {check_interval} seconds until next check...")
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
            self.save_state()
            print("💾 State saved successfully")

def main():
    """Main function to start the auto responder"""
    
    # Configuration
    FANVUE_API_KEY = "fvak_19a03e89bb7a18aca0450dcaa7d20cc3165784e87c4fe4496d04f9820e372e4c_740795"
    
    LLM_CONFIG = {
        "api_key": "SHHHNXH43KX5AF986LR7WEPFFILV6OKKKIT4NVSF",
        "model": "Sao10K/L3-8B-Stheno-v3.2",
        "base_url": "https://c40shf7xpyl0ky-8000.proxy.runpod.net/v1",
        "temperature": 0.5
    }
    
    # Initialize and start the responder
    responder = FanvueAutoResponder(FANVUE_API_KEY, LLM_CONFIG)
    
    # Start monitoring (check every 60 seconds)
    responder.monitor_and_respond(check_interval=60)

if __name__ == "__main__":
    main()
