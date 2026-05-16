import ctypes
import sys
import time

GWL_STYLE = -16
WS_THICKFRAME = 0x00040000
WS_CAPTION = 0x00C00000

def test_maximize(title):
    hwnd = ctypes.windll.user32.FindWindowW(None, title)
    if not hwnd:
        print(f"Window '{title}' not found")
        return
    
    print(f"Found HWND: {hwnd}")
    
    # Add THICKFRAME
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
    style |= WS_THICKFRAME
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)
    
    # Maximize
    ctypes.windll.user32.ShowWindow(hwnd, 3) # SW_MAXIMIZE
    print("Maximized. Check taskbar.")
    time.sleep(5)
    
    # Restore
    ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
    print("Restored.")

if __name__ == "__main__":
    test_maximize("Telegrab")
