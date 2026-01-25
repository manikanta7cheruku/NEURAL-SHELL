import tkinter as tk

class SevenGUI:
    def __init__(self, root):
        self.root = root
        
        # 1. WINDOW SETUP
        self.root.title("SEVEN")
        self.root.geometry("500x150") # Bigger size
        self.root.resizable(False, False)
        
        # 2. POSITIONING (Bottom Right)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x_pos = screen_width - 520
        y_pos = screen_height - 200
        self.root.geometry(f"+{x_pos}+{y_pos}")

        # 3. STYLE
        self.root.configure(bg='black')
        self.root.attributes('-alpha', 0.85)
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)

        # 4. UI ELEMENTS
        self.status_bar = tk.Frame(self.root, bg="#00ff00", width=15)
        self.status_bar.pack(side=tk.LEFT, fill=tk.Y)

        # CHANGE: Using 'Text' widget instead of 'Label' for multi-line support
        self.text_area = tk.Text(
            self.root, 
            font=("Consolas", 11),
            fg="#00ff00",
            bg="black",
            wrap="word",       # Wrap words to next line
            bd=0,              # No border
            highlightthickness=0
        )
        self.text_area.pack(side=tk.LEFT, padx=15, pady=10, expand=True, fill='both')
        
        # Initialize text
        self._apply_update("SYSTEM ONLINE", "#00ff00")

    # --- SIGNAL FUNCTIONS ---
    def update_status(self, text, color):
        self.root.after(0, lambda: self._apply_update(text, color))

    def _apply_update(self, text, color):
        # 1. Clear existing text
        self.text_area.delete(1.0, tk.END)
        # 2. Insert new text
        self.text_area.insert(tk.END, text)
        # 3. Change color
        self.text_area.config(fg=color)
        self.status_bar.config(bg=color)

    def close(self):
        self.root.destroy()