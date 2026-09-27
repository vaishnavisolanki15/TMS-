# Transport Management System (TMS)

A **Transport Management System (TMS)** is a web-based application designed to manage and organize transportation-related activities in a simple and efficient way.

The system helps users manage transport information, vehicles, routes, and other transportation details from a single platform.

## Features

* User-friendly web interface
* Manage vehicle details
* Manage driver information
* Manage routes and transportation details
* Add, update, and delete transport records
* View available transport information
* Simple and easy-to-use dashboard
* Backend connected with MySQL database
* Flask-based backend for handling requests and data

## Technologies Used

### Frontend

* HTML
* CSS
* JavaScript

### Backend

* Python
* Flask

### Database

* MySQL

## Project Structure

```text
Transport-Management-System/
│
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── script.js
│   └── images/
│
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── dashboard.html
│   └── ...
│
├── app.py
├── database.sql
├── requirements.txt
└── README.md
```

> The exact file structure may be different depending on the final version of the project.

## How to Run the Project

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/Transport-Management-System.git
```

### 2. Open the Project Folder

```bash
cd Transport-Management-System
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
```

Activate the virtual environment.

**Windows:**

```bash
venv\Scripts\activate
```

### 4. Install Required Libraries

```bash
pip install -r requirements.txt
```

### 5. Set Up MySQL

1. Open MySQL.
2. Create a database for the project.
3. Import the `database.sql` file.
4. Update the database connection details in `app.py`.

Example:

```python
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'your_password'
app.config['MYSQL_DB'] = 'transport_management'
```

### 6. Run the Application

```bash
python app.py
```

The application will run on a local server, usually:

```text
http://127.0.0.1:5000/
```

Open the link in your browser.

## Database

The project uses **MySQL** to store and manage transportation-related information.

The database can contain information such as:

* Users
* Vehicles
* Drivers
* Routes
* Transport records
* Bookings or schedules

## Working of the System

The basic workflow of the system is:

```text
User
  ↓
Login / Access System
  ↓
Dashboard
  ↓
Manage Transport Information
  ↓
Add / Update / Delete Records
  ↓
MySQL Database
  ↓
Display Updated Information
```

## Objective

The main objective of this project is to develop a simple digital system for managing transportation information. It reduces the need for manual record keeping and makes transport-related data easier to manage and access.

## Future Improvements

Some features that can be added in the future are:

* Online vehicle tracking
* GPS integration
* Online booking system
* Automated notifications
* Driver attendance management
* Transport expense tracking
* Advanced reports and analytics
* Admin and user role management

## Project

**Project Name:** Transport Management System
**Type:** Web Application
**Frontend:** HTML, CSS, JavaScript
**Backend:** Python Flask
**Database:** MySQL

## License

This project was developed for **educational and academic purposes**.
