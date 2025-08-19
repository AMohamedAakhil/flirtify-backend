import requests
import json
import os
from datetime import datetime

# === CONFIGURATION ===
API_KEY = "fvak_19a03e89bb7a18aca0450dcaa7d20cc3165784e87c4fe4496d04f9820e372e4c_740795"
HEADERS = {
    "X-Fanvue-API-Key": API_KEY,
    "X-Fanvue-API-Version": "2025-06-26"
}

# === FUNCTION: Get Current User Info ===
def get_current_user():
    """
    Fetches and prints the current user's UUID, email, and handle.
    """
    response = requests.get("https://api.fanvue.com/users/me", headers=HEADERS)
    data = response.json()

    print("\n[Current User Info]")
    print(f"UUID: {data['uuid']}")
    print(f"Email: {data['email']}")
    print(f"Handle: {data['handle']}")
    
    return data

# === FUNCTION: Get Subscribers ===
def get_subscribers():
    """
    Fetches and prints subscriber info.
    """
    response = requests.get("https://api.fanvue.com/subscribers?page=1", headers=HEADERS)
    data = response.json()
    print("\n[Subscribers]")
    for sub in data["data"]:
        print(f"UUID: {sub['uuid']}, Handle: {sub['handle']}, Display Name: {sub.get('displayName')}")
    return data["data"]

# === FUNCTION: Fetch All Messages with Pagination ===
def get_all_messages(user_uuid):
    """
    Retrieves all messages from a chat with pagination.
    """
    all_messages = []
    page = 1
    while True:
        url = f"https://api.fanvue.com/chats/{user_uuid}/messages?page={page}"
        response = requests.get(url, headers=HEADERS)
        result = response.json()
        messages = result.get("data", [])
        all_messages.extend(messages)
        if not result.get("pagination", {}).get("hasMore", False):
            break
        page += 1
    return all_messages

# === FUNCTION: Save Messages to File ===
def save_messages_to_file(user_uuid, messages):
    """
    Saves message data to a JSON file.
    """
    os.makedirs("messages", exist_ok=True)
    with open(f"messages/{user_uuid}.json", "w") as f:
        json.dump(messages, f, indent=2)

# === FUNCTION: Save UUIDs to File ===
def save_uuids_to_file(uuids):
    with open("uuids.txt", "w") as f:
        for uuid in uuids:
            f.write(uuid + "\n")

# === FUNCTION: Send Message ===
def send_message(user_uuid, text="Hey there! Just checking in via the API 😊"):
    """
    Sends a text message to the given user.
    """
    url = f"https://api.fanvue.com/chats/{user_uuid}/message"
    response = requests.post(url, headers=HEADERS, json={"text": text})
    print(f"\n[Sent Message to {user_uuid}] Response: {response.json()}")
    return response.json()

# === FUNCTION: Get Oldest Message ===
def get_oldest_message(messages):
    """
    Returns the oldest message from the list.
    """
    return min(messages, key=lambda m: m.get('sentAt', '9999')) if messages else None

# === FUNCTION: Get Newest Message ===
def get_newest_message(messages):
    """
    Returns the newest message from the list.
    """
    return max(messages, key=lambda m: m.get('sentAt', '0000')) if messages else None

# === FUNCTION: Print Message Summary ===
def print_message_summary(message, label):
    """
    Prints out a message with sender, recipient, and time.
    """
    if message:
        print(f"{label} Message:")
        print(f"  Sent At : {message.get('sentAt')}")
        print(f"  Text    : {message.get('text')}")
        print(f"  From    : {message['sender'].get('handle')}")
        print(f"  To      : {message['recipient'].get('handle')}")
    else:
        print(f"{label} Message: No messages found.")

# === MAIN FLOW ===

# Step 1: Get current user
current_user = get_current_user()

# Step 2: Get subscribers
subscribers = get_subscribers()
if not subscribers:
    print("No subscribers found.")
    exit()

# Use only the first subscriber
first_sub = subscribers[0]
user_uuid = first_sub["uuid"]
all_uuids = [user_uuid]
save_uuids_to_file(all_uuids)

# Step 3: Fetch all messages from the first subscriber chat
messages = get_all_messages(user_uuid)
save_messages_to_file(user_uuid, messages)

# Step 4: Find and print oldest/newest messages
oldest = get_oldest_message(messages)
newest = get_newest_message(messages)

print(f"\n[Messages with {first_sub['handle']}]")
print_message_summary(oldest, "Oldest")
print_message_summary(newest, "Newest")

# Step 5: Send a message
send_message(user_uuid, "This is a test message from the Fanvue API!")

# Step 6: Re-fetch and show newest message
updated_messages = get_all_messages(user_uuid)
newest_after = get_newest_message(updated_messages)

print(f"\n[Newest Message After Sending]")
print_message_summary(newest_after, "Newest")

# Step 7: Total message count
print(f"\n[Total Messages with {first_sub['handle']}]: {len(updated_messages)}")