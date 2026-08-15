import customtkinter as ctk

# Configure default theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Theme colors dictionary for light/dark modes
COLORS = {
	"dark": {
		"bg": "#1e1e2e",
		"card_bg": "#282a36",
		"card_border": "#44475a",
		"text": "#f8f8f2",
		"subtext": "#6272a4",
		"accent": "#bd93f9",
		"success": "#50fa7b",
		"warning": "#ffb86c",
		"error": "#ff5555",
		"entry_bg": "#181825",
	},
	"light": {
		"bg": "#f5f5f7",
		"card_bg": "#ffffff",
		"card_border": "#dcdcdc",
		"text": "#1d1d1f",
		"subtext": "#6e6e73",
		"accent": "#0066cc",
		"success": "#28a745",
		"warning": "#ff9500",
		"error": "#dc3545",
		"entry_bg": "#ffffff",
	}
}

FONT_FAMILY = "Segoe UI"
FONT_TITLE = (FONT_FAMILY, 18, "bold")
FONT_HEADER = (FONT_FAMILY, 14, "bold")
FONT_SUBHEADER = (FONT_FAMILY, 12, "bold")
FONT_NORMAL = (FONT_FAMILY, 12)
FONT_SMALL = (FONT_FAMILY, 10)
FONT_MONO = ("Consolas", 11)
