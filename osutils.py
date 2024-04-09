import ctypes

def start_screensaver():
    WM_SYSCOMMAND = 0x0112
    SC_SCREENSAVE = 0xF140
    ctypes.windll.user32.SendMessageA(ctypes.windll.user32.GetDesktopWindow(), WM_SYSCOMMAND, SC_SCREENSAVE, 0)

