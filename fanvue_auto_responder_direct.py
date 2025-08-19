import requests
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

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
        
        # LLM configuration
        self.llm_config = llm_config
        
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

    def generate_response_with_llm(self, user_message: str, user_handle: str, context: str = "") -> str:
        """Generate an AI response using direct HTTP request to LLM"""
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
            
            response = requests.post(
                f"{self.llm_config['base_url']}/chat/completions",
                headers=llm_headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            print(f"❌ Error generating AI response: {e}")
            return f"Thank you for your message, {user_handle}! I appreciate you reaching out. How are you doing today? 💕"

    def check_for_new_messages(self, subscriber: dict) -> List[dict]:
        """Check for new messages from a subscriber"""
        user_uuid = subscriber["uuid"]
        user_handle = subscriber.get("handle", "Unknown")
        
        # Get recent messages
        messages = self.get_chat_messages(user_uuid, limit=10)
        
        if not messages:
            return []

        # Filter for new messages from the subscriber (not from us)
        current_user = self.get_current_user()
        my_uuid = current_user.get("uuid", "")
        
        new_messages = []
        last_timestamp = self.last_message_timestamps.get(user_uuid, "1970-01-01T00:00:00Z")
        
        for message in messages:
            message_id = message.get("uuid", "")
            sender_uuid = message.get("sender", {}).get("uuid", "")
            message_timestamp = message.get("sentAt", "")
            
            # Skip if it's our own message or already processed
            if sender_uuid == my_uuid or message_id in self.processed_messages:
                continue
                
            # Check if message is newer than our last recorded timestamp
            if message_timestamp > last_timestamp:
                new_messages.append(message)
                self.processed_messages.add(message_id)
        
        # Update last timestamp with the newest message timestamp
        if messages:
            newest_timestamp = max(msg.get("sentAt", "") for msg in messages)
            self.last_message_timestamps[user_uuid] = newest_timestamp
        
        if new_messages:
            print(f"💬 Found {len(new_messages)} new message(s) from {user_handle}")
        
        return new_messages

    def respond_to_messages(self, subscriber: dict, new_messages: List[dict]):
        """Generate and send responses to new messages"""
        user_uuid = subscriber["uuid"]
        user_handle = subscriber.get("handle", "Unknown")
        
        for message in new_messages:
            message_text = message.get("text", "")
            
            if not message_text:
                continue
            
            print(f"📨 New message from {user_handle}: \"{message_text}\"")
            
            # Generate AI response
            response_text = self.generate_response_with_llm(message_text, user_handle)
            print(f"🤖 Generated response: \"{response_text}\"")
            
            # Send the response
            if self.send_message(user_uuid, response_text):
                print(f"✅ Successfully responded to {user_handle}")
            else:
                print(f"❌ Failed to respond to {user_handle}")
            
            # Small delay between responses to avoid rate limiting
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
    responder.monitor_and_respond(check_interval=10)

if __name__ == "__main__":
    main()
