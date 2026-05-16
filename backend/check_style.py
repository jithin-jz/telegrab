import ctypes
import sys

GWL_STYLE = -16
GWL_EXSTYLE = -20

def print_styles(title):
    hwnd = ctypes.windll.user32.FindWindowW(None, title)
    if not hwnd:
        print(f"Window '{title}' not found")
        return
    
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
    ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    
    print(f"HWND: {hwnd}")
    print(f"Style: {hex(style)}")
    print(f"ExStyle: {hex(ex_style)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print_styles(sys.argv[1])
    else:
        print_styles("Telegrab")
