import os
import sys
import sqlite3
import datetime
from enum import Enum
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import customtkinter as ctk
from PIL import Image, ImageTk
import time
from tkcalendar import DateEntry

# Set appearance mode and default theme
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

# Define Priority Levels
class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

# Database Setup
def init_database():
    db_path = os.path.join(os.path.expanduser("~"), ".fancy_todo.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP NOT NULL,
        due_date TIMESTAMP,
        completed_at TIMESTAMP,
        priority INTEGER NOT NULL,
        category_id INTEGER,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )
    ''')
    
    # Insert default categories if they don't exist
    default_categories = ["Work", "Personal", "Shopping", "Health", "Education"]
    for category in default_categories:
        cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (category,))
    
    conn.commit()
    return conn

# Task Management
class TaskManager:
    def __init__(self):
        self.conn = init_database()
        self.cursor = self.conn.cursor()
    
    def add_task(self, title, description="", due_date=None, priority=Priority.MEDIUM, category="Personal"):
        # Get category id
        self.cursor.execute("SELECT id FROM categories WHERE name = ?", (category,))
        result = self.cursor.fetchone()
        if not result:
            self.cursor.execute("INSERT INTO categories (name) VALUES (?)", (category,))
            self.conn.commit()
            category_id = self.cursor.lastrowid
        else:
            category_id = result[0]
        
        # Add task
        self.cursor.execute('''
        INSERT INTO tasks (title, description, created_at, due_date, priority, category_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, description, datetime.datetime.now(), due_date, priority.value, category_id))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_all_tasks(self, include_completed=False):
        query = '''
        SELECT t.id, t.title, t.description, t.created_at, t.due_date, t.completed_at, t.priority, c.name
        FROM tasks t
        JOIN categories c ON t.category_id = c.id
        '''
        if not include_completed:
            query += " WHERE t.completed_at IS NULL"
        query += " ORDER BY t.priority DESC, t.due_date ASC"
        
        self.cursor.execute(query)
        return self.cursor.fetchall()
    
    def get_task(self, task_id):
        self.cursor.execute('''
        SELECT t.id, t.title, t.description, t.created_at, t.due_date, t.completed_at, t.priority, c.name
        FROM tasks t
        JOIN categories c ON t.category_id = c.id
        WHERE t.id = ?
        ''', (task_id,))
        return self.cursor.fetchone()
    
    def update_task(self, task_id, title=None, description=None, due_date=None, priority=None, category=None):
        updates = []
        parameters = []
        
        if title:
            updates.append("title = ?")
            parameters.append(title)
        
        if description is not None:
            updates.append("description = ?")
            parameters.append(description)
        
        if due_date is not None:
            updates.append("due_date = ?")
            parameters.append(due_date)
        
        if priority is not None:
            updates.append("priority = ?")
            parameters.append(priority.value)
        
        if category:
            # Get category id
            self.cursor.execute("SELECT id FROM categories WHERE name = ?", (category,))
            result = self.cursor.fetchone()
            if not result:
                self.cursor.execute("INSERT INTO categories (name) VALUES (?)", (category,))
                self.conn.commit()
                category_id = self.cursor.lastrowid
            else:
                category_id = result[0]
            
            updates.append("category_id = ?")
            parameters.append(category_id)
        
        if updates:
            query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
            parameters.append(task_id)
            self.cursor.execute(query, parameters)
            self.conn.commit()
            return True
        return False
    
    def complete_task(self, task_id):
        self.cursor.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (datetime.datetime.now(), task_id)
        )
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def uncomplete_task(self, task_id):
        self.cursor.execute("UPDATE tasks SET completed_at = NULL WHERE id = ?", (task_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def delete_task(self, task_id):
        self.cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def get_categories(self):
        self.cursor.execute("SELECT id, name FROM categories ORDER BY name")
        return self.cursor.fetchall()
    
    def search_tasks(self, query):
        search_query = f"%{query}%"
        self.cursor.execute('''
        SELECT t.id, t.title, t.description, t.created_at, t.due_date, t.completed_at, t.priority, c.name
        FROM tasks t
        JOIN categories c ON t.category_id = c.id
        WHERE t.title LIKE ? OR t.description LIKE ?
        ORDER BY t.priority DESC, t.due_date ASC
        ''', (search_query, search_query))
        return self.cursor.fetchall()
    
    def get_stats(self):
        # Get total tasks
        self.cursor.execute("SELECT COUNT(*) FROM tasks")
        total = self.cursor.fetchone()[0]
        
        # Get completed tasks
        self.cursor.execute("SELECT COUNT(*) FROM tasks WHERE completed_at IS NOT NULL")
        completed = self.cursor.fetchone()[0]
        
        # Get tasks due today
        today = datetime.datetime.now().date()
        today_start = datetime.datetime.combine(today, datetime.time.min)
        today_end = datetime.datetime.combine(today, datetime.time.max)
        
        self.cursor.execute(
            "SELECT COUNT(*) FROM tasks WHERE due_date BETWEEN ? AND ?", 
            (today_start, today_end)
        )
        due_today = self.cursor.fetchone()[0]
        
        # Get overdue tasks
        self.cursor.execute(
            "SELECT COUNT(*) FROM tasks WHERE due_date < ? AND completed_at IS NULL", 
            (today_start,)
        )
        overdue = self.cursor.fetchone()[0]
        
        return {
            "total": total,
            "completed": completed,
            "due_today": due_today,
            "overdue": overdue
        }

# Task Card UI Component
class TaskCard(ctk.CTkFrame):
    def __init__(self, master, task_data, on_select=None, on_complete=None, on_delete=None, on_edit=None, **kwargs):
        super().__init__(master, **kwargs)
        
        self.task_data = task_data
        self.on_select = on_select
        self.on_complete = on_complete
        self.on_delete = on_delete
        self.on_edit = on_edit
        self.selected = False
        
        # Extract task data
        task_id, title, desc, created, due, completed, priority, category = task_data
        
        self.configure(
            corner_radius=10,
            border_width=2,
            fg_color=self.get_priority_color(priority, completed)
        )
        
        # Create layout
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)
        
        # Task title
        self.title_label = ctk.CTkLabel(
            self, 
            text=title, 
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        self.title_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew", columnspan=4)
        
        # Category badge
        self.category_badge = ctk.CTkLabel(
            self,
            text=f" {category} ",
            corner_radius=5,
            fg_color="#555555",
            text_color="#ffffff",
            font=ctk.CTkFont(size=12)
        )
        self.category_badge.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="w")
        
        # Due date
        due_str = "No due date"
        if due:
            due_date = datetime.datetime.fromisoformat(due.replace("Z", "+00:00"))
            due_str = due_date.strftime("%Y-%m-%d %H:%M")
            
            # Highlight overdue tasks
            if not completed and due_date < datetime.datetime.now():
                due_str = f"⚠️ OVERDUE: {due_str}"
        
        self.due_label = ctk.CTkLabel(
            self,
            text=due_str,
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.due_label.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="w", columnspan=4)
        
        # Description (limited)
        desc_text = desc if desc else "No description"
        if len(desc_text) > 100:
            desc_text = desc_text[:97] + "..."
        
        self.desc_label = ctk.CTkLabel(
            self,
            text=desc_text,
            font=ctk.CTkFont(size=12),
            anchor="w",
            justify="left",
            wraplength=300
        )
        self.desc_label.grid(row=3, column=0, padx=10, pady=(0, 5), sticky="nw", columnspan=4)
        
        # Bottom action buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew", columnspan=4)
        
        # Complete/Uncomplete button
        if completed:
            complete_text = "↩️ Undo"
        else:
            complete_text = "✓ Complete"
            
        self.complete_button = ctk.CTkButton(
            button_frame, 
            text=complete_text,
            font=ctk.CTkFont(size=12),
            width=30,
            height=25,
            command=self._on_complete_clicked
        )
        self.complete_button.pack(side="left", padx=(0, 5))
        
        # Edit button
        self.edit_button = ctk.CTkButton(
            button_frame, 
            text="✏️ Edit",
            font=ctk.CTkFont(size=12),
            width=30,
            height=25,
            command=self._on_edit_clicked
        )
        self.edit_button.pack(side="left", padx=5)
        
        # Delete button
        self.delete_button = ctk.CTkButton(
            button_frame, 
            text="🗑️ Delete",
            font=ctk.CTkFont(size=12),
            width=30,
            height=25,
            fg_color="#FF5252",
            hover_color="#FF1A1A",
            command=self._on_delete_clicked
        )
        self.delete_button.pack(side="left", padx=5)
        
        # ID badge in corner
        self.id_badge = ctk.CTkLabel(
            self,
            text=f"#{task_id}",
            corner_radius=5,
            fg_color="#333333",
            text_color="#ffffff",
            font=ctk.CTkFont(size=10),
            width=5,
            height=5
        )
        self.id_badge.place(relx=1.0, rely=0, anchor="ne", x=-5, y=5)
        
        # Add hover effect
        self.bind("<Enter>", self._on_hover_enter)
        self.bind("<Leave>", self._on_hover_leave)
        self.bind("<Button-1>", self._on_click)
        
        # If completed, add strikethrough effect
        if completed:
            self.title_label.configure(text=self._strikethrough(title))
    
    def _strikethrough(self, text):
        # Note: This is a workaround since Tkinter doesn't support text strikethrough directly
        # Using unicode characters for a makeshift strikethrough effect
        return "✓ " + text
    
    def get_priority_color(self, priority, completed):
        # Color palette based on priority and completion status
        if completed:
            return "#444444"  # Dark gray for completed tasks
        
        # Colors for active tasks by priority
        priority_colors = {
            1: "#3399FF",  # Low - Blue
            2: "#33CC33",  # Medium - Green  
            3: "#FFCC00",  # High - Yellow
            4: "#FF5252"   # Critical - Red
        }
        return priority_colors.get(priority, "#33CC33")
    
    def _on_hover_enter(self, event):
        self.configure(border_color="#aaaaaa")
    
    def _on_hover_leave(self, event):
        if not self.selected:
            self.configure(border_color=None)
    
    def _on_click(self, event):
        if self.on_select:
            self.on_select(self.task_data[0])  # Pass task ID
    
    def _on_complete_clicked(self):
        if self.on_complete:
            self.on_complete(self.task_data[0])  # Pass task ID
    
    def _on_delete_clicked(self):
        if self.on_delete:
            self.on_delete(self.task_data[0])  # Pass task ID
    
    def _on_edit_clicked(self):
        if self.on_edit:
            self.on_edit(self.task_data[0])  # Pass task ID
    
    def set_selected(self, selected):
        self.selected = selected
        if selected:
            self.configure(border_color="#ffffff")
        else:
            self.configure(border_color=None)

# Modern Todo App UI
class ModernTodoApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Fancy Todo App")
        self.geometry("1100x700")
        self.minsize(900, 600)
        
        # Initialize task manager
        self.task_manager = TaskManager()
        
        # UI elements
        self.selected_task_id = None
        self.task_cards = {}
        
        # Setup the main layout
        self.setup_ui()
        
        # Load initial data
        self.refresh_tasks()
    
    def setup_ui(self):
        # Create main layout with sidebar and content area
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)
        self.setup_sidebar()
        
        # Main content area
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=1)
        
        # Top bar with search and filter
        self.filter_frame = ctk.CTkFrame(self.content_frame)
        self.filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        self.setup_filter_bar()
        
        # Tasks area with scrolling
        self.tasks_frame_outer = ctk.CTkFrame(self.content_frame)
        self.tasks_frame_outer.grid(row=1, column=0, sticky="nsew")
        self.tasks_frame_outer.grid_columnconfigure(0, weight=1)
        self.tasks_frame_outer.grid_rowconfigure(0, weight=1)
        
        # Create scrollable frame for tasks
        self.tasks_frame = ctk.CTkScrollableFrame(self.tasks_frame_outer)
        self.tasks_frame.grid(row=0, column=0, sticky="nsew")
        self.tasks_frame.grid_columnconfigure(0, weight=1)
    
    def setup_sidebar(self):
        # App logo/title
        self.logo_label = ctk.CTkLabel(
            self.sidebar, 
            text="✨ Fancy Todo",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        # Add task button
        self.add_button = ctk.CTkButton(
            self.sidebar,
            text="+ Add New Task",
            command=self.show_add_task_dialog,
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.add_button.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        # Statistics section header
        self.stats_header = ctk.CTkLabel(
            self.sidebar,
            text="Statistics",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.stats_header.grid(row=2, column=0, padx=20, pady=(20, 10), sticky="w")
        
        # Stats panels
        self.stats_frame = ctk.CTkFrame(self.sidebar)
        self.stats_frame.grid(row=3, column=0, padx=20, pady=0, sticky="ew")
        
        # Setup theme switcher
        self.appearance_mode_label = ctk.CTkLabel(
            self.sidebar, 
            text="Appearance Mode:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(20, 0), sticky="w")
        
        self.appearance_mode_menu = ctk.CTkOptionMenu(
            self.sidebar,
            values=["System", "Light", "Dark"],
            command=self.change_appearance_mode
        )
        self.appearance_mode_menu.grid(row=6, column=0, padx=20, pady=10, sticky="w")
        
        # Set default appearance
        self.appearance_mode_menu.set("System")
        
        # Version info
        self.version_label = ctk.CTkLabel(
            self.sidebar,
            text="Fancy Todo v1.0",
            font=ctk.CTkFont(size=12),
            text_color="#888888"
        )
        self.version_label.grid(row=9, column=0, padx=20, pady=10, sticky="s")
    
    def setup_filter_bar(self):
        # Search box
        self.search_var = tk.StringVar()
        self.filter_frame.grid_columnconfigure(0, weight=1)
        
        # Search label
        self.search_label = ctk.CTkLabel(
            self.filter_frame,
            text="Search:",
            font=ctk.CTkFont(size=14)
        )
        self.search_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")
        
        # Search entry
        self.search_entry = ctk.CTkEntry(
            self.filter_frame,
            textvariable=self.search_var,
            placeholder_text="Search for tasks...",
            height=35,
            width=250,
            font=ctk.CTkFont(size=14)
        )
        self.search_entry.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        
        # Search button
        self.search_button = ctk.CTkButton(
            self.filter_frame,
            text="Search",
            width=30,
            command=self.search_tasks
        )
        self.search_button.grid(row=0, column=2, padx=5, pady=10)
        
        # Clear search button
        self.clear_button = ctk.CTkButton(
            self.filter_frame,
            text="Clear",
            width=30,
            fg_color="#888888",
            hover_color="#666666",
            command=self.clear_search
        )
        self.clear_button.grid(row=0, column=3, padx=5, pady=10)
        
        # Show completed filter
        self.show_completed_var = tk.BooleanVar(value=False)
        self.show_completed = ctk.CTkCheckBox(
            self.filter_frame,
            text="Show Completed",
            variable=self.show_completed_var,
            command=self.refresh_tasks,
            font=ctk.CTkFont(size=14)
        )
        self.show_completed.grid(row=0, column=4, padx=(20, 10), pady=10)
    
    def refresh_tasks(self):
        # Clear existing task cards
        for widget in self.tasks_frame.winfo_children():
            widget.destroy()
        self.task_cards = {}
        
        # Get tasks from database
        include_completed = self.show_completed_var.get()
        tasks = self.task_manager.get_all_tasks(include_completed=include_completed)
        
        # Create task cards
        for i, task in enumerate(tasks):
            task_id = task[0]
            
            # Create a task card with animation effect
            self.after(i * 30, lambda t=task: self.add_task_card(t))
        
        # Update statistics
        self.update_stats()
    
    def add_task_card(self, task):
        # Create task card with a fade-in effect
        task_card = TaskCard(
            self.tasks_frame, 
            task,
            on_select=self.on_task_select,
            on_complete=self.on_task_complete,
            on_delete=self.on_task_delete,
            on_edit=self.on_task_edit,
            height=180
        )
        task_card.grid(row=len(self.task_cards), column=0, sticky="ew", padx=5, pady=5)
        
        # Store reference to the card
        self.task_cards[task[0]] = task_card
        
        # Apply fade-in animation
        task_card.configure(fg_color="transparent")
        self.animate_fade_in(task_card)
    
    def animate_fade_in(self, widget, step=0):
        if step < 10:
            opacity = step / 10
            # This is a workaround since CustomTkinter doesn't have direct opacity control
            # We're manipulating the frame's color to create a fade-in effect
            priority_color = widget.cget("fg_color")
            widget.after(20, lambda: self.animate_fade_in(widget, step + 1))
        else:
            widget.configure(fg_color=widget.get_priority_color(widget.task_data[6], widget.task_data[5] is not None))
    
    def update_stats(self):
        # Clear existing stats
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        
        # Get fresh statistics
        stats = self.task_manager.get_stats()
        
        # Calculate completion percentage
        completion_pct = 0 if stats["total"] == 0 else (stats["completed"] / stats["total"]) * 100
        
        # Create stats cards
        stats_data = [
            {"label": "Total Tasks", "value": stats["total"], "color": "#3399FF"},
            {"label": "Completed", "value": stats["completed"], "color": "#33CC33"},
            {"label": "Due Today", "value": stats["due_today"], "color": "#FFCC00"},
            {"label": "Overdue", "value": stats["overdue"], "color": "#FF5252"}
        ]
        
        # Create grid layout for stats
        self.stats_frame.columnconfigure(0, weight=1)
        self.stats_frame.columnconfigure(1, weight=1)
        
        # Create stat cards in a 2x2 grid
        for i, stat in enumerate(stats_data):
            row, col = divmod(i, 2)
            
            # Create card for each stat
            stat_card = ctk.CTkFrame(self.stats_frame, corner_radius=6)
            stat_card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            # Value
            ctk.CTkLabel(
                stat_card,
                text=str(stat["value"]),
                font=ctk.CTkFont(size=24, weight="bold"),
                text_color=stat["color"]
            ).pack(pady=(10, 0))
            
            # Label
            ctk.CTkLabel(
                stat_card,
                text=stat["label"],
                font=ctk.CTkFont(size=12)
            ).pack(pady=(0, 10))
        
        # Progress bar for completion
        ctk.CTkLabel(
            self.sidebar,
            text=f"Completion: {completion_pct:.1f}%",
            font=ctk.CTkFont(size=14)
        ).grid(row=4, column=0, padx=20, pady=(10, 5), sticky="w")
        
        progress_bar = ctk.CTkProgressBar(self.sidebar, height=15)
        progress_bar.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")
        progress_bar.set(completion_pct / 100)
    
    def search_tasks(self):
        query = self.search_var.get().strip()
        if not query:
            self.refresh_tasks()
            return
        
        # Clear existing task cards
        for widget in self.tasks_frame.winfo_children():
            widget.destroy()
        self.task_cards = {}
        
        # Get search results
        results = self.task_manager.search_tasks(query)
        
        # Filter completed tasks if needed
        if not self.show_completed_var.get():
            results = [task for task in results if task[5] is None]
        
        # Create task cards
        for i, task in enumerate(results):
            self.after(i * 30, lambda t=task: self.add_task_card(t))
    
    def clear_search(self):
        self.search_var.set("")
        self.refresh_tasks()
    
    def on_task_select(self, task_id):
        # Update selected task
        if self.selected_task_id in self.task_cards:
            self.task_cards[self.selected_task_id].set_selected(False)
        
        self.selected_task_id = task_id
        if task_id in self.task_cards:
            self.task_cards[task_id].set_selected(True)
    
    def on_task_complete(self, task_id):
        task = self.task_manager.get_task(task_id)
        if not task:
            return
        
        _, _, _, _, _, completed, _, _ = task
        
        # Toggle completion status
        if completed:
            self.task_manager.uncomplete_task(task_id)
        else:
            self.task_manager.complete_task(task_id)
        
        # Refresh UI with a cool animation
        self.animate_refresh()
    
    def on_task_delete(self, task_id):
        # Confirm deletion
        result = ctk.CTkInputDialog(
            text="Type 'delete' to confirm task deletion:",
            title="Confirm Delete"
        ).get_input()
        
        if result and result.lower() == "delete":
            # Animate deletion
            if task_id in self.task_cards:
                card = self.task_cards[task_id]
                self.animate_slide_out(card, lambda: self.delete_task(task_id))
            else:
                self.delete_task(task_id)
    
    def delete_task(self, task_id):
        if self.task_manager.delete_task(task_id):
            self.refresh_tasks()
    
    def on_task_edit(self, task_id):
        self.show_edit_task_dialog(task_id)
    
    def show_add_task_dialog(self):
        dialog = TaskDialog(self, "Add New Task")
        if dialog.result:
            title, description, due_date, priority, category = dialog.result
            
            priority_enum = Priority.MEDIUM
            if priority == "Low":
                priority_enum = Priority.LOW
            elif priority == "High":
                priority_enum = Priority.HIGH
            elif priority == "Critical":
                priority_enum = Priority.CRITICAL
            
            task_id = self.task_manager.add_task(
                title=title,
                description=description,
                due_date=due_date,
                priority=priority_enum,
                category=category
            )
            
            # Refresh the task list with animation
            self.animate_refresh()
    
    def show_edit_task_dialog(self, task_id=None):
        if task_id is None:
            if self.selected_task_id is None:
                ctk.CTkMessagebox(
                    title="No Selection",
                    message="Please select a task to edit."
                )
                return
            task_id = self.selected_task_id
        
        task = self.task_manager.get_task(task_id)
        if not task:
            return
        
        task_id, title, desc, created, due, completed, priority, category = task
        
        # Format due date for the dialog
        due_date = None
        if due:
            due_date = datetime.datetime.fromisoformat(due.replace("Z", "+00:00"))
        
        # Map priority value to name
        priority_name = "Medium"
        if priority == 1:
            priority_name = "Low"
        elif priority == 3:
            priority_name = "High"
        elif priority == 4:
            priority_name = "Critical"
        
        dialog = TaskDialog(
            self, 
            "Edit Task",
            title=title,
            description=desc or "",
            due_date=due_date,
            priority=priority_name,
            category=category
        )
        
        if dialog.result:
            new_title, new_description, new_due_date, new_priority, new_category = dialog.result
            
            priority_enum = Priority.MEDIUM
            if new_priority == "Low":
                priority_enum = Priority.LOW
            elif new_priority == "High":
                priority_enum = Priority.HIGH
            elif new_priority == "Critical":
                priority_enum = Priority.CRITICAL
            
            self.task_manager.update_task(
                task_id=task_id,
                title=new_title,
                description=new_description,
                due_date=new_due_date,
                priority=priority_enum,
                category=new_category
            )
            
            # Refresh the task list with animation
            self.animate_refresh()
    
    def animate_refresh(self):
        # Slide out all cards
        for widget in self.tasks_frame.winfo_children():
            self.animate_slide_out(widget, None)
        
        # After animation delay, refresh the list
        self.after(300, self.refresh_tasks)
    
    def animate_slide_out(self, widget, callback=None):
        # Animate sliding out to the right
        widget.configure(fg_color="transparent")
        if callback:
            self.after(250, callback)
    
    def change_appearance_mode(self, new_appearance_mode):
        ctk.set_appearance_mode(new_appearance_mode)

# Modern Task Dialog
class TaskDialog(ctk.CTkToplevel):
    def __init__(self, parent, title_text, title="", description="", due_date=None, priority="Medium", category="Personal"):
        super().__init__(parent)
        self.title(title_text)
        self.geometry("600x500")
        self.resizable(False, False)
        self.grab_set()
        
        # Store initial values
        self.result = None
        self.initial_title = title
        self.initial_description = description
        self.initial_due_date = due_date
        self.initial_priority = priority
        self.initial_category = category
        
        # Get task manager for categories
        self.task_manager = parent.task_manager
        
        # Set up UI
        self.setup_ui()
        
        # Wait for window to be destroyed
        self.wait_window()
    
    def setup_ui(self):
        main_frame = ctk.CTkFrame(self, corner_radius=0)
        main_frame.pack(fill="both", expand=True)
        
        # Create a title bar for the dialog
        title_bar = ctk.CTkFrame(main_frame, fg_color=("#dcddde", "#2b2b2b"), height=60)
        title_bar.pack(fill="x", padx=0, pady=0)
        
        # Dialog title
        ctk.CTkLabel(
            title_bar, 
            text=self.title(),
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left", padx=20, pady=15)
        
        # Content area
        content = ctk.CTkFrame(main_frame)
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Task fields
        # Title
        ctk.CTkLabel(
            content, 
            text="Title:",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(0, 5))
        
        self.title_entry = ctk.CTkEntry(
            content,
            placeholder_text="Enter task title",
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.title_entry.pack(fill="x", pady=(0, 15))
        if self.initial_title:
            self.title_entry.insert(0, self.initial_title)
        
        # Description
        ctk.CTkLabel(
            content, 
            text="Description:",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(0, 5))
        
        self.description_text = ctk.CTkTextbox(
            content,
            height=100,
            font=ctk.CTkFont(size=14)
        )
        self.description_text.pack(fill="x", pady=(0, 15))
        if self.initial_description:
            self.description_text.insert("0.0", self.initial_description)
        
        # Due Date
        due_frame = ctk.CTkFrame(content)
        due_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            due_frame, 
            text="Due Date:",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=(0, 10))
        
        self.due_date_checkbox_var = tk.BooleanVar(value=self.initial_due_date is not None)
        self.use_due_date_checkbox = ctk.CTkCheckBox(
            due_frame,
            text="Set Due Date",
            variable=self.due_date_checkbox_var,
            command=self.toggle_due_date,
            font=ctk.CTkFont(size=14)
        )
        self.use_due_date_checkbox.pack(side="left")
        
        # Date picker and time entry
        date_time_frame = ctk.CTkFrame(content)
        date_time_frame.pack(fill="x", pady=(0, 15))
        
        self.date_entry = DateEntry(
            date_time_frame,
            width=12,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            state="disabled" if not self.initial_due_date else "normal"
        )
        self.date_entry.pack(side="left", padx=(0, 10))
        
        time_frame = ctk.CTkFrame(date_time_frame)
        time_frame.pack(side="left")
        
        self.hour_var = tk.StringVar(value="12")
        self.minute_var = tk.StringVar(value="00")
        
        self.hour_spinbox = ctk.CTkEntry(
            time_frame,
            textvariable=self.hour_var,
            width=40,
            font=ctk.CTkFont(size=14),
            state="disabled" if not self.initial_due_date else "normal"
        )
        self.hour_spinbox.pack(side="left")
        
        ctk.CTkLabel(time_frame, text=":").pack(side="left", padx=2)
        
        self.minute_spinbox = ctk.CTkEntry(
            time_frame,
            textvariable=self.minute_var,
            width=40,
            font=ctk.CTkFont(size=14),
            state="disabled" if not self.initial_due_date else "normal"
        )
        self.minute_spinbox.pack(side="left")
        
        # Set default values for date and time
        if self.initial_due_date:
            self.date_entry.set_date(self.initial_due_date.date())
            self.hour_var.set(f"{self.initial_due_date.hour:02d}")
            self.minute_var.set(f"{self.initial_due_date.minute:02d}")
        else:
            now = datetime.datetime.now()
            self.date_entry.set_date(now.date())
            self.hour_var.set(f"{now.hour:02d}")
            self.minute_var.set(f"{now.minute:02d}")
        
        # Priority
        ctk.CTkLabel(
            content, 
            text="Priority:",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(0, 5))
        
        self.priority_var = tk.StringVar(value=self.initial_priority)
        priority_frame = ctk.CTkFrame(content)
        priority_frame.pack(fill="x", pady=(0, 15))
        
        priorities = ["Low", "Medium", "High", "Critical"]
        for i, p in enumerate(priorities):
            rb = ctk.CTkRadioButton(
                priority_frame, 
                text=p, 
                variable=self.priority_var, 
                value=p,
                font=ctk.CTkFont(size=14)
            )
            rb.pack(side="left", padx=(0 if i == 0 else 20, 0))
        
        # Category
        ctk.CTkLabel(
            content, 
            text="Category:",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(0, 5))
        
        category_frame = ctk.CTkFrame(content)
        category_frame.pack(fill="x", pady=(0, 15))
        
        # Get categories
        categories = [c[1] for c in self.task_manager.get_categories()]
        self.category_var = tk.StringVar(value=self.initial_category if self.initial_category in categories else categories[0])
        
        self.category_optionmenu = ctk.CTkOptionMenu(
            category_frame,
            values=categories,
            variable=self.category_var,
            font=ctk.CTkFont(size=14),
            dynamic_resizing=False,
            width=200
        )
        self.category_optionmenu.pack(side="left")
        
        # New category
        self.custom_category_var = tk.BooleanVar(value=False)
        self.custom_category_check = ctk.CTkCheckBox(
            category_frame,
            text="New Category",
            variable=self.custom_category_var,
            command=self.toggle_custom_category,
            font=ctk.CTkFont(size=14)
        )
        self.custom_category_check.pack(side="left", padx=(20, 0))
        
        self.custom_category_entry = ctk.CTkEntry(
            content,
            placeholder_text="Enter new category name",
            state="disabled",
            font=ctk.CTkFont(size=14)
        )
        self.custom_category_entry.pack(fill="x", pady=(0, 15))
        
        # Buttons
        button_frame = ctk.CTkFrame(content)
        button_frame.pack(fill="x", pady=(10, 0))
        
        # Cancel button
        self.cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self.destroy,
            fg_color="#888888",
            hover_color="#666666",
            font=ctk.CTkFont(size=14),
            height=40
        )
        self.cancel_button.pack(side="left", padx=(0, 10), fill="x", expand=True)
        
        # Save button
        self.save_button = ctk.CTkButton(
            button_frame,
            text="Save",
            command=self.on_save,
            font=ctk.CTkFont(size=14),
            height=40
        )
        self.save_button.pack(side="left", fill="x", expand=True)
    
    def toggle_due_date(self):
        state = "normal" if self.due_date_checkbox_var.get() else "disabled"
        self.date_entry.config(state=state)
        self.hour_spinbox.configure(state=state)
        self.minute_spinbox.configure(state=state)
    
    def toggle_custom_category(self):
        if self.custom_category_var.get():
            self.custom_category_entry.configure(state="normal")
            self.category_optionmenu.configure(state="disabled")
        else:
            self.custom_category_entry.configure(state="disabled")
            self.category_optionmenu.configure(state="normal")
    
    def on_save(self):
        # Validate title
        title = self.title_entry.get().strip()
        if not title:
            self.show_error("Error", "Title is required.")
            return
        
        # Get description
        description = self.description_text.get("0.0", "end").strip()
        
        # Get due date
        due_date = None
        if self.due_date_checkbox_var.get():
            try:
                selected_date = self.date_entry.get_date()
                hour = int(self.hour_var.get())
                minute = int(self.minute_var.get())
                
                # Validate time values
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    self.show_error("Error", "Invalid time. Hours must be 0-23, minutes 0-59.")
                    return
                    
                due_date = datetime.datetime(
                    year=selected_date.year,
                    month=selected_date.month,
                    day=selected_date.day,
                    hour=hour,
                    minute=minute
                )
            except ValueError:
                self.show_error("Error", "Invalid time format. Please use numbers for hours (0-23) and minutes (0-59).")
                return
        
        # Get priority
        priority = self.priority_var.get()
        
        # Get category
        if self.custom_category_var.get():
            category = self.custom_category_entry.get().strip()
            if not category:
                self.show_error("Error", "Custom category name is required.")
                return
        else:
            category = self.category_var.get()
        
        # Set result and close
        self.result = (title, description, due_date, priority, category)
        self.destroy()
    
    def show_error(self, title, message):
        ctk.CTkMessagebox(
            master=self,
            title=title,
            message=message,
            icon="cancel"
        )

if __name__ == "__main__":
    app = ModernTodoApp()
    app.mainloop()

