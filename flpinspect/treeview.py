"""
Treeview implementation used by FLPInspect's Event View.

Stackoverflow to my rescue :)
Column resize event:            https://stackoverflow.com/a/47697226
Editable cells:                 https://stackoverflow.com/a/18815802
Entry scrolling (mousewheel):   https://stackoverflow.com/a/61977144
Entry scrolling (scrollbar):    https://stackoverflow.com/a/61977043
Filtering:                      https://stackoverflow.com/a/63612596
Sorting (ascending/descending): https://stackoverflow.com/a/63432251
Tooltips:                       https://stackoverflow.com/a/68243086
Empty a treeview:               https://stackoverflow.com/a/66967466

Godmode treeview:   https://github.com/unodan/TkInter-Treeview-Example-Demo
"""

import tkinter as tk
from tkinter import ttk, messagebox
from functools import partial

from .constants import EP_MAX, HTIP_MAX, HTIP_MIN, VALUECOL_WIDTH


class EntryPopup(ttk.Entry):
    def __init__(self, tv: ttk.Treeview, iid, text, **kw):
        """If relwidth is set, then width is ignored"""
        super().__init__(tv, **kw)
        self.tv = tv
        self.iid = iid

        self.insert(0, text)
        self["exportselection"] = False

        self.focus_force()
        self.bind("<Return>", self.on_return)
        self.bind("<Control-a>", self.select_all)
        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("<MouseWheel>", lambda _: self.destroy())

    def on_return(self, _=None):
        values = list(self.tv.item(self.iid, "values"))
        values[-1] = self.get()
        self.tv.item(self.iid, values=values)
        self.destroy()

    def select_all(self, _):
        """Set selection on the whole text."""
        self.selection_range(0, "end")

        # returns 'break' to interrupt default key-bindings
        return "break"


class Treeview(ttk.Treeview):
    """A Treeview which supports cell-editing, item-filtering, \
    scrollbars, row-sorting and column resizing.

    NOTE: It is assumed that column headings are #0, #1, #2... and so on.
    """

    allow_unsafe = False

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        # Double-click cell to popup an EntryPopup
        self.bind("<Double-1>", self.on_double_click)

        # Dynamic EntryPopup resizing when Treeview columns are resized
        self.bind("<B1-Motion>", self.on_resize)

        # Tooltip placement
        self.bind("<Motion>", self.show_htip)

        # Close the EntryPopup when the MouseWheel is moved
        self.bind("<MouseWheel>", self.close_popup)

        # Close the EntryPopup when a row is selected
        self.bind("<<TreeviewSelect>>", self.close_popup)

        # Vertical scroll bar
        self.vsb = ttk.Scrollbar(parent, orient="vertical", command=self.yview)
        self.vsb.bind("<Button>", self.close_popup)
        self.vsb.pack(side="right", fill="y")

        # Horizontal scroll bar
        self.hsb = ttk.Scrollbar(parent, orient="horizontal", command=self.xview)
        self.hsb.bind("<Button>", self.close_popup)
        self.hsb.pack(side="bottom", fill="x")

        # "Attach" scrollbars to the treeview
        self.configure(xscrollcommand=self.hsb.set, yscrollcommand=self.vsb.set)

        # IdleLib 'HoverTip'-inspired Tooltip
        self.htip = ttk.Label(
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("TkFixedFont", 8),
            wraplength=250,
        )

        self.__hid = ""
        self.show_htips = self.editable = True

    def heading(self, column, sort_by=None, **kwargs):
        """Implements sorting (ascending-descnding ordering)."""

        if sort_by and not hasattr(kwargs, "command"):
            func = getattr(self, f"_sort_by_{sort_by}", None)
            if func:
                kwargs["command"] = partial(func, column, False)
            else:
                raise tk.TclError(f"No such sort algorithm '{sort_by}'")
        return super().heading(column, **kwargs)

    def __sort(self, column, reverse, data_type, callback):
        l = [(self.set(k, column), k) for k in self.get_children("")]
        l.sort(key=lambda t: data_type(t[0]), reverse=reverse)
        for index, (_, k) in enumerate(l):
            self.move(k, "", index)
        self.heading(column, command=partial(callback, column, not reverse))

    def _sort_by_index(self, column, reverse):
        """Orders the 'Index' column in ascending (0, 1, 2, ...)
        or descending (..., 2, 1, 0) order."""
        self.__sort(column, reverse, int, self._sort_by_index)

    def _sort_by_event(self, column, reverse):
        """Orders the 'Event' column according to standard string
        comparison (0, 1, 2, ..., A, B, C, ...) order."""
        self.__sort(column, reverse, str, self._sort_by_event)

    def close_popup(self, _: tk.Event = None):
        """Close entry popup."""
        if hasattr(self, "ep"):
            self.ep.destroy()

    def toggle_htips(self):
        self.htip.place_forget()
        self.show_htips = not self.show_htips

    def on_resize(self, e: tk.Event):
        """Detect column resizing, resize `self.ep` if active."""

        if not self.identify_region(e.x, e.y) == "separator":
            return

        if hasattr(self, "ep"):
            col0_w = self.column("#0", "width")
            col1_w = self.column("#1", "width")
            col2_w = self.column("#2", "width")
            col3_w = self.column("#3", "width")
            self.ep.place_configure(x=col0_w + col1_w + col2_w, width=col3_w)

    def toggle_editing(self):
        self.editable = not self.editable
        self.close_popup()

    def place_htip(self, text: str, x: int, y: int):
        """Tooltip placement scheduler."""
        # If a place event is already scheduled hide the tooltip and cancel it first
        if self.__hid:
            self.htip.place_forget()
            self.after_cancel(self.__hid)

        # Place the tooltip a bit over the mouse position
        self.__hid = self.after(1000, self.htip.place, {"x": x + 10, "y": y + 15})
        self.htip.configure(text=text)

    def show_htip(self, event: tk.Event):
        if self.show_htips and self.identify_region(event.x, event.y) == "cell":
            self.htip.place_forget()
            row = self.identify_row(event.y)
            values = self.item(row, "values")
            if values:
                text = values[2]
                if len(text) in range(HTIP_MIN, HTIP_MAX) or self.allow_unsafe:
                    self.place_htip(text, event.x, event.y)

    def on_double_click(self, event: tk.Event):
        """Executed, when a row is double-clicked. Opens read-only
        EntryPopup above the item's column, so it is possible to select
        text. If column heading is double clicked, reset its width."""

        # Close previous popups
        self.close_popup()

        # cell, separator, heading, etc.
        region = self.identify_region(event.x, event.y)

        # what row and column was clicked on
        row = self.identify_row(event.y)
        column = self.identify_column(event.x)

        # ! Single click action occurs first (sorting), unexpected behavior
        # ? Could maybe use .after(200, ...) or so when single event is fired
        # ? And .after_cancel here
        # if column == "#0":
        #     self.column(column, width=COL0_WIDTH)
        # if column == "#1":
        #     self.column(column, width=INDEXCOL_WIDTH)
        # elif column == "#2":
        #     self.column(column, width=EVENTCOL_WIDTH)
        if column == "#3":

            # Show popup only when a cell in "Values" is clicked
            if region == "cell":
                # get column position info
                x, y, width, height = self.bbox(row, column)

                # y-axis offset (This value will make the popup appear over
                # the cell, mimicking the behavior of an actual editable cell)
                pady = height // 2

                # place Entry popup properly
                text = self.item(row, "values")[2]
                yes = True
                if len(text) >= EP_MAX and not self.allow_unsafe:
                    yes = messagebox.askyesno(
                        title="Warning",
                        message="Trying to edit this value will most "
                        "likely cause a crash, as it is too big. Continue?",
                        icon=messagebox.WARNING,
                    )
                if yes:
                    state = "normal" if self.editable else "disabled"
                    self.ep = EntryPopup(self, row, text, state=state)
                    self.ep.place(x=x, y=y + pady, anchor="w", width=width)

            # Reset column width
            elif region == "heading":
                self.column(column, width=VALUECOL_WIDTH)
