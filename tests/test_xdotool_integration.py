#!/usr/bin/env python3
"""Integration test for xdotool mouse and keyboard operations.

This test verifies that xdotool can:
1. Move the mouse to specific coordinates
2. Click at positions
3. Type text via clipboard
4. Send Enter key

Run with: python tests/test_xdotool_integration.py
"""

import subprocess
import sys
import time

# Add src to path
sys.path.insert(0, "src")


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return result."""
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if check and result.returncode != 0:
        print(f"  FAILED: {result.stderr}")
        return result
    if result.stdout.strip():
        print(f"  Output: {result.stdout.strip()}")
    return result


def test_xdotool_available():
    """Test 1: Check xdotool is available."""
    print("\n=== Test 1: xdotool available ===")
    result = run_cmd(["which", "xdotool"])
    if result.returncode == 0:
        print("  ✓ xdotool found")
        return True
    print("  ✗ xdotool not found")
    return False


def test_mouse_move():
    """Test 2: Test mouse movement."""
    print("\n=== Test 2: Mouse movement ===")
    
    # Get current position
    result = run_cmd(["xdotool", "getmouselocation"])
    if result.returncode != 0:
        print("  ✗ Failed to get mouse location")
        return False
    
    # Parse position
    parts = result.stdout.strip().split()
    old_x = int(parts[0].split(":")[1])
    old_y = int(parts[1].split(":")[1])
    print(f"  Current position: ({old_x}, {old_y})")
    
    # Move to new position
    new_x, new_y = 100, 100
    run_cmd(["xdotool", "mousemove", str(new_x), str(new_y)])
    time.sleep(0.2)
    
    # Verify position
    result = run_cmd(["xdotool", "getmouselocation"])
    parts = result.stdout.strip().split()
    actual_x = int(parts[0].split(":")[1])
    actual_y = int(parts[1].split(":")[1])
    
    if actual_x == new_x and actual_y == new_y:
        print(f"  ✓ Mouse moved to ({new_x}, {new_y})")
        # Restore position
        run_cmd(["xdotool", "mousemove", str(old_x), str(old_y)])
        return True
    else:
        print(f"  ✗ Mouse at ({actual_x}, {actual_y}), expected ({new_x}, {new_y})")
        return False


def test_mouse_click():
    """Test 3: Test mouse click."""
    print("\n=== Test 3: Mouse click ===")
    
    # Move and click (we can't easily verify click worked, but we can verify no error)
    run_cmd(["xdotool", "mousemove", "500", "500"])
    time.sleep(0.1)
    result = run_cmd(["xdotool", "click", "1"])
    
    if result.returncode == 0:
        print("  ✓ Click command succeeded")
        return True
    print("  ✗ Click command failed")
    return False


def test_keyboard_input():
    """Test 4: Test keyboard input."""
    print("\n=== Test 4: Keyboard input ===")
    
    # Test key press
    result = run_cmd(["xdotool", "key", "Return"])
    if result.returncode != 0:
        print("  ✗ Key press failed")
        return False
    print("  ✓ Return key succeeded")
    
    # Test hotkey
    result = run_cmd(["xdotool", "key", "ctrl+a"])
    if result.returncode != 0:
        print("  ✗ Hotkey failed")
        return False
    print("  ✓ Ctrl+A hotkey succeeded")
    
    return True


def test_clipboard():
    """Test 5: Test clipboard operations."""
    print("\n=== Test 5: Clipboard operations ===")
    
    test_text = "测试文本 Test 123"
    
    # Try wl-copy (Wayland)
    result = subprocess.run(
        ["wl-copy"], input=test_text.encode(), capture_output=True, timeout=5
    )
    if result.returncode == 0:
        print("  ✓ wl-copy succeeded")
        # Verify with wl-paste
        result = subprocess.run(["wl-paste"], capture_output=True, timeout=5)
        if result.stdout.decode().strip() == test_text:
            print("  ✓ Clipboard content verified")
            return True
    
    # Try xclip
    result = subprocess.run(
        ["xclip", "-selection", "clipboard"],
        input=test_text.encode(), capture_output=True, timeout=5
    )
    if result.returncode == 0:
        print("  ✓ xclip succeeded")
        return True
    
    print("  ✗ Clipboard operations failed")
    return False


def test_input_simulator():
    """Test 6: Test InputSimulator class."""
    print("\n=== Test 6: InputSimulator class ===")
    
    try:
        from liao.core.input_simulator import InputSimulator
        
        sim = InputSimulator()
        print(f"  xdotool available: {sim._linux_xdotool}")
        print(f"  ydotool available: {sim._linux_ydotool}")
        print(f"  wl-copy available: {sim._linux_wl_copy}")
        print(f"  xclip available: {sim._linux_xclip}")
        
        if not sim._linux_xdotool:
            print("  ✗ xdotool not detected by InputSimulator")
            return False
        
        # Test move_to
        print("  Testing move_to(200, 200)...")
        sim.move_to(200, 200)
        time.sleep(0.2)
        
        result = run_cmd(["xdotool", "getmouselocation"])
        parts = result.stdout.strip().split()
        x = int(parts[0].split(":")[1])
        y = int(parts[1].split(":")[1])
        
        if x == 200 and y == 200:
            print("  ✓ move_to works")
        else:
            print(f"  ✗ move_to failed: got ({x}, {y})")
            return False
        
        # Test click
        print("  Testing click(300, 300)...")
        sim.click(300, 300)
        time.sleep(0.2)
        
        result = run_cmd(["xdotool", "getmouselocation"])
        parts = result.stdout.strip().split()
        x = int(parts[0].split(":")[1])
        y = int(parts[1].split(":")[1])
        
        if x == 300 and y == 300:
            print("  ✓ click works")
        else:
            print(f"  ✗ click position wrong: got ({x}, {y})")
            return False
        
        # Test press_key
        print("  Testing press_key('enter')...")
        sim.press_key("enter")
        print("  ✓ press_key works (no error)")
        
        # Test hotkey
        print("  Testing hotkey('ctrl', 'a')...")
        sim.hotkey("ctrl", "a")
        print("  ✓ hotkey works (no error)")
        
        print("  ✓ InputSimulator tests passed")
        return True
        
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_click_in_window():
    """Test 7: Test click_in_window method."""
    print("\n=== Test 7: click_in_window method ===")
    
    try:
        from liao.core.input_simulator import InputSimulator
        
        sim = InputSimulator()
        
        # Get active window
        result = run_cmd(["xdotool", "getactivewindow"])
        if result.returncode != 0:
            print("  ✗ Could not get active window")
            return False
        
        hwnd = int(result.stdout.strip())
        print(f"  Active window: {hwnd}")
        
        # Test click_in_window at (400, 400)
        print("  Testing click_in_window(400, 400)...")
        sim.click_in_window(hwnd, 0, 0, 400, 400)
        time.sleep(0.2)
        
        result = run_cmd(["xdotool", "getmouselocation"])
        parts = result.stdout.strip().split()
        x = int(parts[0].split(":")[1])
        y = int(parts[1].split(":")[1])
        
        if x == 400 and y == 400:
            print("  ✓ click_in_window works")
            return True
        else:
            print(f"  ✗ click_in_window position wrong: got ({x}, {y})")
            return False
        
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_typing_flow():
    """Test 8: Test full typing flow with a real window."""
    print("\n=== Test 8: Full typing flow (interactive) ===")
    print("  This test will open gedit and type text.")
    print("  Press Ctrl+C to skip this test.")
    
    try:
        input("  Press Enter to start, or Ctrl+C to skip...")
    except KeyboardInterrupt:
        print("\n  Skipped")
        return True
    
    try:
        from liao.core.input_simulator import InputSimulator
        
        # Open gedit
        print("  Opening gedit...")
        proc = subprocess.Popen(["gedit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        
        # Get gedit window
        result = run_cmd(["xdotool", "search", "--name", "gedit"])
        if result.returncode != 0 or not result.stdout.strip():
            print("  ✗ Could not find gedit window")
            proc.terminate()
            return False
        
        hwnd = int(result.stdout.strip().split()[0])
        print(f"  gedit window: {hwnd}")
        
        # Focus gedit
        run_cmd(["xdotool", "windowactivate", "--sync", str(hwnd)])
        time.sleep(0.5)
        
        # Get window geometry
        result = run_cmd(["xdotool", "getwindowgeometry", str(hwnd)])
        # Parse position and size
        lines = result.stdout.strip().split("\n")
        pos_line = [l for l in lines if "Position:" in l][0]
        size_line = [l for l in lines if "Geometry:" in l][0]
        
        pos_parts = pos_line.split(":")[1].strip().split(",")
        win_x = int(pos_parts[0])
        win_y = int(pos_parts[1].split()[0])
        
        size_parts = size_line.split(":")[1].strip().split("x")
        win_w = int(size_parts[0])
        win_h = int(size_parts[1])
        
        print(f"  Window at ({win_x}, {win_y}), size {win_w}x{win_h}")
        
        # Click in the text area (center of window)
        click_x = win_x + win_w // 2
        click_y = win_y + win_h // 2
        print(f"  Clicking at ({click_x}, {click_y})...")
        
        sim = InputSimulator()
        sim.click_in_window(hwnd, win_x, win_y, click_x, click_y)
        time.sleep(0.3)
        
        # Type some text
        test_text = "Hello from Liao test! 你好！"
        print(f"  Typing: {test_text}")
        sim.type_text(test_text, clear_first=False)
        time.sleep(0.5)
        
        # Press Enter
        print("  Pressing Enter...")
        sim.press_key("enter")
        time.sleep(0.3)
        
        # Type more
        sim.type_text("Second line - 第二行", clear_first=False)
        time.sleep(0.5)
        
        print("  ✓ Typing flow completed")
        print("  Check gedit to verify the text was typed correctly.")
        
        try:
            input("  Press Enter to close gedit...")
        except KeyboardInterrupt:
            pass
        
        proc.terminate()
        return True
        
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Liao xdotool Integration Test")
    print("=" * 60)
    
    results = {}
    
    # Basic tests
    results["xdotool_available"] = test_xdotool_available()
    if not results["xdotool_available"]:
        print("\n✗ xdotool not available, cannot continue")
        return 1
    
    results["mouse_move"] = test_mouse_move()
    results["mouse_click"] = test_mouse_click()
    results["keyboard_input"] = test_keyboard_input()
    results["clipboard"] = test_clipboard()
    
    # InputSimulator tests
    results["input_simulator"] = test_input_simulator()
    results["click_in_window"] = test_click_in_window()
    
    # Interactive test
    results["full_typing_flow"] = test_full_typing_flow()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
