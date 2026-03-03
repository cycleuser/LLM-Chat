#!/usr/bin/env python3
"""Test script to verify mouse click and typing works with WeChat.

This script will:
1. Find the WeChat window
2. Click in the input area
3. Type test text
4. Click the send button

Run with: python tests/test_wechat_send.py
"""

import subprocess
import sys
import time

sys.path.insert(0, "src")


def find_wechat_window():
    """Find WeChat window ID."""
    # Try different search terms
    for term in ["WeChat", "微信", "wechat"]:
        result = subprocess.run(
            ["xdotool", "search", "--name", term],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            windows = result.stdout.strip().split("\n")
            print(f"Found {len(windows)} windows matching '{term}'")
            return int(windows[0])
    return None


def get_window_geometry(hwnd: int) -> tuple[int, int, int, int]:
    """Get window position and size."""
    result = subprocess.run(
        ["xdotool", "getwindowgeometry", str(hwnd)],
        capture_output=True, text=True, timeout=5
    )
    lines = result.stdout.strip().split("\n")
    
    # Parse position
    pos_line = [l for l in lines if "Position:" in l][0]
    pos_str = pos_line.split(":")[1].strip().split()[0]
    x, y = map(int, pos_str.split(","))
    
    # Parse size
    size_line = [l for l in lines if "Geometry:" in l][0]
    size_str = size_line.split(":")[1].strip()
    w, h = map(int, size_str.split("x"))
    
    return x, y, w, h


def main():
    print("=" * 60)
    print("WeChat Send Test")
    print("=" * 60)
    
    # Step 1: Find WeChat
    print("\n[Step 1] Finding WeChat window...")
    hwnd = find_wechat_window()
    if not hwnd:
        print("ERROR: Could not find WeChat window!")
        print("Make sure WeChat is running.")
        return 1
    print(f"  Window ID: {hwnd}")
    
    # Step 2: Get geometry
    print("\n[Step 2] Getting window geometry...")
    x, y, w, h = get_window_geometry(hwnd)
    print(f"  Position: ({x}, {y})")
    print(f"  Size: {w}x{h}")
    
    # Calculate input area (bottom portion of window)
    # WeChat layout: ~22% sidebar, ~6% header, ~13% input at bottom
    input_left = x + int(w * 0.22)
    input_top = y + int(h * 0.87)
    input_right = x + w
    input_bottom = y + h
    
    input_center_x = (input_left + input_right) // 2
    input_center_y = (input_top + input_bottom) // 2
    
    print(f"  Estimated input area: ({input_left}, {input_top}) to ({input_right}, {input_bottom})")
    print(f"  Input center: ({input_center_x}, {input_center_y})")
    
    # Send button position (bottom-right of input area)
    send_btn_x = input_right - 45
    send_btn_y = input_bottom - 15
    print(f"  Send button estimate: ({send_btn_x}, {send_btn_y})")
    
    # Step 3: Focus window
    print("\n[Step 3] Focusing WeChat window...")
    subprocess.run(["xdotool", "windowactivate", "--sync", str(hwnd)])
    time.sleep(0.5)
    print("  Done")
    
    # Step 4: Click input area
    print(f"\n[Step 4] Clicking input area at ({input_center_x}, {input_center_y})...")
    subprocess.run(["xdotool", "mousemove", str(input_center_x), str(input_center_y)])
    time.sleep(0.1)
    subprocess.run(["xdotool", "click", "1"])
    time.sleep(0.2)
    subprocess.run(["xdotool", "click", "1"])  # Double click
    time.sleep(0.3)
    
    # Verify mouse position
    result = subprocess.run(["xdotool", "getmouselocation"], capture_output=True, text=True)
    print(f"  Mouse position: {result.stdout.strip()}")
    
    # Step 5: Type test message
    print("\n[Step 5] Typing test message...")
    test_msg = f"Liao Test {int(time.time()) % 10000}"
    print(f"  Message: {test_msg}")
    
    # Clear existing text
    subprocess.run(["xdotool", "key", "ctrl+a"])
    time.sleep(0.1)
    subprocess.run(["xdotool", "key", "Delete"])
    time.sleep(0.1)
    
    # Set clipboard and paste
    subprocess.run(["wl-copy"], input=test_msg.encode(), timeout=5)
    time.sleep(0.1)
    subprocess.run(["xdotool", "key", "ctrl+v"])
    time.sleep(0.3)
    print("  Text pasted")
    
    # Step 6: Click send button
    print(f"\n[Step 6] Clicking send button at ({send_btn_x}, {send_btn_y})...")
    subprocess.run(["xdotool", "mousemove", str(send_btn_x), str(send_btn_y)])
    time.sleep(0.1)
    subprocess.run(["xdotool", "click", "1"])
    time.sleep(0.3)
    
    # Verify mouse position
    result = subprocess.run(["xdotool", "getmouselocation"], capture_output=True, text=True)
    print(f"  Mouse position: {result.stdout.strip()}")
    
    # Also try Enter key as backup
    print("\n[Step 7] Also pressing Enter as backup...")
    # Click input area again
    subprocess.run(["xdotool", "mousemove", str(input_center_x), str(input_center_y)])
    time.sleep(0.1)
    subprocess.run(["xdotool", "click", "1"])
    time.sleep(0.2)
    subprocess.run(["xdotool", "key", "Return"])
    time.sleep(0.3)
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("Check WeChat to see if the message was sent.")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
