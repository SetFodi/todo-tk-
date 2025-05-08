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
        dialog = ctk.CTkInputDialog(
            text="Type 'delete' to confirm task deletion:",
            title="Confirm Delete"
        )
        result = dialog.get_input()
        
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
        # Fixed Dialog Window
        dialog = FixedTaskDialog(self, "Add New Task")
        
        # Check if the dialog was completed successfully
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
                # Show error message
                dialog = ctk.CTkMessagebox(
                    title="No Selection",
                    message="Please select a task to edit.",
                    icon="cancel"
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
        
        # Fixed Dialog Window
        dialog = FixedTaskDialog(
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


# FIXED Task Dialog with proper sizing and button functionality
class FixedTaskDialog(ctk.CTkToplevel):
    def __init__(self, parent, dialog_title, title="", description="", due_date=None, priority="Medium", category="Personal"):
        super().__init__(parent)
        
        # Set window title and properties
        self.title(dialog_title)
        self.geometry("600x500")
        self.minsize(500, 450)  # Minimum size to ensure all elements are visible
        self.resizable(True, True)  # Allow resizing
        
        # Make sure dialog appears on top and grabs focus
        self.transient(parent)
        self.grab_set()
        
        # Center the dialog on the parent window
        self.center_on_parent(parent)
        
        # Initialize result
        self.result = None
        
        # Store input values
        self.initial_title = title
        self.initial_description = description
        self.initial_due_date = due_date
        self.initial_priority = priority
        self.initial_category = category
        
        # Get task manager reference
        self.task_manager = parent.task_manager
        
        # Build the UI
        self.setup_ui()
        
        # Wait for window to close before returning
        self.wait_window()
    
    def center_on_parent(self, parent):
        # Center the dialog on the parent window
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        width = 600
        height = 500
        
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        
        self.geometry(f"{width}x{height}+{x}+{y}")
    
    def setup_ui(self):
        # Main content frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Title bar
        self.title_bar = ctk.CTkFrame(self.main_frame, corner_radius=0, fg_color=("#dcddde", "#2b2b2b"), height=50)
        self.title_bar.pack(fill=tk.X, pady=0)
        
        # Title label
        self.title_label = ctk.CTkLabel(
            self.title_bar,
            text=self.title(),
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.title_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        # Content area
        self.content_frame = ctk.CTkFrame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Task Title
        self.title_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.title_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.title_label = ctk.CTkLabel(
            self.title_frame,
            text="Title:",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=80,
            anchor="w"
        )
        self.title_label.pack(side=tk.LEFT)
        
        self.title_entry = ctk.CTkEntry(
            self.title_frame,
            placeholder_text="Task title",
            height=35,
            font=ctk.CTkFont(size=13)
        )
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        
        # Pre-fill title if editing
        if self.initial_title:
            self.title_entry.insert(0, self.initial_title)
        
        # Description
        self.desc_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.desc_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.desc_label = ctk.CTkLabel(
            self.desc_frame,
            text="Description:",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        self.desc_label.pack(anchor=tk.W)
        
        self.desc_text = ctk.CTkTextbox(
            self.content_frame,
            height=100,
            font=ctk.CTkFont(size=13),
            wrap="word"
        )
        self.desc_text.pack(fill=tk.X, pady=(0, 15))
        
        # Pre-fill description if editing
        if self.initial_description:
            self.desc_text.insert("0.0", self.initial_description)
        
        # Due Date frame
        self.due_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.due_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Due date label and checkbox
        self.due_date_label = ctk.CTkLabel(
            self.due_frame,
            text="Due Date:",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=80,
            anchor="w"
        )
        self.due_date_label.pack(side=tk.LEFT)
        
        self.due_date_var = tk.BooleanVar(value=self.initial_due_date is not None)
        self.due_date_check = ctk.CTkCheckBox(
            self.due_frame,
            text="Set Due Date",
            variable=self.due_date_var,
            command=self.toggle_due_date
        )
        self.due_date_check.pack(side=tk.LEFT, padx=(10, 0))
        
        # Date and time selector
        self.date_time_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.date_time_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Date entry
        self.date_entry = DateEntry(
            self.date_time_frame,
            width=12,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            state="disabled" if not self.initial_due_date else "normal"
        )
        self.date_entry.pack(side=tk.LEFT)
        
        # Time label
        time_label = ctk.CTkLabel(
            self.date_time_frame,
            text="Time:",
            font=ctk.CTkFont(size=13),
            width=30
        )
        time_label.pack(side=tk.LEFT, padx=(20, 10))
        
        # Hour entry
        self.hour_var = tk.StringVar(value="12")
        self.hour_entry = ctk.CTkEntry(
            self.date_time_frame,
            width=40,
            textvariable=self.hour_var,
            state="disabled" if not self.initial_due_date else "normal"
        )
        self.hour_entry.pack(side=tk.LEFT)
        
        # Time separator
        colon_label = ctk.CTkLabel(self.date_time_frame, text=":", width=5)
        colon_label.pack(side=tk.LEFT)
        
        # Minute entry
        self.minute_var = tk.StringVar(value="00")
        self.minute_entry = ctk.CTkEntry(
            self.date_time_frame,
            width=40,
            textvariable=self.minute_var,
            state="disabled" if not self.initial_due_date else "normal"
        )
        self.minute_entry.pack(side=tk.LEFT)
        
        # Set initial time values if editing
        if self.initial_due_date:
            self.date_entry.set_date(self.initial_due_date.date())
            self.hour_var.set(f"{self.initial_due_date.hour:02d}")
            self.minute_var.set(f"{self.initial_due_date.minute:02d}")
        
        # Priority section
        self.priority_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.priority_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.priority_label = ctk.CTkLabel(
            self.priority_frame,
            text="Priority:",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        self.priority_label.pack(anchor=tk.W)
        
        # Priority radio buttons
        self.priority_radio_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.priority_radio_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.priority_var = tk.StringVar(value=self.initial_priority or "Medium")
        
        # Create radio buttons for priorities
        priorities = ["Low", "Medium", "High", "Critical"]
        for i, priority in enumerate(priorities):
            radio = ctk.CTkRadioButton(
                self.priority_radio_frame,
                text=priority,
                variable=self.priority_var,
                value=priority,
                font=ctk.CTkFont(size=13)
            )
            radio.pack(side=tk.LEFT, padx=(0 if i == 0 else 20, 0))
        
        # Category section
        self.category_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.category_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.category_label = ctk.CTkLabel(
            self.category_frame,
            text="Category:",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        self.category_label.pack(anchor=tk.W)
        
        # Category selector
        self.category_select_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.category_select_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Get categories from database
        categories = [c[1] for c in self.task_manager.get_categories()]
        
        # Set the default category
        self.category_var = tk.StringVar(
            value=self.initial_category if self.initial_category in categories else categories[0]
        )
        
        # Category dropdown
        self.category_dropdown = ctk.CTkOptionMenu(
            self.category_select_frame,
            values=categories,
            variable=self.category_var,
            font=ctk.CTkFont(size=13),
            width=200
        )
        self.category_dropdown.pack(side=tk.LEFT)
        
        # Custom category checkbox
        self.custom_category_var = tk.BooleanVar(value=False)
        self.custom_category_check = ctk.CTkCheckBox(
            self.category_select_frame,
            text="New Category",
            variable=self.custom_category_var,
            command=self.toggle_custom_category
        )
        self.custom_category_check.pack(side=tk.LEFT, padx=(20, 0))
        
        # Custom category entry
        self.custom_category_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.custom_category_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.custom_category_entry = ctk.CTkEntry(
            self.custom_category_frame,
            placeholder_text="Enter new category name",
            font=ctk.CTkFont(size=13),
            state="disabled"
        )
        self.custom_category_entry.pack(fill=tk.X)
        
        # Button frame at the bottom
        self.button_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.button_frame.pack(fill=tk.X, pady=(20, 0))
        
        # Cancel button
        self.cancel_button = ctk.CTkButton(
            self.button_frame,
            text="Cancel",
            fg_color="#888888",
            hover_color="#666666",
            command=self.on_cancel,
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.cancel_button.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        
        # Save button
        self.save_button = ctk.CTkButton(
            self.button_frame,
            text="Save",
            command=self.on_save,
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.save_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    def toggle_due_date(self):
        # Enable/disable date and time controls based on checkbox
        state = "normal" if self.due_date_var.get() else "disabled"
        self.date_entry.config(state=state)
        self.hour_entry.configure(state=state)
        self.minute_entry.configure(state=state)
    
    def toggle_custom_category(self):
        # Enable/disable custom category entry based on checkbox
        if self.custom_category_var.get():
            self.custom_category_entry.configure(state="normal")
            self.category_dropdown.configure(state="disabled")
        else:
            self.custom_category_entry.configure(state="disabled")
            self.category_dropdown.configure(state="normal")
    
    def on_cancel(self):
        # Cancel and close dialog
        self.result = None
        self.destroy()
    
    def on_save(self):
        # Validate inputs and save results
        title = self.title_entry.get().strip()
        if not title:
            self.show_error("Title Required", "Please enter a title for the task.")
            return
        
        # Get description
        description = self.desc_text.get("0.0", "end").strip()
        
        # Get due date if enabled
        due_date = None
        if self.due_date_var.get():
            try:
                date_val = self.date_entry.get_date()
                hour = int(self.hour_var.get())
                minute = int(self.minute_var.get())
                
                # Validate time values
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    self.show_error("Invalid Time", "Hours must be 0-23 and minutes 0-59.")
                    return
                
                # Create datetime object
                due_date = datetime.datetime(
                    year=date_val.year,
                    month=date_val.month,
                    day=date_val.day,
                    hour=hour,
                    minute=minute
                )
            except ValueError:
                self.show_error("Invalid Time", "Please enter valid numbers for hours and minutes.")
                return
        
        # Get priority
        priority = self.priority_var.get()
        
        # Get category
        if self.custom_category_var.get():
            category = self.custom_category_entry.get().strip()
            if not category:
                self.show_error("Category Required", "Please enter a category name.")
                return
        else:
            category = self.category_var.get()
        
        # Set result tuple and close dialog
        self.result = (title, description, due_date, priority, category)
        self.destroy()
    
    def show_error(self, title, message):
        # Display error message
        error_dialog = ctk.CTkMessagebox(
            master=self,
            title=title,
            message=message,
            icon="cancel"
        )


if __name__ == "__main__":
    app = ModernTodoApp()
    app.mainloop()

