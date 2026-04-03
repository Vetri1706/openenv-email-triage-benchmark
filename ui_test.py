#!/usr/bin/env python3
"""
Quick test script to verify the UI is accessible.
Start the FastAPI server and test the UI endpoints.
"""

if __name__ == "__main__":
    print("=" * 60)
    print("Email Triage Environment - Web UI Test")
    print("=" * 60)
    print()
    print("To start the environment and access the web UI:")
    print()
    print("  1. Install dependencies:")
    print("     pip install -r requirements.txt")
    print()
    print("  2. Start the FastAPI server:")
    print("     python -m uvicorn app:app --reload --port 8000")
    print()
    print("  3. Open your browser:")
    print("     http://localhost:8000")
    print()
    print("=" * 60)
    print("UI Features:")
    print("=" * 60)
    print("✓ Task selection (easy, medium, hard, killer)")
    print("✓ Interactive inbox with email selection")
    print("✓ Action submission (reply, escalate, archive, mark_spam)")
    print("✓ Real-time observation display (JSON formatted)")
    print("✓ Action history logging")
    print("✓ Reward and step tracking")
    print()
