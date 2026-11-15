
const taskList = document.getElementById("task-list");
const taskForm = document.getElementById("task-form");
const formCard = document.getElementById("task-form-card");

const addButton = document.getElementById("add-task-btn");
const cancelButton = document.getElementById("cancel-btn");

const searchInput = document.getElementById("search-input");
const filterSelect = document.getElementById("filter-select");
const categoryFilter = document.getElementById("category-filter");
const sortSelect = document.getElementById("sort-select");

let tasks = [];
let editingTaskId = null;
const notifiedTasks = new Set();


// API helper
async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers
        }
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Something went wrong");
    }

    return data;
}


// Get today's date without timezone problems
function getToday() {
    const now = new Date();

    return new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate()
    );
}


// Determine task deadline status
function getDeadlineStatus(task) {
    if (!task.due_date || task.completed) {
        return "";
    }

    const dueDate = new Date(`${task.due_date}T00:00:00`);
    const today = getToday();

    if (dueDate < today) {
        return "overdue";
    }

    if (dueDate.getTime() === today.getTime()) {
        return "due-today";
    }

    return "upcoming";
}


// Create browser reminder button
const reminderButton = document.createElement("button");
reminderButton.type = "button";
reminderButton.textContent = "🔔 Enable Reminders";
reminderButton.className = "action-button";
reminderButton.style.marginLeft = "10px";

addButton.insertAdjacentElement("afterend", reminderButton);


// Enable browser notifications after user clicks
reminderButton.addEventListener("click", async () => {
    if (!("Notification" in window)) {
        alert("Your browser does not support notifications.");
        return;
    }

    const permission = await Notification.requestPermission();

    if (permission === "granted") {
        reminderButton.textContent = "🔔 Reminders Enabled";
        checkReminders();
        alert("Task reminders enabled successfully!");
    } else {
        alert("Please allow notifications in your browser settings.");
    }
});


// Check upcoming and overdue tasks
function checkReminders() {
    if (!("Notification" in window) ||
        Notification.permission !== "granted") {
        return;
    }

    const today = getToday();

    tasks.forEach(task => {
        if (task.completed || !task.due_date) return;

        const dueDate = new Date(`${task.due_date}T00:00:00`);
        const tomorrow = new Date(today);
        tomorrow.setDate(today.getDate() + 1);

        let message = "";

        if (dueDate < today) {
            message = "This task is overdue!";
        } else if (dueDate.getTime() === today.getTime()) {
            message = "This task is due today!";
        } else if (dueDate.getTime() === tomorrow.getTime()) {
            message = "This task is due tomorrow!";
        }

        const notificationKey = `${task.id}-${task.due_date}`;

        if (message && !notifiedTasks.has(notificationKey)) {
            new Notification(`TaskFlow: ${task.title}`, {
                body: message,
                icon: ""
            });

            notifiedTasks.add(notificationKey);
        }
    });
}


// Load all tasks
async function loadTasks() {
    try {
        tasks = await apiRequest("/api/tasks");

        updateDashboard();
        renderTasks();
        checkReminders();

    } catch (error) {
        taskList.innerHTML =
            `<p class="empty-state">${error.message}</p>`;
    }
}


// Update dashboard statistics
function updateDashboard() {
    const total = tasks.length;
    const completed = tasks.filter(task => task.completed).length;
    const pending = total - completed;

    document.getElementById("total-count").textContent = total;
    document.getElementById("pending-count").textContent = pending;
    document.getElementById("completed-count").textContent = completed;
}


// Render tasks
function renderTasks() {
    const searchText = searchInput.value.toLowerCase();
    const filter = filterSelect.value;
    const category = categoryFilter ? categoryFilter.value : "all";
    const sort = sortSelect ? sortSelect.value : "newest";

    let filteredTasks = tasks.filter(task => {
        const matchesSearch =
            task.title.toLowerCase().includes(searchText) ||
            (task.description || "").toLowerCase().includes(searchText);

        const matchesStatus =
            filter === "all" ||
            (filter === "pending" && !task.completed) ||
            (filter === "completed" && task.completed);

        const matchesCategory =
            category === "all" ||
            (task.category || "Other") === category;

        return matchesSearch && matchesStatus && matchesCategory;
    });

    // Sorting
    if (sort === "due-date") {
        filteredTasks.sort((a, b) => {
            if (!a.due_date) return 1;
            if (!b.due_date) return -1;
            return a.due_date.localeCompare(b.due_date);
        });

    } else if (sort === "priority") {
        const priorityOrder = {
            High: 1,
            Medium: 2,
            Low: 3
        };

        filteredTasks.sort((a, b) =>
            priorityOrder[a.priority] - priorityOrder[b.priority]
        );

    } else {
        filteredTasks.sort((a, b) => b.id - a.id);
    }

    if (filteredTasks.length === 0) {
        taskList.innerHTML =
            `<p class="empty-state">No tasks found. Add a new task!</p>`;
        return;
    }

    taskList.replaceChildren();

    filteredTasks.forEach(task => {
        const deadlineStatus = getDeadlineStatus(task);

        const card = document.createElement("article");
        card.className = `task-card ${task.completed ? "completed" : ""}`;

        if (deadlineStatus === "overdue") {
            card.classList.add("overdue");
        } else if (deadlineStatus === "due-today") {
            card.classList.add("due-today");
        }

        const info = document.createElement("div");
        info.className = "task-info";

        const heading = document.createElement("h3");
        heading.textContent = task.title;

        const description = document.createElement("p");
        description.textContent =
            task.description || "No description provided";

        const meta = document.createElement("div");
        meta.className = "task-meta";

        const priority = document.createElement("span");
        priority.className = `priority ${task.priority}`;
        priority.textContent = task.priority;

        const categoryLabel = document.createElement("span");
        categoryLabel.className = "task-category";
        categoryLabel.textContent = task.category || "Other";

        const date = document.createElement("span");
        date.textContent = task.due_date
            ? `Due: ${task.due_date}`
            : "No due date";

        meta.append(priority, categoryLabel, date);

        // Add deadline status label
        if (deadlineStatus) {
            const statusLabel = document.createElement("span");
            statusLabel.className = "task-date-status";

            if (deadlineStatus === "overdue") {
                statusLabel.classList.add("overdue-label");
                statusLabel.textContent = "Overdue";
            } else if (deadlineStatus === "due-today") {
                statusLabel.classList.add("today-label");
                statusLabel.textContent = "Due Today";
            } else {
                statusLabel.classList.add("upcoming-label");
                statusLabel.textContent = "Upcoming";
            }

            meta.appendChild(statusLabel);
        }

        info.append(heading, description, meta);

        const actions = document.createElement("div");
        actions.className = "task-actions";

        const completeBtn = document.createElement("button");
        completeBtn.className = "action-button";
        completeBtn.textContent = task.completed ? "Undo" : "✓ Done";
        completeBtn.addEventListener("click", () => toggleTask(task.id));

        const editBtn = document.createElement("button");
        editBtn.className = "action-button";
        editBtn.textContent = "Edit";
        editBtn.addEventListener("click", () => editTask(task.id));

        const deleteBtn = document.createElement("button");
        deleteBtn.className = "action-button delete-button";
        deleteBtn.textContent = "Delete";
        deleteBtn.addEventListener("click", () => deleteTask(task.id));

        actions.append(completeBtn, editBtn, deleteBtn);
        card.append(info, actions);

        taskList.appendChild(card);
    });
}


// Open add task form
addButton.addEventListener("click", () => {
    resetForm();
    formCard.classList.remove("hidden");
    document.getElementById("form-heading").textContent = "Add New Task";
    document.getElementById("task-title").focus();
});


// Close form
cancelButton.addEventListener("click", resetForm);

function resetForm() {
    taskForm.reset();
    editingTaskId = null;
    formCard.classList.add("hidden");
}


// Add or update task
taskForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const taskData = {
        title: document.getElementById("task-title").value.trim(),
        description: document.getElementById("task-description").value.trim(),
        priority: document.getElementById("task-priority").value,
        due_date: document.getElementById("task-date").value,
        category: document.getElementById("task-category").value
    };

    try {
        if (editingTaskId !== null) {
            await apiRequest(`/api/tasks/${editingTaskId}`, {
                method: "PUT",
                body: JSON.stringify(taskData)
            });
        } else {
            await apiRequest("/api/tasks", {
                method: "POST",
                body: JSON.stringify(taskData)
            });
        }

        resetForm();
        await loadTasks();

    } catch (error) {
        alert(error.message);
    }
});


// Edit task
function editTask(id) {
    const task = tasks.find(item => item.id === id);

    if (!task) return;

    editingTaskId = id;

    document.getElementById("form-heading").textContent = "Edit Task";
    document.getElementById("task-title").value = task.title;
    document.getElementById("task-description").value = task.description || "";
    document.getElementById("task-priority").value = task.priority;
    document.getElementById("task-date").value = task.due_date || "";
    document.getElementById("task-category").value = task.category || "Personal";

    formCard.classList.remove("hidden");
    document.getElementById("task-title").focus();
}


// Complete or undo task
async function toggleTask(id) {
    try {
        await apiRequest(`/api/tasks/${id}/toggle`, {
            method: "PATCH"
        });

        await loadTasks();

    } catch (error) {
        alert(error.message);
    }
}


// Delete task
async function deleteTask(id) {
    if (!confirm("Are you sure you want to delete this task?")) {
        return;
    }

    try {
        await apiRequest(`/api/tasks/${id}`, {
            method: "DELETE"
        });

        await loadTasks();

    } catch (error) {
        alert(error.message);
    }
}


// Search, status, category and sorting
searchInput.addEventListener("input", renderTasks);
filterSelect.addEventListener("change", renderTasks);

if (categoryFilter) {
    categoryFilter.addEventListener("change", renderTasks);
}

if (sortSelect) {
    sortSelect.addEventListener("change", renderTasks);
}


// Refresh reminders while TaskFlow is open
setInterval(checkReminders, 60000);


// Load data when page opens
loadTasks();
