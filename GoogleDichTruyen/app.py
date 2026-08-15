import sys
import os

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app_window import GoogleDichTruyenApp

if __name__ == "__main__":
	app = GoogleDichTruyenApp()
	app.mainloop()
