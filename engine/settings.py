import math

W, H = 320, 200          # internal render resolution
SCALE = 3                # window scale factor
FOV = math.radians(100)
TEX = 64                 # texture size
WALL_H = 2               # wall height in world units (eye is at 0.5)
MOUSE_SENS = 0.0025
MOVE_SPEED = 3.0
SPRINT_MULT = 1.6        # hold Shift (moving forward)
SLIDE_SPEED = 2.6        # Ctrl: slide starts at MOVE_SPEED * this and eases off
SLIDE_TIME = 0.75        # seconds
SLIDE_DROP = 0.25        # how far the camera dips while sliding (world units)
DIVE_LIFT = 1.8          # upward speed a mid-air slide (dive) gives you, if you were rising slower
SLIDE_STEER = 5.0        # radians/sec a slide can turn toward the held direction
DOUBLE_TAP = 0.25        # max seconds between taps of a direction key to slide that way
FPS = 60
BAR_H = 34               # status bar height
VIEW_H = H - BAR_H       # 3D view height
PITCH_SENS = 0.5         # vertical look, screen pixels per mouse pixel
MAX_PITCH = 150          # how far the horizon can shift up/down (pixels)
HEADSHOT_MULT = 2.5
RESOLUTIONS = ["retro", "medium", "full"]  # 3D view: 320x200, half the screen's resolution, the screen's own
