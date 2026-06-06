import customtkinter as ctk
import json
import os
from datetime import date, datetime
from pathlib import Path
import uuid

# -- Palette (light "paper notepad" theme) --------------------------------------
PAPER       = "#ffffff"   # page background
INK         = "#23262e"   # main text / title
RULE_DARK   = "#23262e"   # bold rule under the title
RULE_LIGHT  = "#e4e5ea"   # faint ruled lines under each row
LABEL_GRAY  = "#9298a3"   # small-caps section labels ("TOP PRIORITIES")
BOX_BORDER  = "#b9bdc6"   # checkbox outline
CHECK_FILL  = "#2f3440"   # checked checkbox fill
DONE_TEXT   = "#aab0b9"   # completed item text
DATE_FILL   = "#eef0f3"   # date field background
HOVER       = "#f3f4f6"   # subtle hover
DELETE_GRAY = "#c7cbd2"   # delete "x"
SUB_TEXT    = "#5b616c"   # subtask text
ACCENT      = "#2563eb"   # add-subtask "+"

# Due-date colors
DUE_OVERDUE = "#dc2626"
DUE_TODAY   = "#d97706"
DUE_SOON    = "#2563eb"
DUE_LATER   = "#9298a3"

# Minimum ruled lines drawn per panel for the printed-notepad look
MIN_LINES = {"todo": 18, "priority": 7, "appointment": 7}

CATEGORIES = ["todo", "priority", "appointment"]

# -- Persistence ----------------------------------------------------------------
def get_data_path():
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home())) / "TaskTracker"
    else:
        base = Path.home() / ".tasktracker"
    base.mkdir(parents=True, exist_ok=True)
    return base / "tasks.json"

DATA_FILE = get_data_path()

def load_tasks():
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            for t in data:
                cat = t.get("category", "todo")
                t["category"] = cat if cat in CATEGORIES else "todo"
                t.setdefault("due", "")
                t.setdefault("subtasks", [])
                t.setdefault("expanded", True)
                t.setdefault("created", "")
            return data
    except Exception:
        return []

def save_tasks(tasks):
    with open(DATA_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

# -- Date helpers ---------------------------------------------------------------
def parse_due(s):
    """Return ISO date string, '' for blank, or None if unparseable."""
    s = s.strip()
    if not s:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m/%d"):
        try:
            d = datetime.strptime(s, fmt).date()
            if fmt == "%m/%d":
                d = d.replace(year=date.today().year)
            return d.isoformat()
        except ValueError:
            continue
    return None

def due_priority(due):
    if not due:
        return 99999
    return (date.fromisoformat(due) - date.today()).days

def fmt_due(due):
    """Short label + color for a due date."""
    d = date.fromisoformat(due)
    label = d.strftime("%b %-d") if os.name != "nt" else d.strftime("%b %#d")
    delta = (d - date.today()).days
    if delta < 0:
        return f"{label} ⚠", DUE_OVERDUE
    if delta == 0:
        return "Today", DUE_TODAY
    if delta <= 3:
        return label, DUE_SOON
    return label, DUE_LATER

def item_font(size=15, overstrike=False):
    # Clean printed look — uses CustomTkinter's default font family
    return ctk.CTkFont(size=size, overstrike=overstrike)

# -- App ------------------------------------------------------------------------
class TaskTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title("To-Do List")
        self.geometry("900x820")
        self.minsize(720, 580)
        self.configure(fg_color=PAPER)

        self.tasks = load_tasks()
        self.frames = {}          # category -> scrollable frame
        self.entries = {}         # category -> add (name) entry
        self.date_entries = {}    # category -> add (due) entry
        self._subtask_open_id = None

        self._build_ui()
        self._render_all()

    # -- Layout -----------------------------------------------------------------
    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=36, pady=(26, 0))
        ctk.CTkLabel(hdr, text="TO-DO LIST",
                     font=ctk.CTkFont(size=30, weight="bold"),
                     text_color=INK).pack(side="left")

        date_box = ctk.CTkFrame(hdr, fg_color="transparent")
        date_box.pack(side="right")
        ctk.CTkLabel(date_box, text="DATE",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=LABEL_GRAY).pack(side="left", padx=(0, 8), pady=(6, 0))
        self.date_entry = ctk.CTkEntry(date_box, width=120, height=30,
                                       fg_color=DATE_FILL, border_width=0,
                                       text_color=INK, justify="center",
                                       font=ctk.CTkFont(size=14))
        self.date_entry.insert(0, date.today().strftime("%m/%d/%Y"))
        self.date_entry.pack(side="left", pady=(4, 0))

        ctk.CTkFrame(self, height=2, fg_color=RULE_DARK).pack(
            fill="x", padx=36, pady=(10, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=36, pady=(8, 24))
        body.columnconfigure(0, weight=3, uniform="col")
        body.columnconfigure(1, weight=2, uniform="col")
        body.rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 22))
        self._panel(left, "todo", title=None, expand=True)

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        top = ctk.CTkFrame(right, fg_color="transparent")
        top.grid(row=0, column=0, sticky="nsew", pady=(0, 16))
        self._panel(top, "priority", title="TOP PRIORITIES", expand=True)

        bot = ctk.CTkFrame(right, fg_color="transparent")
        bot.grid(row=1, column=0, sticky="nsew")
        self._panel(bot, "appointment", title="APPOINTMENTS / CALLS", expand=True)

    def _panel(self, parent, category, title, expand):
        if title:
            ctk.CTkLabel(parent, text=title,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=LABEL_GRAY).pack(anchor="w", pady=(0, 2))

        addrow = ctk.CTkFrame(parent, fg_color="transparent")
        addrow.pack(fill="x", pady=(2, 6))
        addrow.columnconfigure(0, weight=1)
        entry = ctk.CTkEntry(addrow, placeholder_text="Add an item",
                             height=34, fg_color=PAPER, border_color=RULE_LIGHT,
                             border_width=1, text_color=INK,
                             font=ctk.CTkFont(size=13))
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        date_e = ctk.CTkEntry(addrow, placeholder_text="Due (opt)",
                              width=88, height=34, fg_color=PAPER,
                              border_color=RULE_LIGHT, border_width=1,
                              text_color=INK, font=ctk.CTkFont(size=12))
        date_e.grid(row=0, column=1)
        for w in (entry, date_e):
            w.bind("<Return>", lambda e, c=category: self._add(c))
        self.entries[category] = entry
        self.date_entries[category] = date_e

        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                        scrollbar_button_color="#dfe1e6",
                                        scrollbar_button_hover_color="#cfd2d8")
        scroll.pack(fill="both", expand=expand)
        self.frames[category] = scroll

    # -- Rendering --------------------------------------------------------------
    def _render_all(self):
        for cat in CATEGORIES:
            self._render_panel(cat)

    def _render_panel(self, category):
        frame = self.frames[category]
        for w in frame.winfo_children():
            w.destroy()

        items = [t for t in self.tasks if t["category"] == category]
        items.sort(key=lambda t: (t["done"], due_priority(t.get("due", "")),
                                  t.get("created", "")))
        rows = 0
        for t in items:
            self._item_row(frame, t)
            rows += 1 + (len(t.get("subtasks", [])) if t.get("expanded", True) else 0)

        for _ in range(max(0, MIN_LINES[category] - rows)):
            self._empty_line(frame)

    def _item_row(self, parent, task):
        done = task["done"]
        due = task.get("due", "")
        subs = task.get("subtasks", [])
        expanded = task.get("expanded", True)

        outer = ctk.CTkFrame(parent, fg_color="transparent")
        outer.pack(fill="x")
        row = ctk.CTkFrame(outer, fg_color="transparent")
        row.pack(fill="x")
        row.columnconfigure(1, weight=1)

        var = ctk.StringVar(value="on" if done else "off")
        ctk.CTkCheckBox(
            row, text="", variable=var, onvalue="on", offvalue="off",
            width=22, checkbox_width=20, checkbox_height=20, corner_radius=4,
            border_width=2, border_color=BOX_BORDER, fg_color=CHECK_FILL,
            hover_color=CHECK_FILL, checkmark_color="#ffffff",
            command=lambda tid=task["id"]: self._toggle(tid)
        ).grid(row=0, column=0, sticky="w", padx=(2, 8), pady=7)

        ctk.CTkLabel(row, text=task["name"], anchor="w",
                     font=item_font(15, overstrike=done),
                     text_color=DONE_TEXT if done else INK).grid(
            row=0, column=1, sticky="ew", pady=7)

        col = 2
        if due:
            txt, clr = fmt_due(due)
            ctk.CTkLabel(row, text=txt, font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=DONE_TEXT if done else clr).grid(
                row=0, column=col, padx=(6, 2), pady=7)
            col += 1

        if subs:
            dc = sum(1 for s in subs if s["done"])
            badge_col = "#16a34a" if dc == len(subs) else LABEL_GRAY
            ctk.CTkLabel(row, text=f"{dc}/{len(subs)}",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=badge_col).grid(row=0, column=col, padx=(4, 2), pady=7)
            col += 1
            arrow = "▾" if expanded else "▸"
            ctk.CTkButton(row, text=arrow, width=24, height=24,
                          fg_color="transparent", hover_color=HOVER,
                          text_color=LABEL_GRAY, font=ctk.CTkFont(size=13),
                          command=lambda tid=task["id"]: self._toggle_expand(tid)).grid(
                row=0, column=col, padx=(0, 2), pady=7)
            col += 1

        ctk.CTkButton(row, text="+", width=24, height=24,
                      fg_color="transparent", hover_color=HOVER,
                      text_color=ACCENT, font=ctk.CTkFont(size=16, weight="bold"),
                      command=lambda tid=task["id"]: self._toggle_subtask_input(tid)).grid(
            row=0, column=col, padx=(0, 2), pady=7)
        col += 1
        ctk.CTkButton(row, text="✕", width=24, height=24,
                      fg_color="transparent", hover_color=HOVER,
                      text_color=DELETE_GRAY, font=ctk.CTkFont(size=12),
                      command=lambda tid=task["id"]: self._delete(tid)).grid(
            row=0, column=col, padx=(0, 2), pady=7)

        if subs and expanded:
            for s in subs:
                self._subtask_row(outer, task["id"], s)
        if self._subtask_open_id == task["id"]:
            self._render_subtask_input(outer, task["id"])

        ctk.CTkFrame(parent, height=1, fg_color=RULE_LIGHT).pack(fill="x")

    def _subtask_row(self, parent, task_id, sub):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=(28, 0))
        row.columnconfigure(1, weight=1)
        ctk.CTkFrame(row, width=2, fg_color=RULE_LIGHT).grid(
            row=0, column=0, sticky="ns", padx=(2, 8), pady=2)
        sd = sub["done"]
        var = ctk.StringVar(value="on" if sd else "off")
        ctk.CTkCheckBox(
            row, text="", variable=var, onvalue="on", offvalue="off",
            width=20, checkbox_width=16, checkbox_height=16, corner_radius=3,
            border_width=2, border_color=BOX_BORDER, fg_color=CHECK_FILL,
            hover_color=CHECK_FILL, checkmark_color="#ffffff",
            command=lambda sid=sub["id"]: self._toggle_subtask(task_id, sid)
        ).grid(row=0, column=1, sticky="w", padx=(0, 6), pady=3)
        ctk.CTkLabel(row, text=sub["name"], anchor="w",
                     font=item_font(13, overstrike=sd),
                     text_color=DONE_TEXT if sd else SUB_TEXT).grid(
            row=0, column=2, sticky="ew", pady=3)
        ctk.CTkButton(row, text="✕", width=22, height=22,
                      fg_color="transparent", hover_color=HOVER,
                      text_color=DELETE_GRAY, font=ctk.CTkFont(size=11),
                      command=lambda sid=sub["id"]: self._delete_subtask(task_id, sid)).grid(
            row=0, column=3, padx=(4, 2), pady=3)

    def _render_subtask_input(self, parent, task_id):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=(28, 0))
        frame.columnconfigure(1, weight=1)
        ctk.CTkFrame(frame, width=2, fg_color=ACCENT).grid(
            row=0, column=0, sticky="ns", padx=(2, 8), pady=2)
        entry = ctk.CTkEntry(frame, placeholder_text="Subtask name…",
                             height=30, fg_color=PAPER, border_color=RULE_LIGHT,
                             border_width=1, text_color=INK, font=ctk.CTkFont(size=12))
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=2)
        entry.focus()

        def commit(_=None):
            name = entry.get().strip()
            if name:
                self._add_subtask(task_id, name)
            else:
                self._subtask_open_id = None
                self._render_all()

        def cancel(_=None):
            self._subtask_open_id = None
            self._render_all()

        entry.bind("<Return>", commit)
        entry.bind("<Escape>", cancel)
        ctk.CTkButton(frame, text="Add", width=52, height=30, fg_color=ACCENT,
                      hover_color="#1d4ed8", font=ctk.CTkFont(size=12, weight="bold"),
                      command=commit).grid(row=0, column=2, padx=(0, 2), pady=2)

    def _empty_line(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=36)
        row.pack(fill="x")
        row.pack_propagate(False)
        box = ctk.CTkFrame(row, width=20, height=20, fg_color=PAPER,
                           border_width=2, border_color="#dadde2", corner_radius=4)
        box.pack(side="left", padx=(2, 8), pady=8)
        box.pack_propagate(False)
        ctk.CTkFrame(parent, height=1, fg_color=RULE_LIGHT).pack(fill="x")

    # -- Actions ----------------------------------------------------------------
    def _add(self, category):
        entry = self.entries[category]
        date_e = self.date_entries[category]
        name = entry.get().strip()
        if not name:
            entry.focus()
            return
        due = parse_due(date_e.get())
        if due is None:
            date_e.delete(0, "end")
            date_e.configure(placeholder_text="bad date")
            return
        self.tasks.append({
            "id": str(uuid.uuid4()),
            "name": name,
            "category": category,
            "due": due,
            "done": False,
            "created": datetime.now().isoformat(),
            "completed_at": None,
            "subtasks": [],
            "expanded": True,
        })
        entry.delete(0, "end")
        date_e.delete(0, "end")
        save_tasks(self.tasks)
        self._render_panel(category)
        entry.focus()

    def _toggle(self, tid):
        cat = None
        for t in self.tasks:
            if t["id"] == tid:
                t["done"] = not t["done"]
                t["completed_at"] = datetime.now().isoformat() if t["done"] else None
                cat = t["category"]
                break
        save_tasks(self.tasks)
        if cat:
            self._render_panel(cat)

    def _delete(self, tid):
        cat = next((t["category"] for t in self.tasks if t["id"] == tid), None)
        self.tasks = [t for t in self.tasks if t["id"] != tid]
        if self._subtask_open_id == tid:
            self._subtask_open_id = None
        save_tasks(self.tasks)
        if cat:
            self._render_panel(cat)

    def _toggle_expand(self, tid):
        for t in self.tasks:
            if t["id"] == tid:
                t["expanded"] = not t.get("expanded", True)
                self._render_panel(t["category"])
                break

    def _toggle_subtask_input(self, tid):
        if self._subtask_open_id == tid:
            self._subtask_open_id = None
        else:
            self._subtask_open_id = tid
            for t in self.tasks:
                if t["id"] == tid:
                    t["expanded"] = True
                    break
        self._render_all()

    def _add_subtask(self, task_id, name):
        for t in self.tasks:
            if t["id"] == task_id:
                t.setdefault("subtasks", []).append(
                    {"id": str(uuid.uuid4()), "name": name, "done": False})
                t["expanded"] = True
                break
        self._subtask_open_id = task_id
        save_tasks(self.tasks)
        self._render_all()

    def _toggle_subtask(self, task_id, sub_id):
        for t in self.tasks:
            if t["id"] == task_id:
                for s in t.get("subtasks", []):
                    if s["id"] == sub_id:
                        s["done"] = not s["done"]
                        break
                self._render_panel(t["category"])
                break
        save_tasks(self.tasks)

    def _delete_subtask(self, task_id, sub_id):
        for t in self.tasks:
            if t["id"] == task_id:
                t["subtasks"] = [s for s in t.get("subtasks", []) if s["id"] != sub_id]
                self._render_panel(t["category"])
                break
        save_tasks(self.tasks)


# -- Entry point ----------------------------------------------------------------
if __name__ == "__main__":
    app = TaskTrackerApp()
    app.mainloop()
