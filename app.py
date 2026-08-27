import os
from datetime import datetime,timezone,date
from flask import Flask,Response, request, render_template_string, redirect, url_for, flash, render_template, jsonify,json
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy import create_engine, text,cast,Date,func,case
from flask_migrate import Migrate
#import uui
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import math
#from weasyprint import HTML
#import pdfkit
from functools import wraps

#from flask import Flask, render_template, request, redirect, url_for, flash
#from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin
#from werkzeug.security import check_password_hash

#from flask import Blueprint, jsonify, request
#from sqlalchemy import func
#from yourapp.models import WarehouseTransactions, User, Branch
#from yourapp.extensions import db
#import subprocess

#bp = Blueprint("warehouse", __name__)

app = Flask(__name__)
app.secret_key = "super_secret_key"  # required for flash/session

# Secret token for init route (set in Render Environment tab)
INIT_SECRET = os.environ.get("INIT_SECRET", "changeme")

# Get DB URL from environment
db_url = os.environ.get("DATABASE_URL")

# Fallback for local dev
if not db_url:
  #db_url = "sqlite:///local.db"
  # Use SQL Server locally
  db_url = (
      "mssql+pyodbc:///?odbc_connect="
      "DRIVER={ODBC Driver 17 for SQL Server};"
      "SERVER=TOSHIBA\\SQLEXP2014;"
      "DATABASE=YbeautyRegister;"
      "UID=sa;"
      "PWD=CMos@2019"
  )

# Fix Render’s default prefix if needed
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)


# External SQL Server connection
external_engine = create_engine(
    "mssql+pyodbc:///?odbc_connect="
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=tundagreen.aceplasticsafrica.com;"
    "DATABASE=ACELIVEDATA;"
    "UID=Usertunda;"
    "PWD=Tunda@2024"
)

# Apply config
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)
migrate = Migrate(app, db)


# Import models AFTER db is defined
#import models
# --- Models ---
#class Outlet(db.Model):
#    __tablename__ = 'outlet'
#    id = db.Column(db.Integer, primary_key=True)   # internal PK
#    outlet_id = db.Column(db.Integer, nullable=False, unique=True)
#    name = db.Column(db.String(255), nullable=False)

class Outlet(db.Model):
    __tablename__ = 'outlet'

    # Primary keys and identifiers
    id = db.Column(db.Integer, primary_key=True)   # internal PK
    outlet_id = db.Column(db.Integer, nullable=False, unique=True)  # business ID
    name = db.Column(db.String(255), nullable=False)

    # Location details
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # Operational details
    address = db.Column(db.String(255), nullable=True)
    clock_in_radius = db.Column(db.Integer, default=50)  # meters

    # Relationships
    user_id = db.Column(db.Integer, nullable=True)
    #user = db.relationship('User', backref='outlets')

    # Audit fields
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f"<Outlet {self.name} ({self.outlet_id})>"


class Users(db.Model,UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    staff_name = db.Column(db.String(100), unique=True, nullable=False) #name
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True) #status
    email = db.Column(db.String(120), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    role = db.Column(db.Integer, nullable=True) # e.g. 1 for superadmin,2 for admin,3 for manager,4 for supervisor,5 for Staff
    privileges = db.Column(db.Integer, nullable=True)  # e.g. 1 for static 2 for reliever 
    base_salary = db.Column(db.Float, nullable=True)  # monthly salary
    hire_date = db.Column(db.Date, nullable=True)
    

    attendances = db.relationship("Attendance", backref="user", lazy=True)
    payrolls = db.relationship("Payroll", backref="user", lazy=True)
    leaves = db.relationship("Leave", backref="user", lazy=True)

    #def __repr__(self):
    #    return f"<User {self.staff_name}>"
    def __repr__(self):
        return f"<User {self.id} - {self.staff_name}>"

class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    date = db.Column(db.Date, nullable=False)
    check_in_time = db.Column(db.DateTime, nullable=True)
    check_out_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default="Present")
    #distance = db.Column(db.Float, nullable=True)
    # Renamed field
    clockin_distance = db.Column(db.Float, nullable=True)
    # New field
    clockout_distance = db.Column(db.Float, nullable=True)
    work_hours = db.Column(db.Float, nullable=True)
    overtime_hours = db.Column(db.Float, nullable=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=True)

    geo_lat = db.Column(db.Float, nullable=True)
    geo_lon = db.Column(db.Float, nullable=True)
    device_info = db.Column(db.String(100), nullable=True)
    remarks = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, default=db.func.now(),
                           onupdate=db.func.now(), nullable=False)

class Shift(db.Model):
    __tablename__ = "shifts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    overtime_rate = db.Column(db.Float, nullable=True)

    attendances = db.relationship("Attendance", backref="shift", lazy=True)

class Leave(db.Model):
    __tablename__ = "leave"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False)   # Sick, Annual, Unpaid
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    approved_by = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default="Pending")    # Pending, Approved, Rejected

class Payroll(db.Model):
    __tablename__ = "payroll"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)

    base_salary = db.Column(db.Float, nullable=False)
    daily_rate = db.Column(db.Float, nullable=True)
    overtime_pay = db.Column(db.Float, nullable=True)
    deductions = db.Column(db.Float, nullable=True)
    bonuses = db.Column(db.Float, nullable=True)

    gross_salary = db.Column(db.Float, nullable=False)
    net_salary = db.Column(db.Float, nullable=False)

    generated_at = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    approved_by = db.Column(db.String(50), nullable=True)
    remarks = db.Column(db.Text, nullable=True)


class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    whrsh_outlets_id = db.Column(db.Integer, nullable=False)  # just a plain field

    good_crates = db.Column(db.Integer, default=0)
    worn_crates = db.Column(db.Integer, default=0)
    disposed_crates = db.Column(db.Integer, default=0)
    dispatched_crates = db.Column(db.Integer, default=0)
    collected_crates = db.Column(db.Integer, default=0)
    total_crates = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"<Warehouse {self.name}>"


class WarehouseTransaction(db.Model):
    __tablename__ = 'warehouse_transactions'
    id = db.Column(db.Integer, primary_key=True)
    wrhse_outlet_id = db.Column(db.Integer, nullable=False)  # just a plain field

    transaction_type = db.Column(db.String(50), nullable=False)
    good_crates = db.Column(db.Integer, default=0)
    worn_crates = db.Column(db.Integer, default=0)
    disposed_crates = db.Column(db.Integer, default=0)
    notes = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=db.func.now())
    staff_name = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<WarehouseTransaction {self.transaction_type} for Outlet {self.wrhse_outlet_id}>"

class EndDayLog(db.Model):
    __tablename__ = "end_day_logs"

    id = db.Column(db.Integer, primary_key=True)
    #warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouse.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, nullable=False) 
    dispatched_crates = db.Column(db.Integer, nullable=False)
    app_collections = db.Column(db.Integer, nullable=False)
    physical_crates = db.Column(db.Integer, nullable=False)
    variance = db.Column(db.Integer, nullable=False)
    staff_name = db.Column(db.String(100), nullable=False)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.now())

    #warehouse = db.relationship("Warehouse", backref="end_day_logs")

ROLE_LABELS = {
    1: "Super Admin",
    2: "Admin",
    3: "Manager",
    4: "Supervisor",
    5: "Staff"
}

PRIVILEGE_LABELS = {
    1: "All",
    2: "Sup",
    3: "Reg"
}

# Secure one-time init route
# Example to create all tables manually: http://127.0.0.1:10000/init-db?token=changeme
@app.route("/init-db")
def init_db():
    token = request.args.get("token")
    if token != INIT_SECRET:
        return "Unauthorized", 403

    with app.app_context():
        # Ensure tables exist
        db.create_all()

        from sqlalchemy import text
        try:
            # Safely drop column 'inactive' by removing its default constraint first
            db.session.execute(text("""
            -- Insert default SUPER_ADMINISTRATOR account if not already present
            IF NOT EXISTS (
                SELECT 1 FROM users WHERE username = 'SP_ADMIN'
                )
                BEGIN
                    INSERT INTO users (
                        staff_name,
                        username,
                        password_hash,
                        is_active,
                        email,
                        department,
                        role,
                        privileges,
                        base_salary,
                        hire_date
                    )
                    VALUES (
                        'SUPER_ADMINISTRATOR',   -- staff_name
                        'SP_ADMIN',              -- username
                        'scrypt:32768:8:1$HwXmeq1EUpSyRCSI$9f1ab94b977f3dd9827e68aaecc34464ffd0f2051f3d0ac74b2c8560b117ce115da3825c672d49e8ba5713e22b65ffb4b0923a7e78068cb91df8439c58fe01fc', -- password_hash (replace with hashed value!= 1234)
                        1,                       -- is_active
                        'admin@system.com',      -- email
                        'Administration',        -- department
                        1,                 -- role
                        1,                   -- privileges
                        2000,                    -- base_salary
                        '2026-08-01'             -- hire_date
                    );
                END
            """))
            db.session.commit()

            # Add privilege columns if missing
            privilege_columns = [
                ("suspended", "BIT", "0"),
                ("feed_entries", "BIT", "0"),
                ("amend_entry", "BIT", "0"),
                ("provision1", "BIT", "0"),
                ("provision2", "BIT", "0"),
                ("provision3", "BIT", "0"),
                ("provision4", "BIT", "0"),
                ("provision5", "BIT", "0"),
                ("provision6", "BIT", "0"),
                ("provision7", "BIT", "0"),
                ("provision8", "BIT", "0"),
                ("provision9", "BIT", "0"),
            ]

            for col_name, col_type, default in privilege_columns:
                db.session.execute(text(f"""
                    IF NOT EXISTS (
                        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_NAME = 'users' AND COLUMN_NAME = '{col_name}'
                    )
                    ALTER TABLE users ADD {col_name} {col_type}
                    CONSTRAINT DF_users_{col_name} DEFAULT {default} NOT NULL;
                """))

            db.session.commit()

            # Add username column with default if missing
            db.session.execute(text("""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'username'
                )
                ALTER TABLE users ADD username NVARCHAR(80)
                CONSTRAINT DF_users_username DEFAULT 'tempuser' NOT NULL;
            """))

            # Add password_hash column with default if missing
            db.session.execute(text("""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'password_hash'
                )
                ALTER TABLE users ADD password_hash NVARCHAR(200)
                CONSTRAINT DF_users_password_hash DEFAULT 'changeme' NOT NULL;
            """))

            # Add status column with default if missing
            db.session.execute(text("""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'status'
                )
                ALTER TABLE users ADD status INT
                CONSTRAINT DF_users_status DEFAULT 1 NOT NULL;
            """))

            # Rename column 'inactive' to 'suspended' if it exists
            db.session.execute(text("""
                IF EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'inactive'
                )
                AND NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'suspended'
                )
                BEGIN
                    EXEC sp_rename 'users.inactive', 'suspended', 'COLUMN';
                END
            """))
            db.session.commit()

            # Safely drop column 'inactive' by removing its default constraint first
            db.session.execute(text("""
                DECLARE @ConstraintName NVARCHAR(200);

                -- Find the default constraint bound to 'inactive'
                SELECT @ConstraintName = dc.name
                FROM sys.default_constraints dc
                INNER JOIN sys.columns c ON c.default_object_id = dc.object_id
                INNER JOIN sys.tables t ON t.object_id = c.object_id
                WHERE t.name = 'users' AND c.name = 'inactive';

                -- Drop the constraint if found
                IF @ConstraintName IS NOT NULL
                BEGIN
                    EXEC('ALTER TABLE users DROP CONSTRAINT ' + @ConstraintName);
                END

                -- Now drop the column if it exists
                IF EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'inactive'
                )
                BEGIN
                    ALTER TABLE users DROP COLUMN inactive;
                END
            """))
            db.session.commit()


        except Exception as e:
            db.session.rollback()
            return f"Error altering table: {e}", 500

    return "Tables created and altered successfully!"

def run_enviroment_for_app_debbug():
    #1.cd C:\Users\Admin\crate-tracker\backend_for_web
    #2.venv\Scripts\Activate.ps1
    #3.python app.py or your app.py_name run
    print("terminal_process")

def push_to_github():
    #Nb.you should be here
    #(venv) PS C:\Users\Admin\crate-tracker\backend_for_web>

    # 1. Initialize Git in your project folder (only once)
    #git init

    # 2. Add your remote GitHub repository
    # Replace with your actual repo URL
    #git remote add origin https://github.com/your-username/your-repo.git
    #my correct path
    #git remote set-url origin https://github.com/mutumagitonga0-dot/tgl_crates_issuance_n_tracking.git"

    # 3. Stage all files (prepare them for commit)
    #git add .

    # 4. Commit your changes with a message
    #git commit -m "Initial commit or update backend code" 

    # 5. Push to GitHub
    # First push (sets branch name and upstream)
    #git branch -M main
    #git push -u origin main


    # upload any change Subsequent pushes (after making new changes)
    #git add .
    #git commit -m "Describe your changes here"
    #git push
    print("github_process")

def connect_sqlalchemy_database_through_cmd():
    # Path to your psql.exe
    psql_path = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"
    
    # Full connection string
    conn_str = "postgresql://tgl_crates_db_user:Vk1PPiktlT6aktTgzdCCNkQZZFfLeiX5@dpg-d6uodkchg0os73f4kql0-a.oregon-postgres.render.com/tgl_crates_db"
    
    #full cmd string 
    cmd_str = r"C:\Program Files\PostgreSQL\18\bin\psql.exe" "postgresql://tgl_crates_db_user:Vk1PPiktlT6aktTgzdCCNkQZZFfLeiX5@dpg-d6uodkchg0os73f4kql0-a.oregon-postgres.render.com/tgl_crates_db"
    # Run the command


    #if this error : ERROR:  character with byte sequence 0xe2 0x80 0x91 in encoding "UTF8" has no equivalent in encoding "WIN1252"
    #run this line \encoding UTF8
    
    # run this \x 
    # This shows each row with column names and values vertically. 

    #run \pset tuples_only off
    #That command tells psql to include column headers. If tuples_only is set to on, headers are hidden.

    #run  \x auto
    #This will switch between table and expanded view depending on row width, always showing headers.
    
    
    #subprocess.run([psql_path, conn_str])


@app.route("/github_instructions")
def github_instructions():
    return f"<pre>{github_upload_instructions()}</pre>"

## --- Routes ---
#@app.route("/", methods=["GET", "POST"])
#def login():
#    if request.method == "POST":
#        username = request.form["username"]
#        password = request.form["password"]
#        # Replace with proper authentication logic
#        if username == "admin" and password == "secret":
#            #return redirect(url_for("dashboard"))
#            return redirect(url_for("home"))
#        else:
#            flash("Invalid credentials, please try again.", "danger")
#    return render_template("login.html")

# --- CONFIG ---
#SITE_LAT = -1.221770 # -1.2921   # Example: Nairobi CBD
#SITE_LON =  36.880007 #36.8219
#CLOCKIN_RADIUS = 50 #3  #For an office attendance system, a 50 m radius is usually safe. It avoids false negatives from small coordinate shifts but still prevents clock‑ins from far away.

# --- UTILS ---
def preserve_this_haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


from math import radians, sin, cos, sqrt, atan2
def haversine(lat1, lon1, lat2, lon2):
    # Earth radius in meters
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def update_user_password(username: str, plain_password: str) -> bool:
    """
    Hashes a plain password and updates the given user's record.
    Returns True if successful, False if user not found.
    """
    user = Users.query.filter_by(username=username).first()
    if not user:
        return False
    
    user.password_hash = generate_password_hash(plain_password)
    db.session.commit()
    return True

#@app.route("/", methods=["GET", "POST"])
def no_warnings_login():
    if request.method == "POST":
        #username = request.form["username"]
        username = request.form["username"].lower()
        password = request.form["password"]
        print(username,password)
        user = Users.query.filter_by(username=username).first()
        
        # Update Admin user
        #success = update_user_password("tempuser", "changeme")
        #if success:
        #    print("Password updated and hashed successfully.")
        #else:
        #    print("User not found.")
        if user and not user.is_active: #it was if suspended
            flash("You are currently suspended login into system, please contact your admin.", "danger")    
        elif user and check_password_hash(user.password_hash, password):
            print(user)
            print(user.role)
            login_user(user)
            #return redirect(url_for("home"))
            return redirect(url_for("dashboard"))
            #return render_template("dashboard.html")
        else:
            #print(generate_password_hash("1234"))
            flash("Invalid credentials, please try again.", "danger")

    return render_template("login.html")


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]
        print(username, password)

        user = Users.query.filter_by(username=username).first()

        if user and not user.is_active:
            return jsonify({
                "status": "error",
                "message": "⚠️ You are currently suspended. Please contact your admin."
            }), 400

        elif user and check_password_hash(user.password_hash, password):
            login_user(user, remember="remember" in request.form)
            return jsonify({
                "status": "success",
                "message": "✅ Login successful",
                "redirect": url_for("dashboard")   # ✅ include redirect target
            }), 200

        else:
            return jsonify({
                "status": "error",
                "message": "⚠️ Invalid credentials, please try again."
            }), 400

    return render_template("login.html")


@app.route("/profile")
@login_required
def profile():
    # Example attendance summary (replace with DB queries)
    attendance = {
        "present": Attendance.query.filter_by(user_id=current_user.id, status="Present").count(),
        "absent": Attendance.query.filter_by(user_id=current_user.id, status="Absent").count(),
        "late": Attendance.query.filter_by(user_id=current_user.id, status="Late").count()
    }

    # Example leave balance (replace with DB queries)
    leave = {
        "annual": 12,  # Example static value
        "sick": 5
    }
    user_id=current_user.id
    #token = serializer.dumps(user_id, salt="password-reset-salt")
    token = serializer.dumps(user_id, salt="password-reset")
    return render_template("profile.html",
                           attendance=attendance,
                           token=token,
                           outletname=get_current_user_outlet(),
                           leave=leave)

@app.route("/logout")
@login_required
def logout():
    # End the user session
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    #return Users.query.get(int(user_id))
    return db.session.get(Users, int(user_id))
    

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            flash("Access denied: Admins only", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/employees')
@login_required
@admin_required
def employees():
    return render_template('admin/employees.html')


def get_current_user_outlet():
   outlet = Outlet.query.filter_by(user_id=current_user.id).first()
   if outlet:
    user_outlet = outlet.name
   else:
    user_outlet = "None"
   return (user_outlet)    
    
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    #summary = get_today_summary(current_user.id)
    #return jsonify(summary)   # or render_template("home.html", summary=summary)
    # Find outlet attached to current user
    #outlet = Outlet.query.filter_by(user_id=current_user.id).first()

    #if outlet:
    #    outletname = outlet.name
    #else:
    #    outletname = "None"

    return render_template("dashboard.html",outletname=get_current_user_outlet())
    

# --- ROUTES ---
@app.route("/clockin", methods=["POST"])
@login_required
def clock_in():

    ok, error_response, distance, user_lat, user_lon,outletname = checkif_any_existing_login_onloading()
    if not ok:
        return error_response
    
    # Step 1: Get outlet attached to current user
    #outlet = Outlet.query.filter_by(user_id=current_user.id).first()
    #if not outlet:
    #    return jsonify({"error": "No outlet assigned to this user"}), 400

    # Step 2: Calculate distance between user location and outlet location
    #outlet_lat = float(outlet.latitude)
    #outlet_lon = float(outlet.longitude)
    #outlet_radius = float(outlet.radius)  # radius in meters

    #distance = haversine(user_lat, user_lon, outlet_lat, outlet_lon)

    #if distance > outlet_radius:
    #    return jsonify({
    #        "error": f"You are not within the required outlet area. "
    #                 f"Outlet: {outlet.name}, Address: {outlet.address}, "
    #                 f"Distance: {distance:.2f}m (allowed radius {outlet_radius}m)"
    #    }), 400

    


    # Step 3: Record clock-in
    check_in_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Get outlet attached to current user
    outlet = Outlet.query.filter_by(user_id=current_user.id).first()

    record = Attendance(
        user_id=current_user.id,
        date=date.today(),
        check_in_time=check_in_time,
        check_out_time=None,
        status="Present",
        clockin_distance=distance,
        geo_lat=user_lat,
        geo_lon=user_lon,
        device_info="PC",
        remarks=None,
        outlet_id=outlet.id if outlet else None,
        outlet_name=outlet.name if outlet else "None"
        #outlet_address=outlet.address if outlet else "None"
    )
    db.session.add(record)
    db.session.commit()


    summary = get_today_summary(current_user.id)
    return jsonify({
        "success": f"Clock-in successful at {check_in_time}, "
                   f"{distance:.2f}m from {outletname}",
        "summary": summary
    })

@app.route("/clockout", methods=["POST"])
@login_required
def clock_out():
    data = request.json
    user_lat = data.get("latitude")
    user_lon = data.get("longitude")

    if not user_lat or not user_lon:
        return jsonify({"error": "Location required"}), 400

    # Step 1: Get outlet attached to current user
    outlet = Outlet.query.filter_by(user_id=current_user.id).first()
    if not outlet:
        return jsonify({"error": "No outlet assigned to this user"}), 400

    outlet_lat = float(outlet.latitude)
    outlet_lon = float(outlet.longitude)
    outlet_radius = float(outlet.clock_in_radius)  # radius in meters

    # Step 2: Calculate distance from outlet
    distance = haversine(float(user_lat), float(user_lon), outlet_lat, outlet_lon)

    if distance > outlet_radius:
        return jsonify({
            "error": f"You are not within the required outlet area to clock out. "
                     f"Outlet: {outlet.name}, Location: {outlet.address}, "
                     f"Distance: {distance:.2f}m (allowed radius {outlet_radius}m)"
        }), 403

    # Step 3: Get the last attendance record
    last_record = Attendance.query.filter_by(user_id=current_user.id)\
                                  .order_by(Attendance.id.desc())\
                                  .first()

    if not last_record or last_record.check_out_time is not None:
        return jsonify({"error": "You are not currently clocked in. Please check in first"}), 403

    # Step 4: Update with check-out time
    check_out_time = datetime.now().replace(second=0, microsecond=0)
    last_record.check_out_time = check_out_time
    last_record.clockout_distance = distance

    # Attach outlet info for reporting
    outlet = Outlet.query.filter_by(user_id=current_user.id).first()
    if outlet:
        last_record.outlet_id = outlet.id
        last_record.outlet_name = outlet.name
        #last_record.outlet_address = outlet.address
    else:
        last_record.outlet_id = None
        last_record.outlet_name = "None"
        #last_record.outlet_address = "None"

    # Step 5: Calculate work hours
    if last_record.check_in_time:
        delta = check_out_time - last_record.check_in_time
        hours_worked = round(delta.total_seconds() / 3600, 2)
        last_record.work_hours = hours_worked

        # Optional overtime
        last_record.overtime_hours = max(0, hours_worked - 8)
    db.session.commit()


    summary = get_today_summary(current_user.id)
    return jsonify({
        "success": f"Clocked out {check_out_time.strftime('%Y-%m-%d %H:%M')} successfully "
                   f"at {distance:.2f}m from {outlet.name}, worked {last_record.work_hours:.2f} hrs",
        "summary": summary
    })


@app.route("/static_clockin", methods=["POST"])
#@app.route("/clockin", methods=["POST"])
@login_required
def static_clock_in():

    ok, error_response, distance, user_lat, user_lon = checkif_any_existing_login_onloading()
    print(ok)
    if not ok:
        #print(error_response,"this?")
        return error_response
        

    #check_in_time=datetime.now()
    check_in_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("display time before inserting record")
    
    # Step 3: Otherwise, insert a new record
    record = Attendance(
        user_id=current_user.id,
        date=date.today(),                   # record the day
        check_in_time=check_in_time,     # when they clocked in
        check_out_time=None,
        status="Present",
        clockin_distance=distance,
        geo_lat=user_lat,
        geo_lon=user_lon,
        device_info="PC",                     # optional metadata
        remarks=None
    )
    db.session.add(record)
    db.session.commit()
    summary = get_today_summary(current_user.id)
    #return jsonify({"success": "Clock-in successful", "summary": summary})
    return jsonify({"success": f"Fantastic!!! Clock-in {check_in_time} successfully at {distance:.2f}mtrs away of site","summary": summary})

def checkif_any_existing_login_onloading():
    data = request.json
    user_lat = data.get("latitude")
    print("user_lat",user_lat)
    user_lon = data.get("longitude")
    print("user_lon",user_lon)

    if not user_lat or not user_lon:
        return False, jsonify({"error": "Location required"}), None, None, None,None

    # Step 1: Get outlet attached to current user
    outlet = Outlet.query.filter_by(user_id=current_user.id).first()
    if not outlet:
        return False, jsonify({"error": "No outlet assigned to this user"}), None, None, None,None

    outlet_lat = float(outlet.latitude)
    outlet_lon = float(outlet.longitude)
    outlet_radius = float(outlet.clock_in_radius)  # radius in meters
    outletname= outlet.name
    print(outletname)

    # Step 2: Calculate distance from outlet
    distance = haversine(float(user_lat), float(user_lon), outlet_lat, outlet_lon)

    if distance > outlet_radius:
        return False, jsonify({
            "error": f"You are not within the required outlet area. "
                     f"Outlet: {outlet.name}, Location: {outlet.address}, "
                     f"Distance: {distance:.2f}m (allowed radius {outlet_radius}m)"
        }), None, None, None,None

    # Step 3: Check if user already has an active clock-in
    last_record = Attendance.query.filter_by(user_id=current_user.id)\
                                  .order_by(Attendance.id.desc())\
                                  .first()
    if last_record and last_record.check_out_time is None:
        return False, jsonify({
            "error": f"You are already clocked in since {last_record.check_in_time}. "
                     f"Please clock out first."
        }), None, None, None,None

    # Step 4: Otherwise allow clock-in
    return True, None, distance, float(user_lat), float(user_lon),str(outletname)


@app.route("/check_active_login_existence", methods=["POST"])
@login_required
def check_active_login_existence():
    ok, error_response, distance, user_lat, user_lon,outletname = checkif_any_existing_login_onloading()
    #print(error_response)
    if not ok:
        # 🚨 return the JSON error with a proper status code
     return error_response
    
@app.route("/alert_user_last_clockout", methods=["POST"]) 
@login_required   
def alert_user_last_clockout():
    # Get the last record with a completed clock-out
    last_clockout = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.check_out_time.isnot(None)
    ).order_by(Attendance.check_out_time.desc()).first()

    # Get the most recent record overall (could be open or closed)
    latest_record = Attendance.query.filter_by(user_id=current_user.id)\
                                    .order_by(Attendance.id.desc())\
                                    .first()

    print(last_clockout)
    print(latest_record)

    if last_clockout:
        print(latest_record.id)
        print(last_clockout.id)
        print(latest_record.check_out_time)

        # If there is a newer record after the last clock-out and it's still open
        if latest_record and latest_record.id > last_clockout.id and latest_record.check_out_time is None:
            return jsonify({
                "success": f"Your last clock-out was at {last_clockout.check_out_time}. "
               f"You have a pending clock-out since {latest_record.check_in_time}"
            })

        else:
            return jsonify({
                "error": f"Your last clock-out was at {last_clockout.check_out_time}"
            })
    else:
        # No previous clock-out found at all
        if latest_record and latest_record.check_out_time is None:
            return jsonify({
                "error": f"You have a pending clock-out since {latest_record.check_in_time}"
            })
        else:
            return jsonify({"error": "No previous clock-out found"})



@app.route("/summary", methods=["GET"])
@login_required
def today_summary():
    today = date.today()
    records = Attendance.query.filter_by(user_id=current_user.id, date=today)\
                              .order_by(Attendance.check_in_time.asc()).all()

    if not records:
        return jsonify({
            "clock_in": "You haven’t clocked in today.",
            "clock_out": "No clock-out record.",
            "work_hours": "No work hours recorded.",
            "clock_in_count": 0,
            "outlet": "None"
        })

    summary = {}

    # First clock-in of the day
    first_record = records[0]
    summary["clock_in"] = (
        f"You first clocked in at {first_record.check_in_time.strftime('%H:%M')} "
        f"at {first_record.outlet_name or 'None'}"
    )

    # Last record for current status
    last_record = records[-1]
    if last_record.check_out_time:
        summary["clock_out"] = (
            f"You last clocked out at {last_record.check_out_time.strftime('%H:%M')} "
            f"from {last_record.outlet_name or 'None'}"
        )
    else:
        summary["clock_out"] = (
            f"You are still logged in since {last_record.check_in_time.strftime('%H:%M')} "
            f"at {last_record.outlet_name or 'None'}"
        )

    # Total hours worked today
    total_hours = sum((r.work_hours or 0) for r in records)
    if last_record.check_in_time and not last_record.check_out_time:
        # Add running time for current session
        delta = datetime.now() - last_record.check_in_time
        total_hours += delta.total_seconds() / 3600

    summary["work_hours"] = f"You have worked {total_hours:.2f} hours today."

    # Number of clock-ins
    summary["clock_in_count"] = f"You have clocked-in {len(records)} times today."

    # Outlet info (last record’s outlet)
    summary["outlet"] = (
        f"{last_record.outlet_name or 'None'} — {last_record.outlet_address or ''}"
    )

    return jsonify(summary)


def get_today_summary(user_id):
    today = date.today()
    record = Attendance.query.filter_by(user_id=user_id, date=today).first()

    if not record:
        return {
            "clock_in": "You haven’t clocked in today.",
            "clock_out": "No clock-out record.",
            "work_hours": "No work hours recorded."
        }

    summary = {}

    # Clock-in
    if record.check_in_time:
        summary["clock_in"] = f"You clocked in at {record.check_in_time.strftime('%H:%M')}"
    else:
        summary["clock_in"] = "You haven’t clocked in today."

    # Clock-out
    if record.check_out_time:
        summary["clock_out"] = f"You clocked out at {record.check_out_time.strftime('%H:%M')}"
    else:
        summary["clock_out"] = f"You are still logged in since {record.check_in_time.strftime('%H:%M')}"

    # Work hours
    if record.work_hours:
        summary["work_hours"] = f"You worked for {record.work_hours:.2f} hours today."
    elif record.check_in_time and not record.check_out_time:
        delta = datetime.now() - record.check_in_time
        summary["work_hours"] = f"You have been working for {delta.total_seconds()/3600:.2f} hours so far."
    else:
        summary["work_hours"] = "No work hours recorded."

    return summary

@app.route("/report", methods=["GET"])
@login_required
def detailed_report():
    user_id = request.args.get("user_id")
    group_id = request.args.get("group_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = Attendance.query

    if user_id:
        query = query.filter_by(user_id=user_id)
    if group_id:
        query = query.join(User).filter(User.group_id == group_id)
    if start_date and end_date:
        query = query.filter(Attendance.date.between(start_date, end_date))

    records = query.order_by(Attendance.date.asc(), Attendance.check_in_time.asc()).all()

    report = []
    for r in records:
        duration = None
        if r.check_in_time and r.check_out_time:
            delta = r.check_out_time - r.check_in_time
            duration = round(delta.total_seconds() / 3600, 2)

        report.append({
            "date": r.date.strftime("%Y-%m-%d"),
            "user_id": r.user.id,                # include user id
            "staff_name": r.user.staff_name,     # include staff name
            "clock_in": r.check_in_time.strftime("%H:%M") if r.check_in_time else None,
            "clock_in_distance": r.clockin_distance,
            "clock_out": r.check_out_time.strftime("%H:%M") if r.check_out_time else None,
            "clock_out_distance": r.clockout_distance,
            "work_hours": duration or r.work_hours,
            "status": r.status
        })
    return jsonify(report)


@app.route('/reports')
@login_required
def reports():
    # Example: only admins can see full reports
    #if current_user.role != "admin":
    #    flash("Access denied: Reports are for admins only", "danger")
    #    return redirect(url_for('dashboard'))

    # Example data (replace with DB queries)
    monthly_summary = {
        "month": date.today().strftime("%B %Y"),
        "total_present": Attendance.query.filter_by(status="Present").count(),
        "total_absent": Attendance.query.filter_by(status="Absent").count(),
        "total_late": Attendance.query.filter_by(status="Late").count()
    }

    # Example: top 5 employees with most late arrivals
    top_late = Attendance.query.filter_by(status="Late")\
                               .group_by(Attendance.user_id)\
                               .limit(5).all()

    #return render_template("admin/reports.html",
    #                       monthly_summary=monthly_summary,
    #                       top_late=top_late)
    return render_template("admin/reports.html",
                           monthly_summary=monthly_summary,
                           )


@app.route("/report_page")
@login_required
def report_page():
    # Query all users and groups
    #users = Users.query.all()
    users = retrieve_offline_users()
    #groups = Group.query.all()
    #print(users)

    # Pass them into the template
    return render_template("report.html", users=users) #groups=groups

import csv
from io import StringIO
from flask import Response, jsonify

@app.route("/report_export", methods=["GET"])
@login_required
def report_export():
    user_id = request.args.get("user_id")
    group_id = request.args.get("group_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = Attendance.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    if group_id:
        query = query.join(User).filter(User.group_id == group_id)
    if start_date and end_date:
        query = query.filter(Attendance.date.between(start_date, end_date))

    records = query.order_by(Attendance.date.asc(), Attendance.check_in_time.asc()).all()

    # 🚨 If no records, return JSON warning instead of CSV
    if not records:
        return jsonify({"error": "No records found for the selected filters. Nothing to export."}), 404

    # Otherwise build CSV
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Date", "User ID", "User Name", "Clock-in", "Clock-in Distance",
                     "Clock-out", "Clock-out Distance", "Hours", "Status"])

    for r in records:
        duration = None
        if r.check_in_time and r.check_out_time:
            delta = r.check_out_time - r.check_in_time
            duration = round(delta.total_seconds() / 3600, 2)

        writer.writerow([
            r.date.strftime("%Y-%m-%d"),
            r.user.id,
            r.user.staff_name,
            r.check_in_time.strftime("%H:%M") if r.check_in_time else "",
            r.clockin_distance or "",
            r.check_out_time.strftime("%H:%M") if r.check_out_time else "",
            r.clockout_distance or "",
            duration or r.work_hours or "",
            r.status or ""
        ])

    output = si.getvalue()
    si.close()

    return Response(output,
                    mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=attendance_report.csv"})



@app.route('/settings')
@login_required
def settings():
    return render_template("settings/index.html")

@app.route('/settings/outlet', methods=['GET', 'POST'])
@login_required
def outlet_settings():
    search_query = request.args.get('search', '')
    if search_query:
        outlets = Outlet.query.filter(
            Outlet.name.ilike(f"%{search_query}%") |
            Outlet.outlet_id.ilike(f"%{search_query}%")
        ).all()
    else:
        outlets = Outlet.query.all()

    selected_outlet = None

    #users with no outlets attached
    # Example using SQLAlchemy
    free_users = Users.query.filter(~Users.id.in_(db.session.query(Outlet.user_id))).all()

    if request.method == 'POST':
        action = request.form.get("action")

        # CREATE
        if action == "create":
            print("we are inside create loop...")

            # 🔎 Compute next outlet_id automatically
            last_outlet = Outlet.query.order_by(Outlet.outlet_id.desc()).first()
            next_outlet_id = (last_outlet.outlet_id + 1) if last_outlet else 1000  # start from 1000

            new_user_id = request.form.get('user_id')

            # Check if user is already attached to another outlet
            if new_user_id:
                existing_outlet = Outlet.query.filter_by(user_id=new_user_id).first()
                if existing_outlet:
                    return jsonify({
                        "error": f"⚠️ Request declined, User is already attached to outlet '{existing_outlet.name}'. Cannot attach to multiple outlets."
                    }), 400

            new_outlet = Outlet(
                outlet_id=next_outlet_id,
                name=request.form.get('name'),
                latitude=float(request.form.get('latitude')) if request.form.get('latitude') else None,
                longitude=float(request.form.get('longitude')) if request.form.get('longitude') else None,
                address=request.form.get('address'),
                clock_in_radius=int(request.form.get('clock_in_radius')) if request.form.get('clock_in_radius') else 50,
                user_id=new_user_id if new_user_id else None
            )

            db.session.add(new_outlet)
            db.session.commit()
            return jsonify({"success": f"New outlet created successfully with ID {next_outlet_id}!"})

        # UPDATE
        outlet_id = request.form.get('outlet_id')
        selected_outlet = Outlet.query.get(outlet_id)
        if action == "update" and selected_outlet:
                        
            # Check if user is already attached to another outlet
            updated_user_id = request.form.get('user_id')
            if updated_user_id:
                existing_outlet = Outlet.query.filter_by(user_id=updated_user_id).first()
                if existing_outlet:
                    return jsonify({
                        "error": f"⚠️ Request declined, User is already attached to outlet '{existing_outlet.name}'. Cannot attach to multiple outlets."
                    }), 400
              
            # update logic...
            selected_outlet.name = request.form.get('name')
            selected_outlet.latitude = float(request.form.get('latitude'))
            selected_outlet.longitude = float(request.form.get('longitude'))
            selected_outlet.address = request.form.get('address')
            selected_outlet.clock_in_radius = int(request.form.get('clock_in_radius'))
            selected_outlet.user_id = request.form.get('user_id')
            db.session.commit()
            return jsonify({"success": "Outlet updated successfully!"})

        # DELETE
        if action == "delete" and selected_outlet:
            db.session.delete(selected_outlet)
            db.session.commit()
            return jsonify({"success": "Outlet deleted successfully!"})

    # For GET requests, also compute next_outlet_id to prefill the form
    last_outlet = Outlet.query.order_by(Outlet.outlet_id.desc()).first()
    next_outlet_id = (last_outlet.outlet_id + 1) if last_outlet else 1000

    return render_template("settings/outlet.html",
                           outlets=outlets,
                           selected_outlet=selected_outlet,
                           users=retrieve_offline_users(),
                           free_users=free_users,
                           search_query=search_query,
                           next_outlet_id=next_outlet_id)


def retrieve_offline_users():
  #users = Users.query.all()  # returns list of User objects
  #usernames = [u.f_namstafe for u in users]  # extract usernames
  #print("DEBUG: usernames =", usernames)
  #return usernames
  return Users.query.all()

def add_purchase(warehouse_id, crates, description=""):
    txn = WarehouseTransaction(
        warehouse_id=warehouse_id,
        transaction_type="purchase",
        crates=crates,
        description=description
    )
    warehouse = Warehouse.query.get(warehouse_id)
    if warehouse:
        warehouse.total_crates += crates
    db.session.add(txn)
    db.session.commit()


from itsdangerous import URLSafeTimedSerializer
serializer = URLSafeTimedSerializer(app.secret_key)
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form["username"]
        user = Users.query.filter_by(username=username).first()
        if user:
            token = serializer.dumps(user.id, salt="password-reset")
            reset_url = url_for("reset_password", token=token, _external=True)
            # TODO: send reset_url via email (Flask-Mail or SMTP)
            flash("Password reset link has been sent to your email.", "info")
        else:
            flash("User not found.", "danger")
    return render_template("forgot_password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    print("Form data:", request.form)
    print("Token received:", token)

    try:
        # Verify token (valid for 1 hour)
        user_id = serializer.loads(token, salt="password-reset", max_age=3600)
    except Exception:
        return jsonify({"status": "error", "message": "⚠️ Invalid or expired reset link."}), 400

    user = Users.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "⚠️ Request declined, user not found."}), 400

    if request.method == "POST":
        print("tracing point 2237")
        current_password = request.form.get("current_password")  # optional
        new_password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # If current_password was provided, validate it
        if current_password:
            print("current_password:", current_password)
            print("new_password:", new_password)
            print("confirm_password:", confirm_password)
            if not check_password_hash(user.password_hash, current_password):
                return jsonify({"status": "error", "message": "⚠️ Current password is incorrect."}), 400

        # Validate new password
        if new_password != confirm_password:
            return jsonify({"status": "error", "message": "⚠️ Passwords do not match."}), 400

        if len(new_password) < 5:
            return jsonify({"status": "error", "message": "⚠️ Password must be at least 5 characters long."}), 400

        # Update securely
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()

        return jsonify({"status": "success", "message": "✅ Password updated successfully."}), 200

    # For GET requests, render the reset page with token
    return render_template("reset_password.html", token=token)

def serialize_txn(txn):
    return {
        "timestamp": txn.timestamp.strftime("%Y-%m-%d %H:%M:%S") if txn.timestamp else None,
        "good_crates": txn.good_crates,
        "staff_name": txn.staff_name
    }

@app.route('/settings/manage_users', methods=['GET', 'POST'])
@login_required
def manage_users():
    outlets = Outlet.query.all()

    if request.method == "POST":
        
        action = request.form.get("action")
        print("Request method:", request.method)
        print("Action:", request.form.get("action"))

        if action == "create":
            name = request.form.get("name")
            plain_password = request.form.get("password")
            existing_user = Users.query.filter_by(staff_name=name).first()
            role_user = request.form.get("role")
            privilege_user = request.form.get("privilege")

            if existing_user:
                return jsonify({"error": f"Request declined,User '{name}' already exists!"}), 400

            hashed_pw = generate_password_hash(plain_password)
            new_user = Users(
                staff_name=name,
                username=name,
                password_hash=hashed_pw,
                is_active=1,
                role=role_user,
                privileges=privilege_user
            )
            db.session.add(new_user)
            db.session.commit()
            return jsonify({"success": f"User '{name}' added successfully!"})

        elif action == "update":
            user_id = request.form.get("username")
            new_name = request.form.get("new_name")
            user = Users.query.get(user_id)

            if not user:
                return jsonify({"error": "Request declined, User not found"}), 404

            if not new_name:
                new_name = user.username

            # Update user fields
            user.staff_name = new_name
            user.is_active = bool(request.form.get("active"))
            user.role = request.form.get("roles")
            user.privileges = request.form.get("privileges")

            new_outlet_id = request.form.get("outlet_id")
            print("Outlet ID from form:", new_outlet_id)

            if new_outlet_id:
                # Check if this user is already attached to any outlet
                existing_outlet = Outlet.query.filter_by(user_id=user.id).first()
                print("form outlet_id",new_outlet_id)
                print("fecthed existing_outlet",existing_outlet.outlet_id)
                if existing_outlet:
                    if str(existing_outlet.outlet_id) != str(new_outlet_id):
                        # User is attached to a different outlet → reject
                        return jsonify({
                            "error": (
                                f"⚠️ Request declined. User '{new_name}' is already attached "
                                f"to outlet '{existing_outlet.name}' (ID {existing_outlet.outlet_id}). "
                                "Cannot attach to multiple outlets."
                            )
                        }), 400
                    else:
                        # Same outlet → allow update of user fields
                        pass  # continue below

                # Now fetch the outlet by its ID
                outlet = Outlet.query.filter_by(outlet_id=new_outlet_id).first()
                if outlet:
                    # Check if outlet is attached to another user
                    if outlet.user_id and str(outlet.user_id) != str(user.id):
                        return jsonify({
                            "error": (
                                f"⚠️ Request declined. Outlet '{outlet.name}' (ID {outlet.outlet_id}) "
                                f"is already attached to user ID {outlet.user_id}. "
                                "Cannot reassign without freeing it first."
                            )
                        }), 400

                    # Safe to attach/update
                    outlet.user_id = user.id

            else:
                # No outlet_id provided → free all outlets attached to this user
                attached_outlets = Outlet.query.filter_by(user_id=user.id).all()
                for outlet in attached_outlets:
                    outlet.user_id = None

            db.session.commit()
            return jsonify({"success": f"User '{new_name}' successfully updated!"})

        elif action == "delete":
            user_id = request.form.get("del_username")
            user = Users.query.get(user_id)
            if not user:
                return jsonify({"error": "User not found"}), 404

            db.session.delete(user)
            db.session.commit()
            return jsonify({"success": f"User '{user.staff_name}' deleted successfully!"})

        return jsonify({"error": "Unknown action"}), 400

    # GET request → render template
    users = Users.query.all()
    return render_template(
        "settings/manage_users.html",
        users=users,
        outlets=outlets,
        roles=ROLE_LABELS.items(),
        privileges=PRIVILEGE_LABELS.items()
    )

@app.route("/get_user_privileges/<int:user_id>")
def get_user_privileges(user_id):
    user = Users.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    outlet = Outlet.query.filter_by(user_id=user_id).first()

    return jsonify({
        "active": bool(user.is_active),
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, "Unknown"),
        "privileges": user.privileges,
        "privileges_label": PRIVILEGE_LABELS.get(user.privileges, "Unknown"),
        "outlet_id": outlet.outlet_id if outlet else None,
        "outlet_label": outlet.name if outlet else "No outlet assigned"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render sets PORT
    app.run(host="0.0.0.0", port=port, debug=True)