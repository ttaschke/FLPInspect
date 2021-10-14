import pathlib
import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as tkfiledlg
import tkinter.messagebox as tkmsgbox
from tkinter.scrolledtext import ScrolledText

from pyflp import Parser
from pyflp.event import Event, ByteEvent, WordEvent, DWordEvent, TextEvent
from pyflp.utils import DATA_TEXT_EVENTS

from .constants import (
    COL0_WIDTH,
    EVENTCOL_WIDTH,
    INDEXCOL_WIDTH,
    SB_DEFAULT,
    VALUECOL_WIDTH,
)
from .gui_logger import GUIHandler  # type: ignore
from .treeview import Treeview


class FLPInspector(tk.Tk):
    def __init__(self, flp: str = "", verbose: bool = True):

        # Init
        super().__init__()
        self.title("FLPInspect")
        self.geometry("600x600")
        self.option_add("*tearOff", tk.FALSE)
        self.style = ttk.Style()

        # Top Menubar
        self.m = tk.Menu()
        self["menu"] = self.m

        # Menubar -> File
        self.m_file = tk.Menu(self.m)
        self.m.add_cascade(menu=self.m_file, label="File")

        # File -> Open
        self.m_file.add_command(
            label="Open", command=self.file_open, accelerator="Ctrl+O", underline=1
        )
        self.bind("<Control-o>", self.file_open)

        # File -> Save
        self.m_file.add_command(
            label="Save as",
            command=self.file_saveas,
            accelerator="Ctrl+S",
            underline=1,
            state="disabled",
        )

        # Menubar -> Preferences
        menu_prefs = tk.Menu(self.m)
        self.m.add_cascade(menu=menu_prefs, label="Preferences")

        # Menubar -> Preferences -> Theme
        prefs_theme = tk.Menu(menu_prefs)
        menu_prefs.add_cascade(menu=prefs_theme, label="Theme")
        themes = self.style.theme_names()
        self.theme = tk.StringVar()
        for t in themes:
            prefs_theme.add_radiobutton(
                label=t,
                value=t,
                variable=self.theme,
                command=lambda *_: self.style.theme_use(self.theme.get()),
            )

        # Menubar -> View
        menu_view = tk.Menu(self.m)
        self.m.add_cascade(menu=menu_view, label="View")

        # All radiobuttons of prefs_theme are bound to self.theme.
        # Select the radiobutton has the name of currently used theme.
        # Without this, no radiobutton will be selected by default.
        self.theme.set(self.style.theme_use())

        # Menubar -> Help
        menu_help = tk.Menu(self.m)
        menu_help.add_command(label="About", command=self.show_about)
        self.m.add_cascade(menu=menu_help, label="Help")

        # Status bar at the bottom
        self.sb = tk.Label(bd=1, relief="sunken", anchor="s", height="1")
        self.sb.pack(side="bottom", fill="x")

        # PanedWindow to split area between Notebook and ScrolledText
        self.pw = tk.PanedWindow(bd=4, sashwidth=10, orient="vertical")
        self.pw.pack(fill="both", expand=tk.TRUE)

        # PanedWindow -> Notebook
        self.nb = ttk.Notebook(self.pw)

        # Clear stale status when tab is changed
        self.nb.bind("<<NotebookTabChanged>>", lambda _: self.sb.configure(text=""))

        # Event View frame
        self.ef = ttk.Frame(self.nb)

        # Treeview
        self.etv = Treeview(self.ef, columns=("#1", "#2", "#3"), show="tree headings")
        self.etv.column("#0", minwidth=COL0_WIDTH, width=COL0_WIDTH, stretch=False)
        self.etv.column("#1", width=INDEXCOL_WIDTH, anchor="w", stretch=False)
        self.etv.heading("#1", text="Index", sort_by="index")
        self.etv.column("#2", width=EVENTCOL_WIDTH, anchor="w", stretch=False)
        self.etv.heading("#2", text="Event", sort_by="event")
        self.etv.column("#3", width=VALUECOL_WIDTH, anchor="w", stretch=False)
        self.etv.heading("#3", text="Value")
        self.etv.pack(side="bottom", expand=tk.TRUE, fill="both")

        # Search combobox
        self.ecb = ttk.Combobox(self.ef)
        self.ecb.bind("<<ComboboxSelected>>", self.tv_filter)
        self.ecb.pack(side="top", fill="x", padx=3, pady=3)

        # Add 'Event View' frame
        self.nb.add(self.ef, text="Event View")

        # Notebook -> 'Channels' Listbox
        self.cf = ttk.Frame(self.nb)
        self.clb = tk.Listbox(
            self.cf, relief="flat", activestyle="none", selectmode="extended"
        )
        cvsb = ttk.Scrollbar(self.cf, orient="vertical", command=self.clb.yview)
        cvsb.pack(side="right", fill="y")
        chsb = ttk.Scrollbar(self.cf, orient="horizontal", command=self.clb.xview)
        chsb.pack(side="bottom", fill="x")
        self.clb.pack(expand=tk.TRUE, fill="both")
        self.clb.configure(xscrollcommand=chsb.set, yscrollcommand=cvsb.set)
        self.nb.add(self.cf, text="Channels")

        # Notebook ->'Patterns' listbox
        self.pf = ttk.Frame(self.nb)
        self.plb = tk.Listbox(
            self.pf, relief="flat", activestyle="none", selectmode="extended"
        )
        pvsb = ttk.Scrollbar(self.pf, orient="vertical", command=self.plb.yview)
        pvsb.pack(side="right", fill="y")
        phsb = ttk.Scrollbar(self.pf, orient="horizontal", command=self.plb.xview)
        phsb.pack(side="bottom", fill="x")
        self.plb.pack(expand=tk.TRUE, fill="both")
        self.plb.configure(xscrollcommand=phsb.set, yscrollcommand=pvsb.set)
        self.nb.add(self.pf, text="Patterns")

        # Notebook ->'Arrangements' treeview
        self.af = ttk.Frame(self.nb)
        self.atv = Treeview(self.af, selectmode="extended", show="tree")
        self.atv.pack(expand=tk.TRUE, fill="both")
        self.nb.add(self.af, text="Arrangements")

        # Pack notebook and panedwindow
        self.nb.pack(fill="both", expand=tk.TRUE)
        self.nb.enable_traversal()
        self.pw.add(self.nb, height=400)

        # Menubar -> View -> Tooltips
        self.__show_htips = tk.BooleanVar(value=False)  # !
        menu_view.add_checkbutton(
            label="Tooltips", variable=self.__show_htips, command=self.etv.toggle_htips
        )

        # ! Till the tooltips are a mess, disable theme by default
        self.etv.toggle_htips()

        # Menubar -> Preferences -> Editable
        self.__editable = tk.BooleanVar(value=True)
        menu_prefs.add_checkbutton(
            label="Editable", variable=self.__editable, command=self.etv.toggle_editing
        )

        # ScrolledText to display Parser logs
        self.console = ScrolledText(self.pw, bg="#D3D3D3")
        self.console.pack(side="bottom")
        self.pw.add(self.console, height=100)

        # Menubar -> View -> Console
        self.__console_visible = tk.BooleanVar(value=True)
        menu_view.add_checkbutton(
            label="Console",
            variable=self.__console_visible,
            command=self.toggle_console,
        )

        # Window doesn't appear without this unless FLP gets parsed
        self.update_idletasks()

        # Verbosity
        self.verbose = verbose
        if not self.verbose:
            self.console.insert(
                "end",
                "Logging has been disabled. "
                "Run with -v option to see detailed log information.",
                "WARNING",
            )
        else:
            self.title("FLPInspect (Verbose Mode)")
        self.console.configure(state="disabled")

        # If called with args from command line
        if flp:
            self.populate(pathlib.Path(flp))

        self.mainloop()

    @staticmethod
    def get_event_value(ev: Event) -> str:
        """The value to display in 'Value' column."""
        if isinstance(ev, ByteEvent):
            v = ev.to_int8()
            if v < 0:
                i8 = v
                u8 = ev.to_uint8()
                v = f"{i8} / {u8}"
        elif isinstance(ev, WordEvent):
            v = ev.to_int16()
            if v < 0:
                i16 = v
                u16 = ev.to_uint16()
                v = f"{i16} / {u16}"
        elif isinstance(ev, DWordEvent):
            v = ev.to_int32()
            if v < 0:
                i32 = v
                u32 = ev.to_uint32()
                v = f"{i32} / {u32}"
        elif isinstance(ev, TextEvent):
            v = ev.to_str()
        else:
            v = str(tuple(ev.data))
        return v

    def tv_filter(self, _=None):
        filter = self.ecb.get()
        self.etv.delete(*self.etv.get_children())
        if filter == "Unfiltered":
            for e in self.events:
                v = self.get_event_value(e)
                self.etv.insert("", "end", values=(e.index, e.id, v))
            return
        for e in self.events:
            if str(e.id) == filter:
                v = self.get_event_value(e)
                self.etv.insert("", "end", values=(e.index, e.id, v))

    def update_status(self, event: tk.Event):
        """Status bar management"""
        page: str = self.nb.select()

        def sb_config(lb: tk.Listbox, prop: str):
            sel = lb.curselection()
            if len(sel) == 1:
                idx = sel[0]
                obj = getattr(self.project, prop)[idx]
                text = repr(obj)
                self.sb.config(text=text)
            else:
                prop_singular = prop[:-1]  # objects -> object
                self.sb.config(text=SB_DEFAULT % prop_singular)

        if page == ".!panedwindow.!notebook.!frame":
            if self.etv.identify_region(event.x, event.y) == "cell":
                row = self.etv.identify_row(event.y)
                index = self.etv.item(row, "values")[0]
                self.sb.config(text=repr(self.events[int(index)]))
        elif page == ".!panedwindow.!notebook.!frame2":
            sb_config(self.clb, "channels")
        elif page == ".!panedwindow.!notebook.!frame3":
            sb_config(self.plb, "patterns")
        elif page == ".!panedwindow.!notebook.!frame4":
            self.sb.config(text="")

    def toggle_console(self):

        # Doesn't work properly without the 'not'
        if not self.__console_visible.get():
            self.pw.forget(self.console)
        else:
            self.pw.add(self.console)

    def populate_etv(self):
        """Populates the event treeview."""
        self.etv_filters = set(["Unfiltered"])
        for ev in self.events:
            self.etv_filters.add(str(ev.id))
            value = self.get_event_value(ev)
            self.etv.insert("", "end", values=(ev.index, ev.id, value))

        # Populate the filter with event types
        self.ecb.configure(values=sorted(self.etv_filters, key=str))

        # Selects "Unfiltered" by default
        self.ecb.current(len(self.etv_filters) - 1)

    def populate(self, file: pathlib.Path):
        gui_handler = GUIHandler(self.console)
        parser = Parser(verbose=self.verbose, handlers=[gui_handler])
        self.project = None
        if file.suffix == ".zip":
            # TODO Parser.get_events for ZIPs
            self.project = parser.parse_zip(file)
        else:
            try:
                self.project = parser.parse(file)
            except Exception as e:
                # * Failsafe mode, only 'Event View' will work
                self.console.configure(state="normal")
                self.console.insert(
                    "end",
                    "\n\nFailed to parse properly; only events will be shown. "
                    f"\nException details: {e}",
                    "ERROR",
                )
                self.console.configure(state="disabled")
                self.events = parser.get_events(file)

                # Remove extra tabs
                # * Technically I can still, provide these infos
                # * but that better be done in PyFLP itself.
                self.nb.forget(self.cf)
                self.nb.forget(self.pf)
                self.nb.forget(self.af)
            else:
                self.events = self.project.events

        def clb():
            """Populate 'Channels' listbox."""
            for ch in self.project.channels:
                name = None
                if ch.name:
                    name = ch.name
                elif ch.default_name:
                    name = ch.default_name
                self.clb.insert("end", name)

        def plb():
            """Populate 'Patterns' listbox."""
            for pat in self.project.patterns:
                self.plb.insert("end", pat.name)

        def atv():
            """Populate 'Arrangements' tab treeview."""
            for arr in self.project.arrangements:
                arr_iid = self.atv.insert("", "end", text=arr.name, open=True)
                tm_iid = self.atv.insert(arr_iid, "end", text="TimeMarkers", open=True)
                for tm in arr.timemarkers:
                    tmn = (tm.name,)
                    if tm.name is None:
                        tmn = f"TimeMarker @ {tm.position}"
                    self.atv.insert(tm_iid, "end", text=tmn)
                tr_iid = self.atv.insert(arr_iid, "end", text="Tracks", open=True)
                for tr in arr.tracks:
                    trn = (tr.name,)
                    if tr.name is None:
                        trn = (f"Track {tr.index}",)
                    self.atv.insert(tr_iid, "end", text=trn)

        self.populate_etv()
        if self.project:
            clb()
            plb()
            atv()
        self.sb.config(text="Ready")

    def file_open(self, _=None):
        """Command for File -> Open and callback for Ctrl+O accelerator.

        Args:
            _ (tk.Event): Not required by this function, kept for bind()
        """

        file = tkfiledlg.askopenfilename(
            title="Select an FLP or a ZIP looped package",
            filetypes=(("FL Studio project", "*.flp"), ("ZIP looped package", "*.zip")),
        )

        if file:
            # Clear all existing tables and listboxes
            for i in self.etv.get_children():
                self.etv.delete(i)
            for i in self.atv.get_children():
                self.atv.delete(i)
            self.clb.delete(0, last=self.clb.size())
            self.plb.delete(0, last=self.plb.size())
            self.console.delete("0.0", "end")
            self.populate(pathlib.Path(file))

            # Update title to include the name of the opened FLP
            self.title(f"FLPInspect - {file}")

            # Mouse hovering in Event View will update status bar
            self.bind("<Motion>", self.update_status)

            # Enable save as operation
            self.m_file.entryconfigure(1, state="normal")
            self.bind("<Control-s>", self.file_saveas)

    def file_saveas(self, _=None):
        """Callback for File -> Save As menubutton."""
        file = tkfiledlg.asksaveasfilename(
            title="Choose the file to save to",
            filetypes=(("FL Studio project", "*.flp"), ("All files", "*.*")),
        )

        if file:
            for idx, child in enumerate(self.etv.get_children()):
                try:
                    value = self.etv.item(child, "values")[2]
                    ev = self.project.events[idx]
                    if ev.id >= 208 and ev.id not in DATA_TEXT_EVENTS:
                        # "(100, 200)" -> b'd\xc8'
                        buf = bytes(map(int, value.strip("()").split(", ")))
                    elif ev.id in range(192, 208) or ev.id in DATA_TEXT_EVENTS:
                        buf = value
                    elif ev.id <= 192:
                        arr = value.split("/")
                        assert len(arr) <= 2
                        positive_value_idx = 1 if len(arr) == 2 else 0
                        buf = int(arr[positive_value_idx].strip())
                    ev.dump(buf)
                except:
                    print(ev.id, buf)
                    raise
            self.project.save(file)
        self.sb.config(text=f"Saved to {file}")

    def show_about(self):
        """Help -> About."""
        tkmsgbox.showinfo("About", "FLPInspect - Inspect your FLPs.")
