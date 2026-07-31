from rich.console import Console
from rich.theme import Theme

# COLORS = {
#     "bg": "#16161A",
#     "accent_primary": "#66FCF1",
#     "accent_muted": "#45A29E",
#     "text_light": "#F5F5F7",
#     "text_muted": "#C5C6C7",
#     "border_active": "#66FCF1",
#     "border_muted": "#2D3748",
#     "state_pending": "#F59E0B",
#     "state_accepted": "#10B981",
#     "state_error": "#EF4444",
# }

COLORS = {
    "bg": "#0D0221",              # Deep midnight purple/black
    "accent_primary": "#00F0FF",    # Electric Neon Cyan/Blue
    "accent_muted": "#007A87",      # Muted Teal/Blue (softer on the eyes)
    "text_light": "#FFFFFF",        # Crisp White
    "text_muted": "#708090",        # Muted Slate Gray
    "border_active": "#00F0FF",     # Active Neon Cyan
    "border_muted": "#1A2639",      # Subtle, dark blue-gray border
    "state_pending": "#FFFF00",     # Neon Yellow
    "state_accepted": "#00FF41",    # Matrix Green
    "state_error": "#FF3131",       # Neon Red
}

# COLORS = {
#     "bg": "#0D0221",          # Deep midnight purple
#     "accent_primary": "#00FF41", # Neon Magenta
#     "accent_muted": "#00FF41",  # Electric Violet
#     "text_light": "#FFFFFF",
#     "text_muted": "#A594F9",
#     "border_active": "#00FF41",
#     "border_muted": "#00FF41",
#     "state_pending": "#FFFF00", # Neon Yellow
#     "state_accepted": "#00FF41", # Matrix Green
#     "state_error": "#FF3131",    # Neon Red
# }


# COLORS = {
#     "bg": "#0B0C10",          # Inky black
#     "accent_primary": "#39FF14", # Neon Lime
#     "accent_muted": "#008F11",  # Darker Matrix Green 
#     "text_light": "#E9FFDB",    # Mint-white
#     "text_muted": "#4E9E87",
#     "border_active": "#39FF14",
#     "border_muted": "#1F2833",
#     "state_pending": "#FFD300", # Cyber Yellow
#     "state_accepted": "#00FBFF", # Electric Cyan
#     "state_error": "#FF073A",    # Neon Blood Red
# }

# # COLORS = {
#     "bg": "#120000",          # Deep obsidian red
#     "accent_primary": "#FFAC1C", # Bright Neon Orange
#     "accent_muted": "#E25822",  # Flame
#     "text_light": "#FFFAF0",    # Floral White
#     "text_muted": "#BC544B",
#     "border_active": "#FFAC1C",
#     "border_muted": "#2D0A0A",
#     "state_pending": "#FF00FF", # Contrast Magenta
#     "state_accepted": "#ADFF2F", # Green Yellow
#     "state_error": "#FF0000",    # Pure Red
# }



crucible_theme = Theme({
    "primary": COLORS["accent_primary"],
    "muted": COLORS["accent_muted"],
    "body": COLORS["text_light"],
    "dim": COLORS["text_muted"],
    "pending": COLORS["state_pending"],
    "success": COLORS["state_accepted"],
    "error": COLORS["state_error"],
    "border_muted": COLORS["border_muted"],
    "border_active": COLORS["border_active"],
})

console = Console(color_system="truecolor", theme=crucible_theme, legacy_windows=False)

# crucible_theme = Theme({
#     "primary": COLORS["accent_primary"],
#     "muted": COLORS["accent_muted"],
#     "body": COLORS["text_light"],
#     "dim": COLORS["text_muted"],
#     "pending": COLORS["state_pending"],
#     "success": COLORS["state_accepted"],
#     "error": COLORS["state_error"],
#     "border_muted": COLORS["border_muted"],
#     "border_active": COLORS["border_active"],
# })

# console = Console(color_system="truecolor", theme=crucible_theme)
