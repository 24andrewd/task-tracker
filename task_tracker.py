import customtkinter as ctk
import json
import os
from datetime import date, datetime
from pathlib import Path
import uuid

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
            # migrate old tasks that lack subtasks/expanded fields
            for t in data:
                t.setdefault("subtasks", [])
                t.setdefault("expanded", True)
            return data
    except Exception:
        return []

def save_tasks(tasks):
    with open(DATA_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

# -- Helpers --------------------------------------------------------------------
def today_str():
    return date.today().isoformat()

def due_priority(due):
    if not due:
        return 99999
    t = today_str()
    if due < t:
        return -1
    return (date.fromisoformat(due) - date.today()).days

def fmt_due(due):
    if not due:
        return "", "#9ca3af"
    d = date.fromisoformat(due)
    label = d.strftime("%b %d, %Y")
    delta = (d - date.today()).days
    if delta < 0:
        return f"\U0001f4c5  {label}  \u26a0 Overdue by {-delta}d", "#f87171"
    elif delta == 0:
        return f"\U0001f4c5  {label}  \u25cf Due Today", "#fbbf24"
    elif delta <= 3:
        return f"\U0001f4c5  {label}  \u25cb In {delta}d", "#60a5fa"
    else:
        return f"\U0001f4c5  {label}", "#9ca3af"

def accent_color(due, done):
    if done or not due:
        return None
    t = today_str()
    if due < t:        return "#ef4444"
    elif due == t:     return "#f59e0b"
    delta = (date.fromisoformat(due) - date.today()).days
    if delta <= 3:     return "#4f8ef7"
    return None

# -- App ------------------------------------------------------------------------
class TaskTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Task Tracker")
        self.geometry("740x740")
        self.minsize(580, 500)
        self.configure(fg_color="#0f1117")

        self.tasks = load_tasks()
        self._subtask_open_id = None
        self._build_ui()
        self._render()

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=28, pady=(24, 0))
        ctk.CTkLabel(hdr, text="\U0001f4cb  Task Tracker",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color="#ffffff").pack(side="left")

        form = ctk.CTkFrame(self, fg_color="#1a1d27", corner_radius=12,
                            border_width=1, border_color="#2a2d3a")
        form.pack(fill="x", padx=28, pady=16)

        ctk.CTkLabel(form, text="TASK", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6b7280").grid(row=0, column=0, sticky="w",
                                               padx=(16,4), pady=(12,2))
        ctk.CTkLabel(form, text="DUE DATE", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6b7280").grid(row=0, column=1, sticky="w",
                                               padx=(8,4), pady=(12,2))

        self.task_entry = ctk.CTkEntry(form, placeholder_text="What needs to get done?",
                                       fg_color="#0f1117", border_color="#2a2d3a",
                                       text_color="#e8eaf0", height=38, width=360)
        self.task_entry.grid(row=1, column=0, padx=(16,4), pady=(0,14))
        self.task_entry.bind("<Return>", lambda e: self._add_task())

        self.date_entry = ctk.CTkEntry(form, placeholder_text="YYYY-MM-DD",
                                       fg_color="#0f1117", border_color="#2a2d3a",
                                       text_color="#e8eaf0", height=38, width=148)
        self.date_entry.grid(row=1, column=1, padx=(8,8), pady=(0,14))
        self.date_entry.insert(0, today_str())
        self.date_entry.bind("<Return>", lambda e: self._add_task())

        add_btn = ctk.CTkButton(form, text="+ Add Task", width=110, height=38,
                                fg_color="#4f8ef7", hover_color="#3d7de8",
                                font=ctk.CTkFont(size=13, weight="bold"),
                                command=self._add_task)
        add_btn.grid(row=1, column=2, padx=(4,16), pady=(0,14))
        form.columnconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                              scrollbar_button_color="#2a2d3a",
                                              scrollbar_button_hover_color="#3a3d4a")
        self.scroll.pack(fill="both", expand=True, padx=28, pady=(0,20))

    def _render(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        active    = [t for t in self.tasks if not t["done"]]
        completed = [t for t in self.tasks if t["done"]]
        active.sort(key=lambda t: due_priority(t.get("due", "")))
        completed.sort(key=lambda t: (t.get("due", "9999"), t.get("completed_at", "")))
        self._section_label(f"Active  ({len(active)})")
        if active:
            for t in active: self._task_card(t)
        else:
            ctk.CTkLabel(self.scroll, text="No active tasks - add one above!",
                         text_color="#4b5563", font=ctk.CTkFont(size=13)).pack(pady=12)
        self._section_label(f"Completed  ({len(completed)})")
        if completed:
            for t in completed: self._task_card(t)
        else:
            ctk.CTkLabel(self.scroll, text="Nothing completed yet",
                         text_color="#4b5563", font=ctk.CTkFont(size=13)).pack(pady=12)

    def _section_label(self, text):
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", pady=(14, 6))
        ctk.CTkLabel(row, text=text.upper(), font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#6b7280").pack(side="left")
        ctk.CTkFrame(row, height=1, fg_color="#2a2d3a").pack(side="left", fill="x", expand=True, padx=(10,0), pady=5)

    def _task_card(self, task):
        done=task["done"]; due=task.get("due",""); subtasks=task.get("subtasks",[])
        expanded=task.get("expanded",True); ac=accent_color(due,done)
        outer=ctk.CTkFrame(self.scroll,fg_color="transparent"); outer.pack(fill="x",pady=4)
        card=ctk.CTkFrame(outer,fg_color="#1a1d27",corner_radius=10,border_width=1,border_color="#2a2d3a")
        card.pack(fill="x")
        if ac: ctk.CTkFrame(card,width=4,fg_color=ac,corner_radius=2).pack(side="left",fill="y",padx=(0,0))
        content=ctk.CTkFrame(card,fg_color="transparent"); content.pack(fill="x",expand=True)
        content.columnconfigure(1,weight=1)
        name_col="#4b5563" if done else "#e8eaf0"
        name_btn=ctk.CTkButton(content,text=task["name"],font=ctk.CTkFont(size=14,overstrike=done),
            text_color=name_col,fg_color="transparent",hover_color="#22253a",anchor="w",corner_radius=6,
            command=lambda tid=task["id"]: self._toggle_task(tid))
        name_btn.grid(row=0,column=1,sticky="ew",padx=(14,8),pady=(14,2 if due else 14))
        if due:
            due_txt,due_col=fmt_due(due)
            ctk.CTkLabel(content,text=due_txt,font=ctk.CTkFont(size=11),
                text_color=due_col if not done else "#4b5563",anchor="w").grid(row=1,column=1,sticky="w",padx=(14,8),pady=(0,12))
        if subtasks:
            done_count=sum(1 for s in subtasks if s["done"])
            badge_col="#4ade80" if done_count==len(subtasks) else "#9ca3af"
            ctk.CTkLabel(content,text=f"{done_count}/{len(subtasks)}",font=ctk.CTkFont(size=11,weight="bold"),
                text_color=badge_col).grid(row=0,column=2,padx=(0,4),pady=14)
        if subtasks:
            arrow="\u25be" if expanded else "\u25b8"
            ctk.CTkButton(content,text=arrow,width=28,height=28,fg_color="transparent",hover_color="#2a2d3a",
                text_color="#9ca3af",font=ctk.CTkFont(size=14),
                command=lambda tid=task["id"]: self._toggle_expand(tid)).grid(row=0,column=3,padx=(0,4),pady=14)
        add_sub=ctk.CTkButton(content,text="\u2295",width=28,height=28,fg_color="transparent",hover_color="#1f2a3a",
            text_color="#4f8ef7",font=ctk.CTkFont(size=16),
            command=lambda tid=task["id"],ow=outer: self._toggle_subtask_input(tid,ow))
        add_sub.grid(row=0,column=4,padx=(0,4),pady=14)
        ctk.CTkButton(content,text="\u2715",width=28,height=28,fg_color="transparent",hover_color="#2a1a1a",
            text_color="#3a3d4a",font=ctk.CTkFont(size=13),
            command=lambda tid=task["id"]: self._delete_task(tid)).grid(row=0,column=5,padx=(0,12),pady=14)
        if subtasks and expanded:
            sub_frame=ctk.CTkFrame(outer,fg_color="#131620",corner_radius=0,border_width=0)
            sub_frame.pack(fill="x",padx=(18,0))
            for sub in subtasks: self._subtask_row(sub_frame,task["id"],sub)
        if self._subtask_open_id==task["id"]: self._render_subtask_input(outer,task["id"])

    def _subtask_row(self,parent,task_id,sub):
        row=ctk.CTkFrame(parent,fg_color="transparent"); row.pack(fill="x",padx=(12,12),pady=2)
        row.columnconfigure(1,weight=1)
        ctk.CTkFrame(row,width=2,fg_color="#2a2d3a",corner_radius=1).grid(row=0,column=0,sticky="ns",padx=(4,8))
        sub_done=sub["done"]
        ctk.CTkButton(row,text=sub["name"],font=ctk.CTkFont(size=13,overstrike=sub_done),
            text_color="#4b5563" if sub_done else "#b0b8c8",fg_color="transparent",hover_color="#22253a",
            anchor="w",corner_radius=4,
            command=lambda sid=sub["id"]: self._toggle_subtask(task_id,sid)).grid(row=0,column=1,sticky="ew",padx=(0,4),pady=5)
        ctk.CTkButton(row,text="\u2715",width=22,height=22,fg_color="transparent",hover_color="#2a1a1a",
            text_color="#3a3d4a",font=ctk.CTkFont(size=11),
            command=lambda sid=sub["id"]: self._delete_subtask(task_id,sid)).grid(row=0,column=2,padx=(4,4),pady=5)

    def _render_subtask_input(self,parent,task_id):
        inp_frame=ctk.CTkFrame(parent,fg_color="#1a1d27",corner_radius=0,border_width=1,border_color="#2a2d3a")
        inp_frame.pack(fill="x",padx=(18,0))
        inner=ctk.CTkFrame(inp_frame,fg_color="transparent"); inner.pack(fill="x",padx=12,pady=8)
        inner.columnconfigure(0,weight=1)
        ctk.CTkFrame(inner,width=2,fg_color="#4f8ef7",corner_radius=1).grid(row=0,column=0,sticky="ns",padx=(4,8))
        entry=ctk.CTkEntry(inner,placeholder_text="Subtask name...",fg_color="#0f1117",
            border_color="#2a2d3a",text_color="#e8eaf0",height=32,width=340)
        entry.grid(row=0,column=1,padx=(0,8)); entry.focus()
        def commit(e=None):
            name=entry.get().strip()
            if name: self._add_subtask(task_id,name)
            else: self._subtask_open_id=None; self._render()
        def cancel(e=None): self._subtask_open_id=None; self._render()
        entry.bind("<Return>",commit); entry.bind("<Escape>",cancel)
        ctk.CTkButton(inner,text="Add",width=60,height=32,fg_color="#4f8ef7",hover_color="#3d7de8",
            font=ctk.CTkFont(size=12,weight="bold"),command=commit).grid(row=0,column=2,padx=(0,4))
        ctk.CTkButton(inner,text="\u2715",width=32,height=32,fg_color="transparent",hover_color="#2a1a1a",
            text_color="#6b7280",font=ctk.CTkFont(size=13),command=cancel).grid(row=0,column=3)

    def _add_task(self):
        name=self.task_entry.get().strip(); due=self.date_entry.get().strip()
        if not name: self.task_entry.focus(); return
        if due:
            try: date.fromisoformat(due)
            except ValueError:
                self.date_entry.delete(0,"end"); self.date_entry.insert(0,"Invalid date!"); return
        self.tasks.append({"id":str(uuid.uuid4()),"name":name,"due":due,"done":False,
            "completed_at":None,"subtasks":[],"expanded":True})
        self.task_entry.delete(0,"end"); self.date_entry.delete(0,"end")
        self.date_entry.insert(0,today_str()); save_tasks(self.tasks); self._render(); self.task_entry.focus()

    def _toggle_task(self,tid):
        for t in self.tasks:
            if t["id"]==tid:
                t["done"]=not t["done"]
                t["completed_at"]=datetime.now().isoformat() if t["done"] else None; break
        save_tasks(self.tasks); self._render()

    def _delete_task(self,tid):
        self.tasks=[t for t in self.tasks if t["id"]!=tid]
        if self._subtask_open_id==tid: self._subtask_open_id=None
        save_tasks(self.tasks); self._render()

    def _toggle_expand(self,tid):
        for t in self.tasks:
            if t["id"]==tid: t["expanded"]=not t.get("expanded",True); break
        save_tasks(self.tasks); self._render()

    def _toggle_subtask_input(self,tid,_outer):
        if self._subtask_open_id==tid: self._subtask_open_id=None
        else:
            self._subtask_open_id=tid
            for t in self.tasks:
                if t["id"]==tid: t["expanded"]=True; break
        self._render()

    def _add_subtask(self,task_id,name):
        for t in self.tasks:
            if t["id"]==task_id:
                t.setdefault("subtasks",[]).append({"id":str(uuid.uuid4()),"name":name,"done":False})
                t["expanded"]=True; break
        self._subtask_open_id=task_id; save_tasks(self.tasks); self._render()

    def _toggle_subtask(self,task_id,sub_id):
        for t in self.tasks:
            if t["id"]==task_id:
                for s in t.get("subtasks",[]):
                    if s["id"]==sub_id: s["done"]=not s["done"]; break
                break
        save_tasks(self.tasks); self._render()

    def _delete_subtask(self,task_id,sub_id):
        for t in self.tasks:
            if t["id"]==task_id:
                t["subtasks"]=[s for s in t.get("subtasks",[]) if s["id"]!=sub_id]; break
        save_tasks(self.tasks); self._render()


# -- Entry point ----------------------------------------------------------------
if __name__ == "__main__":
    app = TaskTrackerApp()
    app.mainloop()
