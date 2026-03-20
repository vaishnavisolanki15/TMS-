import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, session, flash
from db import dbconnect
from functools import wraps

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/profiles'
app.secret_key = "tms_secret_key"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "role" not in session or session["role"] not in allowed_roles:
                flash("You do not have permission to access that feature.", "error")
                return redirect("/dashboard")
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# -----------------------------
# LOGIN PAGE
# -----------------------------

@app.route("/", methods=["GET","POST"])

@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        conn = dbconnect()
        cur = conn.cursor(dictionary=True)

        query = "SELECT * FROM users WHERE Email=%s AND Password=%s AND Role=%s"
        cur.execute(query,(email, password, role))

        user = cur.fetchone()

        if user:
            session["user_id"] = user["User_id"]
            session["username"] = user["First_name"] + " " + user["Last_name"]
            session["role"] = user["Role"]
            
            # Additional fetch for profile pic
            if user.get("Profile_pic"):
                session["profile_pic"] = user["Profile_pic"]

            return redirect("/dashboard")

        else:
            return render_template("login.html",error="Invalid Login")

    return render_template("login.html")


# -----------------------------
# LOGOUT
# -----------------------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# -----------------------------
# DASHBOARD
# -----------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    conn = dbconnect()
    cur = conn.cursor(dictionary=True)

    # DRIVER DASHBOARD LOGIC
    if session.get("role") == "driver":
        # Fetch current trips
        cur.execute('''
            SELECT t.Trip_id AS id, v.Truck_Number AS truck, CONCAT(t.Route_From, " to ", t.Route_To) AS route, t.Start_Date AS start
            FROM trips t 
            LEFT JOIN vehicles v ON t.Vehicle_id = v.Vehicle_id
            WHERE t.Driver_id = (SELECT driver_id FROM drivers WHERE name = %s LIMIT 1) AND t.Status = 'in_progress'
        ''', (session.get("username"),))
        current_trips = cur.fetchall()

        # Fetch upcoming trips
        cur.execute('''
            SELECT t.Trip_id AS id, v.Truck_Number AS truck, CONCAT(t.Route_From, " to ", t.Route_To) AS route, t.Start_Date AS start
            FROM trips t 
            LEFT JOIN vehicles v ON t.Vehicle_id = v.Vehicle_id
            WHERE t.Driver_id = (SELECT driver_id FROM drivers WHERE name = %s LIMIT 1) AND t.Status = 'pending'
        ''', (session.get("username"),))
        upcoming_trips = cur.fetchall()

        return render_template("dashboard.html", current_trips=current_trips, upcoming_trips=upcoming_trips)


    # ADMIN / MANAGER / ACCOUNTANT LOGIC
    cur.execute("SELECT COUNT(*) AS c FROM vehicles")
    vehicle_count = cur.fetchone()['c']

    cur.execute("SELECT COUNT(*) AS c FROM trips")
    trip_count = cur.fetchone()['c']

    cur.execute("SELECT COUNT(*) AS c FROM consignments")
    consignment_count = cur.fetchone()['c']

    cur.execute("SELECT IFNULL(SUM(amount), 0) AS c FROM payments")
    payment_total = cur.fetchone()['c']

    # --- REPORTING DATA FOR CHARTS --- #
    
    # 1. Revenue Report
    cur.execute("SELECT IFNULL(SUM(Amount), 0) AS c FROM payments WHERE Payment_date = CURDATE()")
    rev_today = float(cur.fetchone()['c'])
    cur.execute("SELECT IFNULL(SUM(Amount), 0) AS c FROM payments WHERE YEARWEEK(Payment_date, 1) = YEARWEEK(CURDATE(), 1)")
    rev_week = float(cur.fetchone()['c'])
    cur.execute("SELECT IFNULL(SUM(Amount), 0) AS c FROM payments WHERE MONTH(Payment_date) = MONTH(CURDATE()) AND YEAR(Payment_date) = YEAR(CURDATE())")
    rev_month = float(cur.fetchone()['c'])
    cur.execute("SELECT IFNULL(SUM(Amount), 0) AS c FROM payments WHERE YEAR(Payment_date) = YEAR(CURDATE())")
    rev_year = float(cur.fetchone()['c'])
    revenue_data = [rev_today, rev_week, rev_month, rev_year]

    # 2. Trips Report
    cur.execute("SELECT COUNT(*) AS c FROM trips WHERE Start_Date = CURDATE()")
    trips_today = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM trips WHERE YEARWEEK(Start_Date, 1) = YEARWEEK(CURDATE(), 1)")
    trips_week = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM trips WHERE MONTH(Start_Date) = MONTH(CURDATE()) AND YEAR(Start_Date) = YEAR(CURDATE())")
    trips_month = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM trips WHERE YEAR(Start_Date) = YEAR(CURDATE())")
    trips_year = cur.fetchone()['c']
    trips_data = [trips_today, trips_week, trips_month, trips_year]

    # 3. Vehicle Status
    cur.execute("SELECT Status, COUNT(*) AS count FROM vehicles GROUP BY Status")
    v_stats_rows = cur.fetchall()
    v_stats = {r['Status']: r['count'] for r in v_stats_rows}
    vehicle_data = [v_stats.get('available', 0), v_stats.get('in_use', 0), v_stats.get('maintenance', 0)]

    # 4. Consignment Status
    cur.execute("SELECT status, COUNT(*) AS count FROM consignments GROUP BY status")
    c_stats_rows = cur.fetchall()
    c_stats = {r['status']: r['count'] for r in c_stats_rows}
    consignment_data = [c_stats.get('booked', 0), c_stats.get('in_transit', 0), c_stats.get('delivered', 0)]

    return render_template(
        "dashboard.html",
        vehicle_count=vehicle_count,
        trip_count=trip_count,
        consignment_count=consignment_count,
        payment_total=payment_total,
        revenue_data=revenue_data,
        trips_data=trips_data,
        vehicle_data=vehicle_data,
        consignment_data=consignment_data
    )


# -----------------------------
# VEHICLES LIST
# -----------------------------
@app.route("/vehicles")
@login_required
def vehicles():

    conn = dbconnect()
    cur = conn.cursor(dictionary=True, buffered=True)

    cur.execute('''
        SELECT 
            Vehicle_id AS id, 
            Registration_Number AS reg_no, 
            Capacity_Tons AS capacity, 
            Status AS status 
        FROM vehicles
    ''')

    vehicles = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("vehicles.html", vehicles=vehicles)


# -----------------------------
# ADD VEHICLE (POST)
# -----------------------------
@app.route("/add_vehicle", methods=["POST"])
@login_required
@role_required('admin', 'manager')
def add_vehicle():

    truck_no = request.form.get("truck_no")
    reg_no = request.form.get("reg_no")
    capacity = request.form.get("capacity")
    status = request.form.get("status")

    print("DATA:", truck_no, reg_no, capacity, status)  # ✅ DEBUG

    # ✅ CHECK EMPTY VALUES (CRITICAL)
    if not truck_no or not reg_no or not capacity:
        flash("All fields are required", "error")
        return redirect("/add_vehicle")

    # ✅ ENUM VALID
    valid_status = ['available', 'in_use', 'maintenance', 'inactive']
    if status not in valid_status:
        status = 'available'

    try:
        float(capacity)
    except ValueError:
        flash("Capacity must be a number", "error")
        return redirect("/add_vehicle")

    try:
        conn = dbconnect()
        cur = conn.cursor(buffered=True)

        # ✅ DUPLICATE TRUCK NUMBER
        cur.execute("SELECT 1 FROM vehicles WHERE Truck_Number=%s", (truck_no,))
        if cur.fetchone():
            cur.fetchall()
            flash("Truck number already exists", "error")
            return redirect("/add_vehicle")
        cur.fetchall()

        # ✅ DUPLICATE REG NO
        cur.execute("SELECT 1 FROM vehicles WHERE Registration_Number=%s", (reg_no,))
        if cur.fetchone():
            cur.fetchall()
            flash("Registration number already exists", "error")
            return redirect("/add_vehicle")
        cur.fetchall()

        # ✅ INSERT
        cur.execute("""
            INSERT INTO vehicles
            (Truck_Number, Registration_Number, Capacity_Tons, Status)
            VALUES (%s, %s, %s, %s)
        """, (truck_no, reg_no, capacity, status))

        conn.commit()
        flash("Vehicle added successfully", "success")

    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    finally:
        cur.close()
        conn.close()

    return redirect("/vehicles")


# -----------------------------
# EDIT VEHICLE
# -----------------------------
@app.route("/edit_vehicle/<int:id>", methods=["GET", "POST"])
@login_required
@role_required('admin', 'manager')
def edit_vehicle(id):
    print("Edit called:", id)

    conn = dbconnect()
    cur = conn.cursor(dictionary=True, buffered=True)

    if request.method == "POST":

        reg_no = request.form.get("reg_no")
        capacity = request.form.get("capacity")
        status = request.form.get("status")

        # Validation
        try:
            float(capacity)
        except ValueError:
            flash("Capacity must be a number", "error")
            return redirect(f"/edit_vehicle/{id}")

        try:
            # Check duplicate (excluding current)
            cur.execute("""
                SELECT 1 FROM vehicles 
                WHERE Registration_Number=%s AND Vehicle_id != %s
            """, (reg_no, id))

            if cur.fetchone():
                flash("Registration number already exists", "error")
                return redirect(f"/edit_vehicle/{id}")

            # Update
            cur.execute("""
                UPDATE vehicles 
                SET Registration_Number=%s, Capacity_Tons=%s, Status=%s 
                WHERE Vehicle_id=%s
            """, (reg_no, capacity, status, id))

            conn.commit()
            flash("Vehicle updated successfully", "success")
            return redirect("/vehicles")

        except Exception as e:
            flash(f"Error: {str(e)}", "error")
            return redirect(f"/edit_vehicle/{id}")

    # GET request
    cur.execute("SELECT * FROM vehicles WHERE Vehicle_id=%s", (id,))
    vehicle = cur.fetchone()

    if not vehicle:
        flash("Vehicle not found", "error")
        return redirect("/vehicles")

    cur.close()
    conn.close()

    return render_template("edit_vehicle.html", vehicle=vehicle)


# -----------------------------
# DELETE VEHICLE
# -----------------------------
@app.route("/delete_vehicle/<int:id>", methods=["GET"])
@login_required
@role_required('admin', 'manager')
def delete_vehicle(id):
    print("Delete called:", id)

    conn = dbconnect()
    cur = conn.cursor(buffered=True)

    try:
        # Check if used in trips
        cur.execute("SELECT 1 FROM trips WHERE Vehicle_id=%s", (id,))
        trip = cur.fetchone()

        if trip:
            # Soft delete
            cur.execute("""
                UPDATE vehicles 
                SET Status='inactive' 
                WHERE Vehicle_id=%s
            """, (id,))
            flash("Vehicle is assigned to trips, marked as inactive", "warning")

        else:
            # Hard delete
            cur.execute("DELETE FROM vehicles WHERE Vehicle_id=%s", (id,))
            flash("Vehicle deleted successfully", "success")

        conn.commit()

    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    finally:
        cur.close()
        conn.close()

    return redirect("/vehicles")


# -----------------------------
# ADD VEHICLE FORM (GET)
# -----------------------------
@app.route("/add_vehicle", methods=["GET"])
@login_required
@role_required('admin', 'manager')
def add_vehicle_form():
    return render_template("add_vehicle.html")



# -----------------------------
# DRIVERS
# -----------------------------

@app.route("/users")
@login_required
@role_required('admin', 'manager')
def users():
    user_type = request.args.get('type', 'driver') # default to driver

    # Managers cannot see other managers per user instruction
    if session.get('role') == 'manager' and user_type == 'manager':
        flash("You do not have permission to view management personnel.", "error")
        return redirect("/users?type=driver")

    conn = dbconnect()
    cur = conn.cursor(dictionary=True)
    data = []

    if user_type == 'driver':
        cur.execute("SELECT driver_id AS id, name, license_number AS license, phone, status FROM drivers")
        data = cur.fetchall()
    elif user_type == 'manager':
        cur.execute("SELECT User_id AS id, CONCAT(First_name, ' ', Last_name) AS name, Email AS email, Phone AS phone, Status AS status FROM users WHERE Role='manager'")
        data = cur.fetchall()
    elif user_type == 'accountant':
        cur.execute("SELECT User_id AS id, CONCAT(First_name, ' ', Last_name) AS name, Email AS email, Phone AS phone, Status AS status FROM users WHERE Role='accountant'")
        data = cur.fetchall()

    return render_template("users.html", users_data=data, current_type=user_type)

@app.route("/add_driver", methods=["GET", "POST"])
@login_required
@role_required('admin', 'manager')
def add_driver():
    if request.method == "POST":
        name = request.form.get("name")
        license_number = request.form.get("license")
        phone = request.form.get("phone")
        status = request.form.get("status")

        # Validate phone
        if phone and not (phone.isdigit() and len(phone) == 10):
            flash("Phone number must contain exactly 10 digits.", "error")
            return redirect("/add_driver")

        try:
            conn = dbconnect()
            cur = conn.cursor()
            
            # Check duplicates
            cur.execute("SELECT * FROM drivers WHERE license_number=%s", (license_number,))
            if cur.fetchone():
                flash("Driver with this license number already exists. Please enter a unique value.", "error")
                return redirect("/add_driver")
            
            cur.execute("SELECT * FROM drivers WHERE phone=%s AND phone IS NOT NULL AND phone != ''", (phone,))
            if cur.fetchone():
                flash("Driver with this phone number already exists.", "error")
                return redirect("/add_driver")

            query = "INSERT INTO drivers(name, license_number, phone, status) VALUES(%s,%s,%s,%s)"
            cur.execute(query,(name, license_number, phone, status))
            conn.commit()
            flash("Driver added successfully", "success")
        except Exception as e:
            flash(f"Error adding driver: {str(e)}", "error")

        return redirect("/users?type=driver")
        
    return render_template("add_driver.html")

@app.route("/edit_driver/<id>", methods=["GET", "POST"])
@login_required
@role_required('admin', 'manager')
def edit_driver(id):
    conn = dbconnect()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form.get("name")
        license_number = request.form.get("license")
        phone = request.form.get("phone")
        status = request.form.get("status")

        if phone and not (phone.isdigit() and len(phone) == 10):
            flash("Phone number must contain exactly 10 digits.", "error")
            return redirect(f"/edit_driver/{id}")

        try:
            cur.execute("SELECT * FROM drivers WHERE license_number=%s AND driver_id != %s", (license_number, id))
            if cur.fetchone():
                flash("Driver with this license number already exists.", "error")
                return redirect(f"/edit_driver/{id}")

            cur.execute("SELECT * FROM drivers WHERE phone=%s AND phone IS NOT NULL AND phone != '' AND driver_id != %s", (phone, id))
            if cur.fetchone():
                flash("Driver with this phone number already exists.", "error")
                return redirect(f"/edit_driver/{id}")

            cur.execute("UPDATE drivers SET name=%s, license_number=%s, phone=%s, status=%s WHERE driver_id=%s",
                        (name, license_number, phone, status, id))
            conn.commit()
            flash("Driver updated successfully", "success")
            return redirect("/users?type=driver")
        except Exception as e:
            flash(f"Error updating driver: {str(e)}", "error")
            return redirect(f"/edit_driver/{id}")

    cur.execute("SELECT * FROM drivers WHERE driver_id=%s", (id,))
    driver = cur.fetchone()
    if not driver:
        flash("Driver not found", "error")
        return redirect("/users?type=driver")

    return render_template("edit_driver.html", driver=driver)


@app.route("/delete_driver/<id>")
@login_required
@role_required('admin', 'manager')
def delete_driver(id):
    conn = dbconnect()
    cur = conn.cursor()
    cur.execute("DELETE FROM drivers WHERE driver_id=%s",(id,))
    conn.commit()
    return redirect("/users?type=driver")

# -----------------------------
# SYSTEM USERS (MANAGERS/ACCOUNTANTS)
# -----------------------------

@app.route("/add_user", methods=["GET", "POST"])
@login_required
@role_required('admin')
def add_user():
    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        password = request.form.get("password")
        phone = request.form.get("phone")
        role = request.form.get("role")
        status = request.form.get("status")

        if role not in ['manager', 'accountant']:
            flash("Invalid role selected.", "error")
            return redirect("/add_user")

        if phone and not (phone.isdigit() and len(phone) == 10):
            flash("Phone number must contain exactly 10 digits.", "error")
            return redirect("/add_user")

        conn = dbconnect()
        cur = conn.cursor(dictionary=True)

        try:
            # Check for duplicate email
            cur.execute("SELECT * FROM users WHERE Email=%s", (email,))
            if cur.fetchone():
                flash("User with this email already exists.", "error")
                return redirect("/add_user")
            
            # Check for duplicate phone if provided
            if phone:
                cur.execute("SELECT * FROM users WHERE Phone=%s AND Phone IS NOT NULL AND Phone != ''", (phone,))
                if cur.fetchone():
                    flash("User with this phone number already exists.", "error")
                    return redirect("/add_user")

            query = "INSERT INTO users (First_name, Last_name, Email, Password, Role, Phone, Status) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cur.execute(query, (first_name, last_name, email, password, role, phone, status))
            conn.commit()
            flash(f"{role.capitalize()} added successfully", "success")
        except Exception as e:
            flash(f"Error adding user: {str(e)}", "error")
        return redirect(f"/users?type={role}")

    return render_template("add_user.html")


@app.route("/edit_user/<id>", methods=["GET", "POST"])
@login_required
@role_required('admin')
def edit_user(id):
    conn = dbconnect()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        # Ensure they don't overwrite the password if left blank (or omit for simplicity)
        password_update = request.form.get("password")
        phone = request.form.get("phone")
        role = request.form.get("role")
        status = request.form.get("status")

        if role not in ['manager', 'accountant']:
            flash("Invalid role selected.", "error")
            return redirect(f"/edit_user/{id}")

        if phone and not (phone.isdigit() and len(phone) == 10):
            flash("Phone number must contain exactly 10 digits.", "error")
            return redirect(f"/edit_user/{id}")

        try:
            cur.execute("SELECT * FROM users WHERE Email=%s AND User_id != %s", (email, id))
            if cur.fetchone():
                flash("User with this email already exists.", "error")
                return redirect(f"/edit_user/{id}")

            if phone:
                cur.execute("SELECT * FROM users WHERE Phone=%s AND Phone IS NOT NULL AND Phone != '' AND User_id != %s", (phone, id))
                if cur.fetchone():
                    flash("User with this phone number already exists.", "error")
                    return redirect(f"/edit_user/{id}")
            
            if password_update:
                cur.execute("UPDATE users SET First_name=%s, Last_name=%s, Email=%s, Password=%s, Role=%s, Phone=%s, Status=%s WHERE User_id=%s",
                            (first_name, last_name, email, password_update, role, phone, status, id))
            else:
                cur.execute("UPDATE users SET First_name=%s, Last_name=%s, Email=%s, Role=%s, Phone=%s, Status=%s WHERE User_id=%s",
                            (first_name, last_name, email, role, phone, status, id))
                
            conn.commit()
            flash(f"{role.capitalize()} updated successfully", "success")
            return redirect(f"/users?type={role}")
        except Exception as e:
            flash(f"Error updating user: {str(e)}", "error")
            return redirect(f"/edit_user/{id}")

    cur.execute("SELECT * FROM users WHERE User_id=%s", (id,))
    user_record = cur.fetchone()
    if not user_record:
        flash("User not found", "error")
        # Default redirect if role isn't known
        return redirect("/users?type=manager") 

    return render_template("edit_user.html", user=user_record)


@app.route("/delete_user/<id>")
@login_required
@role_required('admin')
def delete_user(id):
    conn = dbconnect()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT Role FROM users WHERE User_id=%s", (id,))
        user_record = cur.fetchone()
        
        # Guard against self-deletion ideally, but keep it simple for now as requested
        if str(id) == str(session.get('user_id')):
            flash("You cannot delete your own admin account.", "error")
            return redirect("/dashboard")

        if user_record:
            role = user_record['Role']
            cur.execute("DELETE FROM users WHERE User_id=%s", (id,))
            conn.commit()
            flash("User deleted successfully.", "success")
            return redirect(f"/users?type={role}")
            
    except Exception as e:
        flash(f"Error deleting user: {str(e)}", "error")
    
    return redirect("/users?type=manager")

# -----------------------------
# TRIPS
# -----------------------------

@app.route("/trips")
@login_required
def trips():

    conn = dbconnect()
    cur = conn.cursor(dictionary=True)

    cur.execute('''
        SELECT 
            t.Trip_id AS id, 
            d.name AS driver, 
            v.Truck_Number AS truck, 
            CONCAT(t.Route_From, " to ", t.Route_To) AS route, 
            t.Status AS status 
        FROM trips t
        LEFT JOIN drivers d ON t.Driver_id = d.driver_id
        LEFT JOIN vehicles v ON t.Vehicle_id = v.Vehicle_id
    ''')

    trips = cur.fetchall()

    return render_template("trips.html",trips=trips)


@app.route("/add_trip", methods=["GET", "POST"])
@login_required
@role_required('admin', 'manager')
def add_trip():
    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id")
        driver_id = request.form.get("driver_id")
        route_from = request.form.get("route_from")
        route_to = request.form.get("route_to")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        status = request.form.get("status", "pending")

        if end_date and start_date and start_date > end_date:
            flash("Start date must be before end date.", "error")
            return redirect("/add_trip")

        try:
            conn = dbconnect()
            cur = conn.cursor()
            query = "INSERT INTO trips(Vehicle_id, Driver_id, Route_From, Route_To, Start_Date, End_Date, Status) VALUES(%s,%s,%s,%s,%s,%s,%s)"
            cur.execute(query,(vehicle_id, driver_id, route_from, route_to, start_date, end_date or None, status))
            conn.commit()
            flash("Trip added successfully", "success")
        except Exception as e:
            flash(f"Error adding trip: {str(e)}", "error")
        return redirect("/trips")
        
    conn = dbconnect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM vehicles")
    vehicles = cur.fetchall()
    cur.execute("SELECT * FROM drivers")
    drivers = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("add_trip.html", vehicles=vehicles, drivers=drivers)

@app.route("/edit_trip/<id>", methods=["GET", "POST"])
@login_required
@role_required('admin', 'manager')
def edit_trip(id):
    conn = dbconnect()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id")
        driver_id = request.form.get("driver_id")
        route_from = request.form.get("route_from")
        route_to = request.form.get("route_to")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        status = request.form.get("status")

        if end_date and start_date and start_date > end_date:
            flash("Start date must be before end date.", "error")
            return redirect(f"/edit_trip/{id}")

        try:
            cur.execute("UPDATE trips SET Vehicle_id=%s, Driver_id=%s, Route_From=%s, Route_To=%s, Start_Date=%s, End_Date=%s, Status=%s WHERE Trip_id=%s",
                        (vehicle_id, driver_id, route_from, route_to, start_date, end_date or None, status, id))
            conn.commit()
            flash("Trip updated successfully", "success")
            return redirect("/trips")
        except Exception as e:
            flash(f"Error updating trip: {str(e)}", "error")
            return redirect(f"/edit_trip/{id}")

    cur.execute("SELECT * FROM trips WHERE Trip_id=%s", (id,))
    trip = cur.fetchone()
    if not trip:
        flash("Trip not found", "error")
        return redirect("/trips")

    cur.execute("SELECT * FROM drivers")
    drivers = cur.fetchall()
    cur.execute("SELECT * FROM vehicles")
    vehicles = cur.fetchall()

    return render_template("edit_trip.html", trip=trip, drivers=drivers, vehicles=vehicles)


@app.route("/delete_trip/<id>")
@login_required
@role_required('admin', 'manager')
def delete_trip(id):
    try:
        conn = dbconnect()
        cur = conn.cursor()
        cur.execute("DELETE FROM trips WHERE Trip_id=%s",(id,))
        conn.commit()
        flash("Trip deleted successfully", "success")
    except Exception as e:
        flash(f"Error deleting trip: {str(e)}", "error")
    return redirect("/trips")

# -----------------------------
# CONSIGNMENTS
# -----------------------------

@app.route("/consignments")
@login_required
def consignments():

    conn = dbconnect()
    cur = conn.cursor(dictionary=True)

    cur.execute('''
        SELECT 
            c.Consignments_id AS id, 
            c.Sender_name AS sender, 
            c.Receiver_name AS receiver, 
            CONCAT(t.Route_From, " to ", t.Route_To) AS route, 
            c.status AS status 
        FROM consignments c
        LEFT JOIN trips t ON c.trip_id = t.Trip_id
    ''')

    consignments = cur.fetchall()

    return render_template("consignments.html",consignments=consignments)


@app.route("/add_consignment", methods=["GET", "POST"])
@login_required
@role_required('admin', 'manager')
def add_consignment():
    if request.method == "POST":
        trip_id = request.form.get("trip_id")
        
        # Handle optional trip assignations (convert '' to None for MySQL INT columns)
        if not trip_id or trip_id.strip() == "":
            trip_id = None
            
        sender = request.form.get("sender")
        receiver = request.form.get("receiver")
        goods_type = request.form.get("goods_type")
        weight = request.form.get("weight")
        amount = request.form.get("amount")
        status = request.form.get("status", "booked")

        try:
            conn = dbconnect()
            cur = conn.cursor()
            query = "INSERT INTO consignments(trip_id, Sender_name, Receiver_name, Goods_type, Weight_tone, Freight_Amount, status) VALUES(%s,%s,%s,%s,%s,%s,%s)"
            cur.execute(query,(trip_id, sender, receiver, goods_type, weight, amount, status))
            conn.commit()
            flash("Consignment added successfully", "success")
        except Exception as e:
            flash(f"Error adding consignment: {str(e)}", "error")
        return redirect("/consignments")

    conn = dbconnect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM trips")
    trips = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("add_consignment.html", trips=trips)

@app.route("/edit_consignment/<id>", methods=["GET", "POST"])
@login_required
@role_required('admin', 'manager')
def edit_consignment(id):
    conn = dbconnect()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        trip_id = request.form.get("trip_id")
        
        if not trip_id or trip_id.strip() == "":
            trip_id = None
            
        sender = request.form.get("sender")
        receiver = request.form.get("receiver")
        goods_type = request.form.get("goods_type")
        weight = request.form.get("weight")
        amount = request.form.get("amount")
        status = request.form.get("status")

        try:
            cur.execute("UPDATE consignments SET trip_id=%s, Sender_name=%s, Receiver_name=%s, Goods_type=%s, Weight_tone=%s, Freight_Amount=%s, status=%s WHERE Consignments_id=%s",
                        (trip_id, sender, receiver, goods_type, weight, amount, status, id))
            conn.commit()
            flash("Consignment updated successfully", "success")
            return redirect("/consignments")
        except Exception as e:
            flash(f"Error updating consignment: {str(e)}", "error")
            return redirect(f"/edit_consignment/{id}")

    cur.execute("SELECT * FROM consignments WHERE Consignments_id=%s", (id,))
    consignment = cur.fetchone()
    if not consignment:
        flash("Consignment not found", "error")
        return redirect("/consignments")

    cur.execute("SELECT * FROM trips")
    trips = cur.fetchall()
    
    cur.close()
    conn.close()

    return render_template("edit_consignment.html", consignment=consignment, trips=trips)


@app.route("/delete_consignment/<id>")
@login_required
@role_required('admin', 'manager')
def delete_consignment(id):
    conn = dbconnect()
    cur = conn.cursor()
    cur.execute("DELETE FROM consignments WHERE Consignments_id=%s",(id,))
    conn.commit()
    return redirect("/consignments")

# -----------------------------
# PAYMENTS
# -----------------------------

@app.route("/payments")
@login_required
def payments():

    conn = dbconnect()
    cur = conn.cursor(dictionary=True)

    cur.execute('''
        SELECT 
            Payment_id AS id, 
            Consignment_id AS trip_id, 
            Amount AS amount, 
            status AS status 
        FROM payments
    ''')

    payments = cur.fetchall()

    return render_template("payments.html",payments=payments)


@app.route("/add_payment", methods=["GET", "POST"])
@login_required
@role_required('admin', 'accountant')
def add_payment():
    if request.method == "POST":
        consignment_id = request.form.get("consignment_id")
        amount = request.form.get("amount")
        method = request.form.get("method")
        payment_date = request.form.get("payment_date")
        reference = request.form.get("reference")
        status = request.form.get("status", "completed")

        try:
            conn = dbconnect()
            cur = conn.cursor()
            query = "INSERT INTO payments(Consignment_id, Amount, method, Payment_date, Reference_no, status) VALUES(%s,%s,%s,%s,%s,%s)"
            cur.execute(query,(consignment_id, amount, method, payment_date, reference, status))
            conn.commit()
            flash("Payment added successfully", "success")
        except Exception as e:
            flash(f"Error adding payment: {str(e)}", "error")
        return redirect("/payments")

    conn = dbconnect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM consignments")
    consignments = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("add_payment.html", consignments=consignments)

@app.route("/edit_payment/<id>", methods=["GET", "POST"])
@login_required
@role_required('admin', 'accountant')
def edit_payment(id):
    conn = dbconnect()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        amount = request.form.get("amount")
        method = request.form.get("method")
        payment_date = request.form.get("payment_date")
        reference = request.form.get("reference")
        status = request.form.get("status")

        try:
            cur.execute("UPDATE payments SET Amount=%s, method=%s, Payment_date=%s, Reference_no=%s, status=%s WHERE Payment_id=%s",
                        (amount, method, payment_date, reference, status, id))
            conn.commit()
            flash("Payment updated successfully", "success")
            return redirect("/payments")
        except Exception as e:
            flash(f"Error updating payment: {str(e)}", "error")
            return redirect(f"/edit_payment/{id}")

    cur.execute("SELECT * FROM payments WHERE Payment_id=%s", (id,))
    payment = cur.fetchone()
    if not payment:
        flash("Payment not found", "error")
        return redirect("/payments")

    return render_template("edit_payment.html", payment=payment)


@app.route("/delete_payment/<id>")
@login_required
@role_required('admin', 'accountant')
def delete_payment(id):
    conn = dbconnect()
    cur = conn.cursor()
    cur.execute("DELETE FROM payments WHERE Payment_id=%s",(id,))
    conn.commit()
    return redirect("/payments")

# -----------------------------
# PROFILE
# -----------------------------

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    conn = dbconnect()
    cur = conn.cursor(dictionary=True)
    
    if request.method == "POST":
        import base64
        
        # Handle camera capture base64 upload
        if 'captured_image' in request.form and request.form['captured_image']:
            img_data = request.form['captured_image']
            if img_data.startswith('data:image'):
                img_data = img_data.split(',')[1]  # Remove data:image/png;base64,
                
            img_bytes = base64.b64decode(img_data)
            new_filename = f"user_{session.get('user_id')}_cam.png"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            
            with open(filepath, 'wb') as f:
                f.write(img_bytes)
                
            # Update database
            cur.execute("UPDATE users SET Profile_pic=%s WHERE User_id=%s", (new_filename, session.get('user_id')))
            conn.commit()
            
            # Update session
            session['profile_pic'] = new_filename
            flash("Profile picture updated successfully!", "success")
            return redirect("/profile")
            
        # Handle regular file upload
        elif 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                # Create unique filename
                ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                new_filename = f"user_{session.get('user_id')}.{ext}"
                
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                file.save(filepath)
                
                # Update database
                cur.execute("UPDATE users SET Profile_pic=%s WHERE User_id=%s", (new_filename, session.get('user_id')))
                conn.commit()
                
                # Update session
                session['profile_pic'] = new_filename
                flash("Profile picture updated successfully!", "success")
                return redirect("/profile")

    cur.execute("SELECT * FROM users WHERE User_id=%s", (session.get("user_id"),))
    user = cur.fetchone()
    
    # Store profile_pic in session if missing
    if user and user.get('Profile_pic'):
        session['profile_pic'] = user['Profile_pic']
        
    return render_template("profile.html", user=user)

# -----------------------------
# RUN SERVER
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True)