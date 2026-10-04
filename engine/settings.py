import math

W, H = 320, 200          # internal render resolution
SCALE = 3                # window scale factor
FOV = math.radians(100)
TEX = 64                 # texture size
WALL_H = 2               # wall height in world units (eye is at 0.5)
MOUSE_SENS = 0.0025
MOVE_SPEED = 3.0
FPS = 60
BAR_H = 34               # status bar height
VIEW_H = H - BAR_H       # 3D view height
PITCH_SENS = 0.5         # vertical look, screen pixels per mouse pixel
MAX_PITCH = 150          # how far the horizon can shift up/down (pixels)
HEADSHOT_MULT = 2.5
RESOLUTIONS = ["retro", "medium", "full"]  # 3D view: 320x200, half the screen's resolution, the screen's own
