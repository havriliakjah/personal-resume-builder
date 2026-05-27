"""
app.py  --  THE UI LAYER  (your "front end")
==============================================================
This file draws the window and reacts to clicks. Read it once
and notice something important: there is NO SQL anywhere in it.

When this file needs data, it calls a function from data.py and
trusts whatever comes back. It does not know -- and must not
care -- that the data lives in SQLite. That ignorance is a
feature. It is what lets the two halves of the app change
independently.

HOW TO RUN IT:
    1. Open a terminal in this folder.
    2. Type:   python app.py
    3. A window opens. Click a table name on the left.

Tkinter (imported below) ships INSIDE Python on Windows, so
there is nothing to install. That is why we start here.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import data  # <-- the data layer. The UI's ONLY door to the database.


class App(tk.Tk):
    """The whole application window.

    Subclassing `tk.Tk` is the Tkinter way of saying
    "this object IS the main window". Everything visible gets
    built inside __init__, which runs once when the app starts.
    """

    def __init__(self):
        super().__init__()
        self.title("Database browser -- starter")
        self.geometry("780x480")
        self.minsize(560, 360)

        # ----- LEFT PANEL: the list of tables ---------------------
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Tables", font=("", 10, "bold")).pack(anchor="w")

        self.table_list = tk.Listbox(left, width=22, exportselection=False)
        self.table_list.pack(fill="y", expand=True, pady=(4, 0))
        # "bind" wires an EVENT to a function. Here: whenever the
        # selection in the listbox changes, run self.on_table_selected.
        self.table_list.bind("<<ListboxSelect>>", self.on_table_selected)

        # ----- RIGHT PANEL: the rows of the chosen table ----------
        right = ttk.Frame(self, padding=10)
        right.pack(side="left", fill="both", expand=True)

        self.status = ttk.Label(right, text="Pick a table on the left.")
        self.status.pack(anchor="w")

        # A small frame holds the data grid and its scrollbar so
        # the two sit side by side and resize together.
        grid_frame = ttk.Frame(right)
        grid_frame.pack(fill="both", expand=True, pady=(6, 0))

        scroll = ttk.Scrollbar(grid_frame, orient="vertical")
        scroll.pack(side="right", fill="y")

        # A Treeview with show="headings" is Tkinter's data grid.
        self.grid = ttk.Treeview(grid_frame, show="headings",
                                 yscrollcommand=scroll.set)
        self.grid.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.grid.yview)  # let the bar scroll the grid

        # ----- Fill the table list once, at startup ---------------
        self.load_tables()

    # ===== EVENT HANDLERS ========================================
    # Each method below is a reaction to something. This is the
    # "event loop" model: the app sits idle, then a user action
    # fires one of these. You will see this pattern in every GUI
    # framework you ever touch.

    def load_tables(self):
        """Ask the data layer for table names and list them."""
        try:
            for name in data.list_tables():
                self.table_list.insert("end", name)
        except Exception as error:
            # If the database file is missing or unreadable, tell
            # the user plainly instead of crashing to a stack trace.
            messagebox.showerror("Could not open database", str(error))

    def on_table_selected(self, _event):
        """Runs every time the user clicks a different table name.

        The `_event` argument is handed in by Tkinter; the leading
        underscore is our way of saying "given to us, but unused".
        """
        selection = self.table_list.curselection()
        if not selection:
            return
        table = self.table_list.get(selection[0])
        self.show_table(table)

    def show_table(self, table):
        """Load one table's columns + rows into the grid on the right.

        Notice the shape of this method: ASK the data layer, then
        DRAW. No SQL, no database knowledge -- just three function
        calls and some widget updates.
        """
        columns = data.get_columns(table)
        rows = data.get_rows(table)
        total = data.count_rows(table)

        # Rebuild the grid's columns for the newly chosen table.
        self.grid.delete(*self.grid.get_children())
        self.grid["columns"] = columns
        for column in columns:
            self.grid.heading(column, text=column)
            self.grid.column(column, width=130, anchor="w")

        # Add one grid line per row of data.
        for row in rows:
            self.grid.insert("", "end", values=row)

        self.status.config(
            text=f"{table}  --  showing {len(rows)} of {total} rows"
        )


# Only build and launch the window when THIS file is run directly
# (python app.py). If some other file ever imports app.py, this
# block stays quiet. Same idiom you saw at the bottom of data.py.
if __name__ == "__main__":
    App().mainloop()
