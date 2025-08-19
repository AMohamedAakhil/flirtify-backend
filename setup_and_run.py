#!/usr/bin/env python3
"""
Setup and run script for Fanvue Auto Responder
"""

import subprocess
import sys
import os

def install_dependencies():
    """Install required dependencies"""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def main():
    """Main setup and run function"""
    print("🚀 Fanvue Auto Responder Setup")
    print("=" * 40)
    
    # Check if requirements.txt exists
    if not os.path.exists("requirements.txt"):
        print("❌ requirements.txt not found!")
        return
    
    # Install dependencies
    if not install_dependencies():
        return
    
    print("\n" + "=" * 40)
    print("🎯 Setup complete!")
    print("\nTo start the auto responder, run:")
    print("python fanvue_auto_responder.py")
    print("\nOr import and use the FanvueAutoResponder class in your own code.")
    print("\n⚠️  Make sure to update your API keys in the script before running!")

if __name__ == "__main__":
    main()
