import os
from datetime import datetime,timezone,date
from flask import Flask,Response, request, render_template_string, redirect, url_for, flash, render_template, jsonify,json
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy import create_engine, text,cast,Date,func,case,exists, not_
from flask_migrate import Migrate
#import uui
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import math
#from weasyprint import HTML
#import pdfkit
from functools import wraps
import pytz

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
    name = db.Column(db.String(255), nullable=False,unique=True)

    # Location details
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # Operational details
    address = db.Column(db.String(255), nullable=True,unique=True)
    clock_in_radius = db.Column(db.Integer, default=50)  # meters

    # Relationships
    #user_id = db.Column(db.Integer, nullable=True)
    #user = db.relationship('User', backref='outlets')

    # Audit fields
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f"<Outlet {self.name} ({self.outlet_id})>"

class AssignedOutlet(db.Model):
    __tablename__ = 'assigned_outlets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    outlet_id = db.Column(db.Integer, db.ForeignKey('outlet.outlet_id'), nullable=False)
    primary_outlet_id = db.Column(db.Integer, db.ForeignKey('outlet.outlet_id'), nullable=True)
    assigned_at = db.Column(db.DateTime, default=db.func.now())

    __table_args__ = (db.UniqueConstraint('user_id', 'outlet_id', name='uq_user_outlet'),)


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
    updated_at = db.Column(db.DateTime, default=db.func.now(),onupdate=db.func.now(), nullable=False)
    outlet_id = db.Column(db.Integer, nullable=True)  # business ID
    outlet_name = db.Column(db.String(100), nullable=True)
    outlet_address = db.Column(db.String(100), nullable=True)
    # Attendance model
    force_closed = db.Column(db.Boolean, default=False, nullable=False)
    #force_closed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    force_closed_by = db.Column(db.Integer, nullable=True)  # user_id, queried manually — no FK/relationship


class Shift(db.Model):
    __tablename__ = "shifts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    overtime_rate = db.Column(db.Float, nullable=True)

    attendances = db.relationship("Attendance", backref="shift", lazy=True)
    #attendances = db.relationship("Attendance",foreign_keys="Attendance.user_id",backref="user",lazy=True)
    

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
    date=date.today()
    if token != INIT_SECRET:
        return "Unauthorized", 403

    with app.app_context():
        db.create_all()
        #from sqlalchemy import text
        #from werkzeug.security import generate_password_hash

        try:
            # ✅ Generate hash at runtime
            admin_password = "12345"   # change this if you want a different raw password
            admin_hash = generate_password_hash(admin_password,method="pbkdf2:sha256")

            # ✅ Insert default SUPER_ADMINISTRATOR account if not already present
            db.session.execute(text("""
                INSERT INTO users (
                    staff_name, username, password_hash, is_active, email,
                    department, role, privileges, base_salary, hire_date
                )
                VALUES (
                    'SP_ADMIN',
                    'SP_ADMIN',
                    :password_hash,
                    TRUE,
                    'admin@system.com',
                    'Administration',
                    1,
                    1,
                    2000,
                    :hire_date
                )
                ON CONFLICT (username) DO NOTHING;
            """), {"password_hash": admin_hash},{"hire_date":date})

        except Exception as e:
            db.session.rollback()
            return f"Error altering table: {e}", 500

    return "Tables created, altered, and admin seeded successfully!"

@app.route("/seed-admin-pass")
def seed_admin_pass():
    #from werkzeug.security import generate_password_hash
    new_hash = generate_password_hash("evamutgi", method="pbkdf2:sha256")

    user = Users.query.filter_by(username="sp_admin").first()
    if user:
        user.password_hash = new_hash
        db.session.commit()
        return "✅ SP_ADMIN password reset to evamutgi"
    else:
        return "⚠️ sp_admin not found"


@app.route("/notupdated_init-db")
def not_update_init_db():
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
    conn_str = r"postgresql://tgl_crates_db_user:Vk1PPiktlT6aktTgzdCCNkQZZFfLeiX5@dpg-d6uodkchg0os73f4kql0-a.oregon-postgres.render.com/tgl_crates_db"
    
    #full cmd string  for tundagreen crates
    #cmd_str = r"C:\Program Files\PostgreSQL\18\bin\psql.exe" "postgresql://tgl_crates_db_user:Vk1PPiktlT6aktTgzdCCNkQZZFfLeiX5@dpg-d6uodkchg0os73f4kql0-a.oregon-postgres.render.com/tgl_crates_db"
    #full cmd string  for yellow beauty register
    cmd_str = r"C:\Program Files\PostgreSQL\18\bin\psql.exe" "postgresql://yellow_beauty_register_db_user:gWliEMbfUm8AD55JDM8TwuMitbGsq2VF@dpg-dagqc4tbedkc739qdhpg-a.oregon-postgres.render.com/yellow_beauty_register_db"
    
    
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


@app.route("/reset-admin-pass", methods=["POST"])
def reset_admin_pass():
    token = request.args.get("token")
    if token != INIT_SECRET:
        return "Unauthorized", 403

    #from werkzeug.security import generate_password_hash
    # ✅ Explicitly lock to PBKDF2-SHA256
    new_hash = generate_password_hash("987654", method="pbkdf2:sha256")

    user = Users.query.filter_by(username="SP_ADMIN").first()
    if user:
        user.password_hash = new_hash
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": "✅ Admin password updated successfully. Raw password is 'evamutgi'"
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": "⚠️ SP_ADMIN not found."
        }), 404


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        #username = request.form["username"].lower()
        username = request.form["username"].upper()
        password = request.form["password"]

        user = Users.query.filter_by(username=username).first()
        #print("retrieved username",user.username,"retrieved user_pass_hass",user.password_hash,"is_user_active",user.is_active)
        if user and not user.is_active:
            return jsonify({
                "status": "error",
                "message": "⚠️ You are currently actively suspended. Please contact your admin."
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
                "message": "⚠️ Invalid credentials, please try again or contact your administrator."
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
    assigned_outlets,active_outlet_id = get_current_user_outlets(user_id)

    #Assume mapped_outlet_ids is your list of dicts
    default_outlet = next(
      (o for o in assigned_outlets if o.get("is_primary")), 
       None
      )

    return render_template("profile.html",
                           attendance=attendance,
                           token=token,
                           outletname=default_outlet["outletname"] if default_outlet else None,
                           assigned_outlets =assigned_outlets,
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
    

from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role not in (1, 2):
            return jsonify({"error": "You do not have permission to perform this action."}), 403
        return f(*args, **kwargs)
    return decorated

def outdated_admin_required(f):
    @wraps(f)
    def outdated_decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            flash("Access denied: Admins only", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return outdated_decorated_function

@app.route('/admin/employees')
@login_required
@admin_required
def employees():
    return render_template('admin/employees.html')


def get_current_user_outlets(user_id=None):
    # Get all assignments for the current user
    #assignments = AssignedOutlet.query.filter_by(user_id=current_user.id).all()
    #print("user_id",user_id)
    assignments = AssignedOutlet.query.filter_by(user_id=user_id)
    #print("assignments",assignments)
    primary_outlet = None
    outlets = []

    # Find active attendance record (still clocked in)
    #active_record = Attendance.query.filter_by(
    #    user_id=current_user.id,
    #    check_out_time=None
    #).order_by(Attendance.id.desc()).first()
   
    active_record = Attendance.query.filter_by(
        user_id=user_id,
        check_out_time=None
    ).order_by(Attendance.id.desc()).first()



    unclosed_clockin_event_outlet_id = active_record.outlet_id if active_record else None

    for assignment in assignments:
        outlet = Outlet.query.filter_by(outlet_id=assignment.outlet_id).first()
        if outlet:
            outlets.append({
                "id": outlet.outlet_id,   # business ID
                "outletname": outlet.name,
                "unclosed_clockin_event": (outlet.outlet_id == unclosed_clockin_event_outlet_id),  # flag active outlet
                "is_primary": (outlet.outlet_id == assignment.primary_outlet_id) # Flag if this assignment marks the primary outlet
            })
            # If this assignment marks a primary outlet, set as default
            #if assignment.primary_outlet_id and assignment.primary_outlet_id == outlet.id:
            #    primary_outlet = outlet.name

    # If no explicit primary, fall back to first outlet
    #if not primary_outlet and outlets:
    #    primary_outlet = outlets[0]["outletname"]


    return outlets, unclosed_clockin_event_outlet_id


def outdate_get_current_user_outlets():
    # Get all assignments for the current user
    assignments = AssignedOutlet.query.filter_by(user_id=current_user.id).all()
    #print("current_userid",current_user.id)

    default_outlet = None
    outlets = []
    

    for assignment in assignments:
        #outlet = Outlet.query.get(assignment.outlet_id)
        # If outlet_id in AssignedOutlet points to Outlet PK
        #outlet = Outlet.query.get(assignment.outlet_id)

        # If outlet_id in AssignedOutlet points to Outlet.outlet_id (business ID)
        outlet = Outlet.query.filter_by(outlet_id=assignment.outlet_id).first()
        if outlet:
            outlets.append({
                "id": outlet.outlet_id,   # business ID
                "label": outlet.name
            })
            # If this assignment marks a primary outlet, set as default
            if assignment.primary_outlet_id and assignment.primary_outlet_id == outlet.id:
                default_outlet = outlet.name

    # If no explicit primary, fall back to first outlet
    if not default_outlet and outlets:
        default_outlet = outlets[0]["label"]

    return default_outlet, outlets


def returning_id_get_current_user_outlet():
   #outlet = Outlet.query.filter_by(user_id=current_user.id).first()
   outlet = AssignedOutlet.query.filter_by(user_id=current_user.id).first()
   if outlet:
    #user_outlet = outlet.name
    user_outlet = outlet.outlet_id
   else:
    user_outlet = "None"
   return (user_outlet)    


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():

    #Attendance.query.filter(
    #Attendance.remarks.ilike("%Force clock-out%"),
    #Attendance.force_closed == False
    #).update({"force_closed": True}, synchronize_session=False)
    #db.session.commit()

    user_id = current_user.id
    user = Users.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "⚠️ Request declined, user not found."}), 400

    
    # --- Outlet summary metrics ---
    today = date.today()

    total_outlets = Outlet.query.count()

    clocked_in_today = (
        db.session.query(Attendance.user_id, Attendance.outlet_id)
        .filter(
            Attendance.date == today,
            Attendance.check_in_time.isnot(None)
        )
        .distinct()
        .count()
    )

    clocked_out_today = (
        db.session.query(Attendance.user_id, Attendance.outlet_id)
        .filter(
            Attendance.date == today,
            Attendance.check_out_time.isnot(None)
        )
        .distinct()
        .count()
    )

    pending_clockouts = (
        db.session.query(Attendance.user_id, Attendance.outlet_id)
        .filter(
            Attendance.date == today,
            Attendance.check_in_time.isnot(None),
            Attendance.check_out_time.is_(None)
        )
        .distinct()
        .count()
    )

    unattended_today = Outlet.query.filter(
        not_(
            exists().where(
                (Attendance.outlet_id == Outlet.outlet_id) &
                (Attendance.date == today) &
                (Attendance.check_in_time.isnot(None))
            )
        )
    ).count()

    force_closure_waiting = (
        db.session.query(Attendance.user_id, Attendance.outlet_id)
        .filter(
            Attendance.check_out_time.is_(None),
            Attendance.check_in_time < today
        )
        .distinct()
        .count()
    )

    # --- Existing outlet assignment logic ---
    outlets, unclosed_clockin_event_outlet_id = get_current_user_outlets(user_id=user_id)

    primary_outlet = next((o for o in outlets if o.get("is_primary")), None)
    activelyassighedoutlet = next((o for o in outlets if o.get("unclosed_clockin_event")), None)

    return render_template(
        "dashboard.html",
        defaultoutletname=primary_outlet["outletname"] if primary_outlet else None,
        activelyassignedoutletname=activelyassighedoutlet["outletname"] if activelyassighedoutlet else None,
        assignedoutlets=outlets,
        # Pass summary metrics to template
        total_outlets=total_outlets,
        clocked_in_today=clocked_in_today,
        clocked_out_today=clocked_out_today,
        pending_clockouts=pending_clockouts,
        unattended_today=unattended_today,
        force_closure_waiting=force_closure_waiting
    )

@app.route("/outlet_clock_summary")
def outlet_clock_summary():
    outlets = Outlet.query.order_by(func.lower(Outlet.name)).all()
    today = date.today()

    result = []
    for outlet in outlets:
        latest_attendance = (
            Attendance.query
            .filter(
                Attendance.outlet_id == outlet.outlet_id,
                Attendance.date == today,
                Attendance.check_in_time.isnot(None)
            )
            .order_by(Attendance.check_in_time.desc())
            .first()
        )

        result.append({
            "id": outlet.id,
            "outlet_id": outlet.outlet_id,
            "name": outlet.name,
            "clocked_in": latest_attendance is not None,
            "last_clock_in": format_local_time(latest_attendance.check_in_time) if latest_attendance else None,
            "checked_out": latest_attendance.check_out_time is not None if latest_attendance else False
        })

    return jsonify(result)
    
@app.route("/no_outlets_summary_dashboard", methods=["GET", "POST"])
@login_required
def no_outlets_summary_dashboard():
    #summary = get_today_summary(current_user.id)
    #return jsonify(summary)   # or render_template("home.html", summary=summary)
    # Find outlet attached to current user
    #outlet = Outlet.query.filter_by(user_id=current_user.id).first()

    #if outlet:
    #    outletname = outlet.name
    #else:
    #    outletname = "None"
    #,attachedoutletname=
    user_id=current_user.id
    user = Users.query.get(user_id)
    if not user:
      return jsonify({"status": "error", "message": "⚠️ Request declined, user not found."}), 400
    
    #print("dashboard user_id",user_id)
    outlets, unclosed_clockin_event_outlet_id= get_current_user_outlets(user_id=user_id)
    #print("dashboard user primary outlet","other outlets",outlets)

    #default_outlet, assigned_outlets,active_outlet_id = get_current_user_outlets()
    #print("default_outlet at 737",default_outlet,"assigned_outlets",assigned_outlets)

    #Assume mapped_outlet_ids is your list of dicts
    primary_outlet = next(
    (o for o in outlets if o.get("is_primary")), 
    None
    )
    #Assume mapped_outlet_ids is your list of dicts
    activelyassighedoutlet = next(
    (o for o in outlets if o.get("unclosed_clockin_event")), 
    None
    )

    return render_template(
    "dashboard.html",
    defaultoutletname=primary_outlet["outletname"] if primary_outlet else None,
    activelyassignedoutletname=activelyassighedoutlet["outletname"] if activelyassighedoutlet  else None,
    assignedoutlets=outlets)
    


from datetime import timezone
from zoneinfo import ZoneInfo


def error_format_local_time(dt):
    """Convert UTC datetime to Nairobi local time string."""
    if dt is None:
        return "N/A"
    # Ensure dt is timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        local_dt = dt.astimezone(ZoneInfo("Africa/Nairobi"))
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")


def format_local_time(dt):
    if dt is None:
        return "N/A"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(ZoneInfo("Africa/Nairobi"))
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


QUICK_CLOCKOUT_THRESHOLD_MINUTES = 120  # adjust to whatever counts as "too soon"

# --- ROUTES ---#
def verify_clock_action(action, outlet_id=None, confirmed=False):
    data = request.json
    user_lat = data.get("latitude")
    user_lon = data.get("longitude")
    accuracy = data.get("accuracy")

    if not user_lat or not user_lon:
        return False, {"error": "Location required"}, None, None, None, None, None

    last_record = Attendance.query.filter_by(user_id=current_user.id)\
                                  .order_by(Attendance.id.desc())\
                                  .first()

    #last_record = Attendance.query.filter_by(user_id=current_user.id)\
    #    .filter(Attendance.status.not_in(['On Leave', 'Off']))\
    #    .order_by(Attendance.id.desc())\
    #    .first()
                               

    today_record = Attendance.query.filter_by(
        user_id=current_user.id,
        date=date.today()
    ).first()

    if action == "clockin":
        if today_record and today_record.status in ("Off", "On Leave"):
            return False, {
                "error": f"You are scheduled as {today_record.status} today and cannot clock in. "
                         f"Contact Admin Muchemi if this is incorrect."
            }, None, None, None, None, today_record

        if last_record and last_record.check_out_time is None and last_record.status not in(['On Leave', 'Off']):
            if last_record.date == date.today():
                return False, {
                    "error": f"You are already clocked in at {last_record.outlet_name} "
                             f"since {format_local_time(last_record.check_in_time)}. Please clock out first."
                }, None, None, None, None, last_record
            else:
                return False, {
                    "error": f"You have an unclosed session from {last_record.date} "
                             f"at {last_record.outlet_name}. Please contact Admin Muchemi "
                             f"to be logged out before clocking in today."
                }, None, None, None, None, last_record

        outlet = None
        distance = None

        if outlet_id:
            outlet = Outlet.query.filter_by(outlet_id=outlet_id).first()
            assigned = AssignedOutlet.query.filter_by(
                user_id=current_user.id,
                outlet_id=outlet_id
            ).first()
            if not outlet or not assigned:
                return False, {"error": "You are not assigned to this outlet"}, None, None, None, None, None

            distance = haversine(float(user_lat), float(user_lon),
                                  float(outlet.latitude), float(outlet.longitude))
            if distance > float(outlet.clock_in_radius):
                return False, {"error": f"You are not within {outlet.name} radius"}, None, None, None, None, None

        else:
            primary_assignment = AssignedOutlet.query.filter(
                AssignedOutlet.user_id == current_user.id,
                AssignedOutlet.primary_outlet_id.isnot(None)
            ).first()

            if primary_assignment:
                candidate = Outlet.query.filter_by(outlet_id=primary_assignment.outlet_id).first()
                if candidate:
                    dist = haversine(float(user_lat), float(user_lon),
                                      float(candidate.latitude), float(candidate.longitude))
                    if dist <= float(candidate.clock_in_radius):
                        outlet = candidate
                        distance = dist

            if not outlet:
                assignments = AssignedOutlet.query.filter_by(user_id=current_user.id).all()
                for a in assignments:
                    o = Outlet.query.filter_by(outlet_id=a.outlet_id).first()
                    if not o:
                        continue
                    dist = haversine(float(user_lat), float(user_lon),
                                      float(o.latitude), float(o.longitude))
                    if dist <= float(o.clock_in_radius):
                        outlet = o
                        distance = dist
                        break

            if not outlet:
                return False, {"error": "No valid outlet found within radius"}, None, None, None, None, None

        return True, "Ready to clock in", distance, float(user_lat), float(user_lon), outlet.name, last_record

    elif action == "clockout":
        if today_record and today_record.status in ("Off", "On Leave"):
            return False, {
                "error": f"You are scheduled as {today_record.status} today and cannot clock in. "
                            f"Contact Admin Muchemi if this is incorrect."
            }, None, None, None, None, today_record
        
        if not last_record or last_record.check_out_time is not None and last_record.status not in(['On Leave', 'Off']):
            return False, {"error": "You are not currently clocked in."}, None, None, None, None, last_record
        
        if last_record.date != date.today() and current_user.role != 1 and last_record.status not in(['On Leave', 'Off']):
            return False, {
                "error": f"You have an unclosed session from {last_record.date} "
                         f"at {last_record.outlet_name}. Please contact Admin Muchemi "
                         f"to have it closed before proceeding."
            }, None, None, None, None, last_record

        outlet = Outlet.query.filter_by(outlet_id=last_record.outlet_id).first()
        if not outlet:
            return False, {
                "error": "Your clocked-in outlet could not be found. Please contact Admin Muchemi."
            }, None, None, None, None, last_record

        distance = haversine(float(user_lat), float(user_lon),
                              float(outlet.latitude), float(outlet.longitude))
        if distance > float(outlet.clock_in_radius):
            return False, {"error": f"You are not within {outlet.name} radius"}, None, None, None, None, last_record

        check_in = last_record.check_in_time
        if check_in.tzinfo is None:
            check_in = check_in.replace(tzinfo=timezone.utc)
        elapsed_minutes = (datetime.now(timezone.utc) - check_in).total_seconds() / 60

        if elapsed_minutes < QUICK_CLOCKOUT_THRESHOLD_MINUTES and not confirmed:
            return "warning", {
                "warning": f"You clocked in only {int(elapsed_minutes)} minute(s) ago "
                           f"at {last_record.outlet_name}. Do you want to proceed with clocking out?",
                "requires_confirmation": True,
                "requires_reason": True
            }, distance, float(user_lat), float(user_lon), outlet.name, last_record

        return True, {"success": "Ready to clock out"}, distance, float(user_lat), float(user_lon), outlet.name, last_record

    elif action == "check_in_status":
        if today_record and today_record.status in ("Off", "On Leave"):
            return False, {
                "error": f"You are scheduled as {today_record.status} today. "
                        f"You cannot clock in or out."
            }, None, float(user_lat), float(user_lon), None, today_record

        if last_record and last_record.check_out_time is None and last_record.status not in(['On Leave', 'Off']):
            return False, {
                "error": f"You are already clocked in at {last_record.outlet_name} "
                        f"since {format_local_time(last_record.check_in_time)}"
            }, None, None, None, None, last_record

        return True, {"success": "No active login, you can clock in"}, None, float(user_lat), float(user_lon), None, last_record

    elif action == "check_out_status":
        if today_record and today_record.status in ("Off", "On Leave"):
            return False, {
                "error": f"You are scheduled as {today_record.status} today. "
                        f"There is no clock-out to perform."
            }, None, float(user_lat), float(user_lon), None, today_record

        if last_record and last_record.check_out_time is None and last_record.status not in(['On Leave', 'Off']):
            return False, {
                "error": f"You have a pending clock-out at {last_record.outlet_name} "
                        f"since {format_local_time(last_record.check_in_time)}"
            }, None, float(user_lat), float(user_lon), None, last_record

        return True, {"success": "No pending clock-out found"}, None, float(user_lat), float(user_lon), None, last_record


    elif action == "preserve_this_status":
        if today_record and today_record.status in ("Off", "On Leave"):
            return False, {
                "error": f"You are scheduled as {today_record.status} today. "
                         f"You cannot clock in or out."
            }, None, float(user_lat), float(user_lon), None, today_record

        if last_record and last_record.check_out_time is None:
            return False, {
                "error": f"You are already clocked in at {last_record.outlet_name} "
                         f"since {format_local_time(last_record.check_in_time)}"
            }, None, None, None, None, last_record
        return True, {"success": "No active login, you can clock in"}, None, float(user_lat), float(user_lon), None, last_record

    
def outdated_forth_oct_verify_clock_action(action, outlet_id=None, confirmed=False):
    data = request.json
    user_lat = data.get("latitude")
    user_lon = data.get("longitude")
    accuracy = data.get("accuracy")

    if not user_lat or not user_lon:
        return False, {"error": "Location required"}, None, None, None, None, None

    last_record = Attendance.query.filter_by(user_id=current_user.id)\
                                  .order_by(Attendance.id.desc())\
                                  .first()

    if action == "clockin":
        today_record = Attendance.query.filter_by(
        user_id=current_user.id,
        date=date.today()
        ).first()

        if today_record and today_record.status in ("Off", "On Leave"):
                        return False, {
                            "error": f"You are scheduled as {today_record.status} today and cannot clock in. "
                                    f"Contact Admin Muchemi if this is incorrect."
                        }, None, None, None, None, today_record

        if last_record and last_record.check_out_time is None:
            if last_record.date == date.today():
                return False, {
                    "error": f"You are already clocked in at {last_record.outlet_name} "
                             f"since {format_local_time(last_record.check_in_time)}. Please clock out first."
                }, None, None, None, None, last_record
            else:
                return False, {
                    "error": f"You have an unclosed session from {last_record.date} "
                             f"at {last_record.outlet_name}. Please contact Admin Muchemi "
                             f"to be logged out before clocking in today."
                }, None, None, None, None, last_record

        outlet = None
        distance = None

        if outlet_id:
            outlet = Outlet.query.filter_by(outlet_id=outlet_id).first()
            assigned = AssignedOutlet.query.filter_by(
                user_id=current_user.id,
                outlet_id=outlet_id
            ).first()
            if not outlet or not assigned:
                return False, {"error": "You are not assigned to this outlet"}, None, None, None, None, None

            distance = haversine(float(user_lat), float(user_lon),
                                  float(outlet.latitude), float(outlet.longitude))
            if distance > float(outlet.clock_in_radius):
                return False, {"error": f"You are not within {outlet.name} radius"}, None, None, None, None, None

        else:
            primary_assignment = AssignedOutlet.query.filter(
                AssignedOutlet.user_id == current_user.id,
                AssignedOutlet.primary_outlet_id.isnot(None)
            ).first()

            if primary_assignment:
                candidate = Outlet.query.filter_by(outlet_id=primary_assignment.outlet_id).first()
                if candidate:
                    dist = haversine(float(user_lat), float(user_lon),
                                      float(candidate.latitude), float(candidate.longitude))
                    if dist <= float(candidate.clock_in_radius):
                        outlet = candidate
                        distance = dist

            if not outlet:
                assignments = AssignedOutlet.query.filter_by(user_id=current_user.id).all()
                for a in assignments:
                    o = Outlet.query.filter_by(outlet_id=a.outlet_id).first()
                    if not o:
                        continue
                    dist = haversine(float(user_lat), float(user_lon),
                                      float(o.latitude), float(o.longitude))
                    if dist <= float(o.clock_in_radius):
                        outlet = o
                        distance = dist
                        break

            if not outlet:
                return False, {"error": "No valid outlet found within radius"}, None, None, None, None, None

        return True, "Ready to clock in", distance, float(user_lat), float(user_lon), outlet.name, last_record

    elif action == "clockout":
        if not last_record or last_record.check_out_time is not None:
            return False, {"error": "You are not currently clocked in."}, None, None, None, None, last_record

        if last_record.date != date.today() and current_user.role != 1:
            return False, {
                "error": f"You have an unclosed session from {last_record.date} "
                         f"at {last_record.outlet_name}. Please contact Admin Muchemi "
                         f"to have it closed before proceeding."
            }, None, None, None, None, last_record

        outlet = Outlet.query.filter_by(outlet_id=last_record.outlet_id).first()
        print("outlet line 1117",outlet)
        if not outlet:
            return False, {
                "error": "Your clocked-in outlet could not be found. Please contact Admin Muchemi."
            }, None, None, None, None, last_record

        distance = haversine(float(user_lat), float(user_lon),
                              float(outlet.latitude), float(outlet.longitude))
        if distance > float(outlet.clock_in_radius):
            return False, {"error": f"You are not within {outlet.name} radius"}, None, None, None, None, last_record

        check_in = last_record.check_in_time
        if check_in.tzinfo is None:
            check_in = check_in.replace(tzinfo=timezone.utc)
        elapsed_minutes = (datetime.now(timezone.utc) - check_in).total_seconds() / 60
        
        #print("elapsed_minutes line 1133",elapsed_minutes)
        if elapsed_minutes < QUICK_CLOCKOUT_THRESHOLD_MINUTES and not confirmed:
            return "warning", {
                "warning": f"You clocked in only {int(elapsed_minutes)} minute(s) ago "
                           f"at {last_record.outlet_name}. Do you want to proceed with clocking out?",
                "requires_confirmation": True,
                "requires_reason": True
            }, distance, float(user_lat), float(user_lon), outlet.name, last_record

        return True, {"success": "Ready to clock out"}, distance, float(user_lat), float(user_lon), outlet.name, last_record

    elif action == "status":
        if last_record and last_record.check_out_time is None:
            return False, {
                "error": f"You are already clocked in at {last_record.outlet_name} "
                         f"since {format_local_time(last_record.check_in_time)}"
            }, None, None, None, None, last_record
        return True, {"success": "No active login, you can clock in"}, None, float(user_lat), float(user_lon), None, last_record

@app.route("/clockin", methods=["POST"])
@login_required
def clock_in():
    payload = request.get_json(silent=True) or {}
    confirmed = payload.get("confirmed", False)
    outlet_id = payload.get("outlet_id")  # None if frontend doesn't send one — falls back to auto-resolve

    ok, response_data, distance, user_lat, user_lon, outletname, last_record = verify_clock_action(
        "clockin", outlet_id=outlet_id, confirmed=confirmed
    )

    if not ok:
        return jsonify(response_data), 400

    check_in_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    outlet = Outlet.query.filter_by(name=outletname).first()

    record = Attendance(
        user_id=current_user.id,
        date=date.today(),
        check_in_time=check_in_time,
        check_out_time=None,
        status="Clocked In",
        clockin_distance=distance,
        geo_lat=user_lat,
        geo_lon=user_lon,
        device_info="PC",
        remarks=None,
        outlet_id=outlet.outlet_id if outlet else None,
        outlet_name=outlet.name if outlet else "None",
        outlet_address=outlet.address if outlet else "None",
        force_closed=False,
        force_closed_by=None
    )
    db.session.add(record)
    db.session.commit()

    summary = get_today_summary(current_user.id)
    return {
        "success": f"Clock-in successful at {format_local_time(check_in_time)}, {distance:.2f}m from {outletname}",
        "summary": summary
    }

@app.route("/clockout", methods=["POST"])
@login_required
def clock_out():
    payload = request.get_json(silent=True) or {}
    confirmed = payload.get("confirmed", False)
    reason = payload.get("reason")

    ok, response_data, distance, user_lat, user_lon, outletname, last_record = verify_clock_action(
        "clockout", confirmed=confirmed
    )

    print("ok",ok,response_data,outletname)
    if ok == "warning":
        return jsonify(response_data), 200

    if not ok:
        return jsonify(response_data), 400

    check_out_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    last_record.check_out_time = check_out_time
    last_record.clockout_distance = distance

    if reason:
        last_record.clockout_note = reason  # still needs confirmation this column exists

    outlet = Outlet.query.filter_by(name=outletname).first()
    if outlet:
        last_record.outlet_id = outlet.outlet_id
        last_record.outlet_name = outlet.name
        last_record.status = 'Clocked Out'
    else:
        last_record.outlet_id = None
        last_record.outlet_name = "None"

    if last_record.check_in_time:
        check_in = last_record.check_in_time
        if check_in.tzinfo is None:
            check_in = check_in.replace(tzinfo=timezone.utc)
        delta = check_out_time - check_in
        hours_worked = round(delta.total_seconds() / 3600, 2)
        last_record.work_hours = hours_worked
        last_record.overtime_hours = max(0, hours_worked - 8)

    db.session.commit()

    summary = get_today_summary(current_user.id)
    return {
        "success": f"Clocked out {format_local_time(check_out_time)} successfully "
                   f"at {distance:.2f}m from {outletname}",
        "summary": summary
    }


import calendar
#from sqlalchemy import func
#from datetime import date, datetime, timezone

from datetime import date, datetime

@app.route("/admin/schedule_days", methods=["POST"])
@login_required
@admin_required
def schedule_days():
    payload = request.get_json(silent=True) or {}
    user_ids = payload.get("user_ids", [])
    dates_list = payload.get("dates", [])   # list of "YYYY-MM-DD" strings
    day_type = payload.get("type")          # "Off" or "Leave"

    if day_type not in ("Off", "Leave"):
        return jsonify({"error": "Invalid type. Must be 'Off' or 'Leave'."}), 400
    if not user_ids:
        return jsonify({"error": "Select at least one staff member."}), 400
    if not dates_list:
        return jsonify({"error": "Select at least one date."}), 400

    status_value = "On Leave" if day_type == "Leave" else "Off"

    parsed_dates = []
    for d_str in dates_list:
        try:
            parsed_dates.append(datetime.strptime(d_str, "%Y-%m-%d").date())
        except ValueError:
            return jsonify({"error": f"Invalid date format: {d_str}"}), 400

    inserted = 0
    skipped = []

    for target_date in parsed_dates:
        for uid in user_ids:
            existing = Attendance.query.filter_by(user_id=uid, date=target_date).first()
            if existing:
                user_obj = Users.query.get(uid)
                skipped.append({
                    "user": user_obj.staff_name if user_obj else f"User {uid}",
                    "date": target_date.strftime("%Y-%m-%d"),
                    "reason": f"Already has a record (status: {existing.status})"
                })
                continue

            record = Attendance(
                user_id=uid,
                date=target_date,
                check_in_time=None,
                check_out_time=None,
                status=status_value,
                remarks=f"Scheduled {status_value} by {current_user.username}"
            )
            db.session.add(record)
            inserted += 1

    db.session.commit()

    return jsonify({
        "success": f"Scheduled {inserted} day(s) successfully.",
        "inserted": inserted,
        "skipped": skipped
    })

@app.route("/admin/unschedule_days", methods=["POST"])
@login_required
@admin_required
def unschedule_days():
    payload = request.get_json(silent=True) or {}
    record_ids = payload.get("record_ids", [])

    if not record_ids:
        return jsonify({"error": "No records selected."}), 400

    removed = 0
    blocked = []

    for rid in record_ids:
        rec = Attendance.query.get(rid)
        if not rec:
            continue
        if rec.status not in ("Off", "On Leave") or rec.check_in_time is not None:
            blocked.append(rid)  # already worked or not a scheduled record — can't remove
            continue
        db.session.delete(rec)
        removed += 1

    db.session.commit()

    return jsonify({
        "success": f"Removed {removed} scheduled day(s).",
        "blocked_count": len(blocked)
    })

@app.route("/outdated_oct_forth_admin/unschedule_day", methods=["POST"])
@login_required
@admin_required
def outdated_oct_forth_unschedule_day():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    date_str = payload.get("date")

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date format."}), 400

    rec = Attendance.query.filter_by(user_id=user_id, date=target_date).first()
    if not rec:
        return jsonify({"error": "No scheduled record found for that date."}), 404

    if rec.status not in ("Off", "On Leave"):
        return jsonify({"error": "This record is not a scheduled Off/Leave day."}), 400

    if rec.check_in_time is not None:
        return jsonify({"error": "Cannot remove — user has already clocked in on this day."}), 400

    db.session.delete(rec)
    db.session.commit()
    return jsonify({"success": "Scheduled day removed."})

@app.route("/admin/scheduled_days_list", methods=["POST"])
@login_required
@admin_required
def scheduled_days_list():
    payload = request.get_json(silent=True) or {}
    user_ids = payload.get("user_ids", [])

    if not user_ids:
        return jsonify({"error": "No staff selected."}), 400

    today = date.today()
    records = (
        Attendance.query.filter(
            Attendance.user_id.in_(user_ids),
            Attendance.status.in_(["Off", "On Leave"]),
            Attendance.check_in_time.is_(None),
            Attendance.date >= today
        )
        .order_by(Attendance.date.asc())
        .all()
    )

    users_by_id = {u.id: u.staff_name for u in Users.query.filter(Users.id.in_(user_ids)).all()}

    return jsonify([{
        "id": r.id,
        "user_name": users_by_id.get(r.user_id, "Unknown"),
        "date": r.date.strftime("%Y-%m-%d"),
        "status": r.status
    } for r in records])

@app.route("/attendance_register")
@login_required
def attendance_register():
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month
    print_mode = request.args.get("print") == "1"

    days_in_month = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)
    today = date.today()

    day_labels = [
        calendar.day_abbr[date(year, month, d).weekday()]
        for d in range(1, days_in_month + 1)
    ]

    records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()
    records_by_user_day = {(r.user_id, r.date.day): r for r in records}

    all_users = Users.query.order_by(func.lower(Users.staff_name)).all()

    def avg_time(minutes_list):
        if not minutes_list:
            return None
        avg = round(sum(minutes_list) / len(minutes_list))
        return f"{avg // 60:02d}:{avg % 60:02d}"

    rows = []
    global_clock_in_minutes = []
    global_clock_out_minutes = []
    total_force_closed = 0

    for u in all_users:
        day_statuses = []
        p_count = o_count = l_count = a_count = 0
        user_clock_in_minutes = []
        user_clock_out_minutes = []
        user_force_closed = 0

        for d in range(1, days_in_month + 1):
            this_date = date(year, month, d)
            rec = records_by_user_day.get((u.id, d))

            if rec and rec.check_in_time:
                status = "P"
                p_count += 1

                ci = rec.check_in_time
                if ci.tzinfo is None:
                    ci = ci.replace(tzinfo=timezone.utc)
                user_clock_in_minutes.append(ci.hour * 60 + ci.minute)
                global_clock_in_minutes.append(ci.hour * 60 + ci.minute)

                if rec.check_out_time:
                    co = rec.check_out_time
                    if co.tzinfo is None:
                        co = co.replace(tzinfo=timezone.utc)
                    user_clock_out_minutes.append(co.hour * 60 + co.minute)
                    global_clock_out_minutes.append(co.hour * 60 + co.minute)

                if rec.force_closed:
                    user_force_closed += 1
                    total_force_closed += 1

            elif rec and rec.status == "On Leave":
                status = "L"
                l_count += 1
            elif rec and rec.status == "Off":
                status = "O"
                o_count += 1
            elif this_date > today:
                status = ""  # future, nothing scheduled — leave blank
            else:
                status = "A"
                a_count += 1

            day_statuses.append(status)

        rows.append({
            "name": u.staff_name,
            "day_statuses": day_statuses,
            "p_count": p_count,
            "o_count": o_count,
            "l_count": l_count,
            "a_count": a_count,
            "avg_clock_in": avg_time(user_clock_in_minutes),
            "avg_clock_out": avg_time(user_clock_out_minutes),
            "force_closed_count": user_force_closed
        })

    total_present = sum(r["p_count"] for r in rows)
    total_off = sum(r["o_count"] for r in rows)
    total_leave = sum(r["l_count"] for r in rows)
    total_absent = sum(r["a_count"] for r in rows)
    tracked_days = total_present + total_absent

    summary = {
        "total_staff": len(all_users),
        "total_present": total_present,
        "total_off": total_off,
        "total_leave": total_leave,
        "total_absent": total_absent,
        "avg_clock_in": avg_time(global_clock_in_minutes),
        "avg_clock_out": avg_time(global_clock_out_minutes),
        "total_force_closed": total_force_closed,
        "completion_rate": round((total_present / tracked_days) * 100, 1) if tracked_days else None
    }

    context = dict(
        rows=rows,
        days_in_month=days_in_month,
        day_range=range(1, days_in_month + 1),
        day_labels=day_labels,
        month=month,
        year=year,
        month_name=calendar.month_name[month],
        now=datetime.now(timezone.utc),
        summary=summary
    )

    template = "attendance_register_print.html" if print_mode else "attendance_register.html"
    return render_template(template, **context)

@app.route("/admin/schedule_grid")
@login_required
@admin_required
def schedule_grid():
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month

    days_in_month = calendar.monthrange(year, month)[1]

    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)

    # Today's date
    today = date.today()

    # ---------------------------------------------------------
    # Day information
    # weekday:
    # Monday = 0
    # Tuesday = 1
    # Wednesday = 2
    # Thursday = 3
    # Friday = 4
    # Saturday = 5
    # Sunday = 6
    # ---------------------------------------------------------
    day_info = [
        {
            "day": d,
            "label": calendar.day_abbr[
                date(year, month, d).weekday()
            ],
            "weekday": date(year, month, d).weekday(),
        }
        for d in range(1, days_in_month + 1)
    ]

    # ---------------------------------------------------------
    # Get attendance records for selected month
    # ---------------------------------------------------------
    records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()

    records_by_user_day = {
        (r.user_id, r.date.day): r
        for r in records
    }

    # ---------------------------------------------------------
    # Get all staff
    # ---------------------------------------------------------
    all_users = Users.query.order_by(
        func.lower(Users.staff_name)
    ).all()

    rows = []

    for u in all_users:

        cells = []

        # These counts come from the database and form
        # the initial saved values shown on the page.
        o_count = 0
        l_count = 0

        for d in range(1, days_in_month + 1):

            cell_date = date(year, month, d)

            # True only for dates BEFORE today.
            # Today remains editable.
            is_past = cell_date < today

            weekday = cell_date.weekday()

            rec = records_by_user_day.get((u.id, d))

            # -------------------------------------------------
            # Present / Worked
            # -------------------------------------------------
            if rec and rec.check_in_time:

                cells.append({
                    "day": d,
                    "value": "P",
                    "locked": True,
                    "past": is_past,
                    "weekday": weekday,
                })

            # -------------------------------------------------
            # Leave
            # -------------------------------------------------
            elif rec and rec.status == "On Leave":

                cells.append({
                    "day": d,
                    "value": "L",
                    "locked": False,
                    "past": is_past,
                    "weekday": weekday,
                })

                l_count += 1

            # -------------------------------------------------
            # Off
            # -------------------------------------------------
            elif rec and rec.status == "Off":

                cells.append({
                    "day": d,
                    "value": "O",
                    "locked": False,
                    "past": is_past,
                    "weekday": weekday,
                })

                o_count += 1

            # -------------------------------------------------
            # Empty
            # -------------------------------------------------
            else:

                cells.append({
                    "day": d,
                    "value": "",
                    "locked": False,
                    "past": is_past,
                    "weekday": weekday,
                })

        rows.append({
            "id": u.id,
            "name": u.staff_name,
            "cells": cells,

            # Saved database counts
            "o_count": o_count,
            "l_count": l_count,
        })

    # ---------------------------------------------------------
    # Current date information
    # ---------------------------------------------------------

    month_names = {
    m: calendar.month_name[m]
    for m in range(1, 13)
    }
    
    current_year = today.year
    current_month = today.month
    current_day = today.day

    # ---------------------------------------------------------
    # Render template
    # ---------------------------------------------------------
    return render_template(
        "schedule_grid.html",

        rows=rows,

        day_range=range(
            1,
            days_in_month + 1
        ),

        day_labels=[
            calendar.day_abbr[
                date(year, month, d).weekday()
            ]
            for d in range(1, days_in_month + 1)
        ],

        # IMPORTANT:
        # Used by HTML to correctly identify
        # Saturday and Sunday.
        day_info=day_info,

        month=month,
        year=year,
        month_name=calendar.month_name[month],
        month_names=month_names,
        current_month_name=calendar.month_name[current_month],
        current_year=current_year,
        current_month=current_month,
        current_day=current_day,
    )


@app.route("/fifth_oct_ver_two_admin/schedule_grid")
@login_required
@admin_required
def firth_oct_ver_two_schedule_grid():

    # =========================================================
    # SELECTED MONTH / YEAR
    # =========================================================

    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month


    # =========================================================
    # MONTH DATES
    # =========================================================

    days_in_month = calendar.monthrange(year, month)[1]

    start_date = date(year, month, 1)

    end_date = date(year, month, days_in_month)


    # =========================================================
    # TODAY
    # =========================================================

    today = date.today()


    # =========================================================
    # DAY LABELS
    # =========================================================

    day_labels = [
        calendar.day_abbr[
            date(year, month, d).weekday()
        ]
        for d in range(1, days_in_month + 1)
    ]


    # =========================================================
    # ATTENDANCE RECORDS
    # =========================================================

    records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()


    records_by_user_day = {
        (r.user_id, r.date.day): r
        for r in records
    }


    # =========================================================
    # ALL STAFF
    # =========================================================

    all_users = Users.query.order_by(
        func.lower(Users.staff_name)
    ).all()


    # =========================================================
    # BUILD GRID
    # =========================================================

    rows = []


    for u in all_users:

        cells = []

        o_count = 0

        l_count = 0


        for d in range(
            1,
            days_in_month + 1
        ):

            # Actual date represented by this cell
            cell_date = date(
                year,
                month,
                d
            )


            # Is this date in the past?
            is_past = cell_date < today


            # Find attendance record
            rec = records_by_user_day.get(
                (u.id, d)
            )


            # =================================================
            # WORKED / PRESENT
            # =================================================

            if rec and rec.check_in_time:

                cells.append({

                    "day": d,

                    "value": "P",

                    "locked": True,

                    "past": is_past

                })


            # =================================================
            # LEAVE
            # =================================================

            elif rec and rec.status == "On Leave":

                cells.append({

                    "day": d,

                    "value": "L",

                    "locked": False,

                    "past": is_past

                })

                l_count += 1


            # =================================================
            # OFF
            # =================================================

            elif rec and rec.status == "Off":

                cells.append({

                    "day": d,

                    "value": "O",

                    "locked": False,

                    "past": is_past

                })

                o_count += 1


            # =================================================
            # EMPTY
            # =================================================

            else:

                cells.append({

                    "day": d,

                    "value": "",

                    "locked": False,

                    "past": is_past

                })


        # =====================================================
        # ADD STAFF ROW
        # =====================================================

        rows.append({

            "id": u.id,

            "name": u.staff_name,

            "cells": cells,

            "o_count": o_count,

            "l_count": l_count

        })


    # =========================================================
    # RENDER TEMPLATE
    # =========================================================

    return render_template(

        "schedule_grid.html",

        rows=rows,

        day_range=range(
            1,
            days_in_month + 1
        ),

        day_labels=day_labels,

        # IMPORTANT:
        # These were commented out in your code.
        # Your HTML needs them.

        month=month,

        year=year,

        # Current date information

        current_year=today.year,

        current_month=today.month,

        current_day=today.day,

        # Month name for the selected grid

        month_name=calendar.month_name[month]

    )




@app.route("/fifth_oct_admin/schedule_grid")
@login_required
@admin_required
def fifth_oct_schedule_grid():
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month

    days_in_month = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)

    day_labels = [
        calendar.day_abbr[date(year, month, d).weekday()]
        for d in range(1, days_in_month + 1)
    ]

    records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()
    records_by_user_day = {(r.user_id, r.date.day): r for r in records}

    all_users = Users.query.order_by(func.lower(Users.staff_name)).all()

    rows = []
    for u in all_users:
        cells = []
        o_count = l_count = 0
        for d in range(1, days_in_month + 1):
            rec = records_by_user_day.get((u.id, d))
            if rec and rec.check_in_time:
                cells.append({"day": d, "value": "P", "locked": True})
            elif rec and rec.status == "On Leave":
                cells.append({"day": d, "value": "L", "locked": False})
                l_count += 1
            elif rec and rec.status == "Off":
                cells.append({"day": d, "value": "O", "locked": False})
                o_count += 1
            else:
                cells.append({"day": d, "value": "", "locked": False})
        rows.append({"id": u.id, "name": u.staff_name, "cells": cells, "o_count": o_count, "l_count": l_count})

    today = date.today()
    current_year = today.year
    current_month = today.month
    current_day = today.day
    
    return render_template(
        "schedule_grid.html",
        rows=rows,
        day_range=range(1, days_in_month + 1),
        day_labels=day_labels,
        #month=month,
        #year=year,
        current_month_name=calendar.month_name[current_month],
        current_year=current_year,
        current_month=current_month,
        current_day=current_day, 
    )
@app.route("/with_no_users_admin/schedule_grid")
@login_required
@admin_required
def with_no_users_schedule_grid():
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month

    days_in_month = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)

    day_labels = [
        calendar.day_abbr[date(year, month, d).weekday()]
        for d in range(1, days_in_month + 1)
    ]

    records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()
    records_by_user_day = {(r.user_id, r.date.day): r for r in records}

    all_users = Users.query.order_by(func.lower(Users.staff_name)).all()

    rows = []
    for u in all_users:
        cells = []
        for d in range(1, days_in_month + 1):
            rec = records_by_user_day.get((u.id, d))
            if rec and rec.check_in_time:
                cells.append({"day": d, "value": "P", "locked": True})
            elif rec and rec.status == "On Leave":
                cells.append({"day": d, "value": "L", "locked": False})
            elif rec and rec.status == "Off":
                cells.append({"day": d, "value": "O", "locked": False})
            else:
                cells.append({"day": d, "value": "", "locked": False})
        rows.append({"id": u.id, "name": u.staff_name, "cells": cells})

    return render_template(
        "schedule_grid.html",
        rows=rows,
        day_range=range(1, days_in_month + 1),
        day_labels=day_labels,
        month=month,
        year=year,
        month_name=calendar.month_name[month]
    )


@app.route("/admin/save_schedule_grid", methods=["POST"])
@login_required
@admin_required
def save_schedule_grid():
    payload = request.get_json(silent=True) or {}
    year = payload.get("year")
    month = payload.get("month")
    cells = payload.get("cells", [])  # [{user_id, day, value}], value in ("", "O", "L")

    if not year or not month or not cells:
        return jsonify({"error": "Missing year, month, or cell data."}), 400

    updated = 0
    cleared = 0
    skipped = []

    for cell in cells:
        uid = cell.get("user_id")
        day = cell.get("day")
        value = cell.get("value", "")

        try:
            target_date = date(int(year), int(month), int(day))
        except (ValueError, TypeError):
            continue

        existing = Attendance.query.filter_by(user_id=uid, date=target_date).first()

        if value == "":
            # Clear: only allowed if the existing row is a scheduled Off/Leave,
            # not a real worked day — matches the unschedule endpoint's guard.
            if existing and existing.status in ("Off", "On Leave") and existing.check_in_time is None:
                db.session.delete(existing)
                cleared += 1
            continue

        status_value = "On Leave" if value == "L" else "Off"

        if existing:
            if existing.check_in_time is not None:
                user_obj = Users.query.get(uid)
                skipped.append({
                    "user": user_obj.staff_name if user_obj else f"User {uid}",
                    "date": target_date.strftime("%Y-%m-%d"),
                    "reason": "Already has a worked record — cannot overwrite."
                })
                continue
            existing.status = status_value
            existing.remarks = f"Set to {status_value} by {current_user.username} (grid)"
            updated += 1
        else:
            record = Attendance(
                user_id=uid,
                date=target_date,
                check_in_time=datetime.now(timezone.utc).replace(second=0, microsecond=0),
                check_out_time = datetime.now(timezone.utc).replace(second=0, microsecond=0),
                status=status_value,
                remarks=f"Set to {status_value} by {current_user.username} (grid)"
            )
            db.session.add(record)
            updated += 1

    db.session.commit()

    return jsonify({
        "success": f"Saved {updated} day(s), cleared {cleared}.",
        "updated": updated,
        "cleared": cleared,
        "skipped": skipped
    })


@app.route("/no_off_n_leaves_attendance_register")
@login_required
def no_off_n_leaves_attendance_register():
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month
    print_mode = request.args.get("print") == "1"

    days_in_month = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)
    today = date.today()

    day_labels = [
        calendar.day_abbr[date(year, month, d).weekday()]
        for d in range(1, days_in_month + 1)
    ]

    records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()
    records_by_user_day = {(r.user_id, r.date.day): r for r in records}

    off_lookup = {}    # TODO: wire from Shifts/roster
    leave_lookup = {}  # TODO: wire from Leave model

    all_users = Users.query.order_by(func.lower(Users.staff_name)).all()

    def avg_time(minutes_list):
        if not minutes_list:
            return None
        avg = round(sum(minutes_list) / len(minutes_list))
        return f"{avg // 60:02d}:{avg % 60:02d}"

    rows = []
    global_clock_in_minutes = []
    global_clock_out_minutes = []
    total_force_closed = 0

    for u in all_users:
        day_statuses = []
        p_count = o_count = l_count = a_count = 0
        user_clock_in_minutes = []
        user_clock_out_minutes = []
        user_force_closed = 0

        for d in range(1, days_in_month + 1):
            this_date = date(year, month, d)
            rec = records_by_user_day.get((u.id, d))

            if this_date > today:
                status = ""
            elif rec and rec.check_in_time:
                status = "P"
                p_count += 1

                ci = rec.check_in_time
                if ci.tzinfo is None:
                    ci = ci.replace(tzinfo=timezone.utc)
                user_clock_in_minutes.append(ci.hour * 60 + ci.minute)
                global_clock_in_minutes.append(ci.hour * 60 + ci.minute)

                if rec.check_out_time:
                    co = rec.check_out_time
                    if co.tzinfo is None:
                        co = co.replace(tzinfo=timezone.utc)
                    user_clock_out_minutes.append(co.hour * 60 + co.minute)
                    global_clock_out_minutes.append(co.hour * 60 + co.minute)

                if rec.force_closed:
                    user_force_closed += 1
                    total_force_closed += 1

            elif leave_lookup.get((u.id, d)):
                status = "L"
                l_count += 1
            elif off_lookup.get((u.id, d)):
                status = "O"
                o_count += 1
            else:
                status = "A"
                a_count += 1

            day_statuses.append(status)

        rows.append({
            "name": u.staff_name,
            "day_statuses": day_statuses,
            "p_count": p_count,
            "o_count": o_count,
            "l_count": l_count,
            "a_count": a_count,
            "avg_clock_in": avg_time(user_clock_in_minutes),
            "avg_clock_out": avg_time(user_clock_out_minutes),
            "force_closed_count": user_force_closed
        })

    total_present = sum(r["p_count"] for r in rows)
    total_off = sum(r["o_count"] for r in rows)
    total_leave = sum(r["l_count"] for r in rows)
    total_absent = sum(r["a_count"] for r in rows)
    tracked_days = total_present + total_absent

    summary = {
        "total_staff": len(all_users),
        "total_present": total_present,
        "total_off": total_off,
        "total_leave": total_leave,
        "total_absent": total_absent,
        "avg_clock_in": avg_time(global_clock_in_minutes),
        "avg_clock_out": avg_time(global_clock_out_minutes),
        "total_force_closed": total_force_closed,
        "completion_rate": round((total_present / tracked_days) * 100, 1) if tracked_days else None
    }

    context = dict(
        rows=rows,
        days_in_month=days_in_month,
        day_range=range(1, days_in_month + 1),
        day_labels=day_labels,
        month=month,
        year=year,
        month_name=calendar.month_name[month],
        now=datetime.now(timezone.utc),
        summary=summary
    )

    template = "attendance_register_print.html" if print_mode else "attendance_register.html"
    return render_template(template, **context)

@app.route("/third_oct_perfect_attendance_register")
@login_required
def third_oct_perfect_attendance_register():
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month
    print_mode = request.args.get("print") == "1"

    days_in_month = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)
    today = date.today()

    day_labels = [
        calendar.day_abbr[date(year, month, d).weekday()]
        for d in range(1, days_in_month + 1)
    ]

    records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()
    records_by_user_day = {(r.user_id, r.date.day): r for r in records}

    # --- TODO: wire real Off/Leave sources here once models are confirmed ---
    off_lookup = {}    # expected shape: {(user_id, day): True, ...}
    leave_lookup = {}  # expected shape: {(user_id, day): True, ...}
    # --------------------------------------------------------------------

    all_users = Users.query.order_by(func.lower(Users.staff_name)).all()

    rows = []
    clock_in_minutes = []
    clock_out_minutes = []
    total_force_closed = 0

    for u in all_users:
        day_statuses = []
        p_count = o_count = l_count = a_count = 0

        for d in range(1, days_in_month + 1):
            this_date = date(year, month, d)
            rec = records_by_user_day.get((u.id, d))

            if this_date > today:
                status = ""
            elif rec and rec.check_in_time:
                status = "P"
                p_count += 1

                ci = rec.check_in_time
                if ci.tzinfo is None:
                    ci = ci.replace(tzinfo=timezone.utc)
                clock_in_minutes.append(ci.hour * 60 + ci.minute)

                if rec.check_out_time:
                    co = rec.check_out_time
                    if co.tzinfo is None:
                        co = co.replace(tzinfo=timezone.utc)
                    clock_out_minutes.append(co.hour * 60 + co.minute)

                if rec.force_closed:
                    total_force_closed += 1

            elif leave_lookup.get((u.id, d)):
                status = "L"
                l_count += 1
            elif off_lookup.get((u.id, d)):
                status = "O"
                o_count += 1
            else:
                status = "A"
                a_count += 1

            day_statuses.append(status)

        rows.append({
            "name": u.staff_name,
            "day_statuses": day_statuses,
            "p_count": p_count,
            "o_count": o_count,
            "l_count": l_count,
            "a_count": a_count
        })

    def avg_time(minutes_list):
        if not minutes_list:
            return None
        avg = round(sum(minutes_list) / len(minutes_list))
        return f"{avg // 60:02d}:{avg % 60:02d}"

    total_present = sum(r["p_count"] for r in rows)
    total_off = sum(r["o_count"] for r in rows)
    total_leave = sum(r["l_count"] for r in rows)
    total_absent = sum(r["a_count"] for r in rows)
    tracked_days = total_present + total_absent

    summary = {
        "total_staff": len(all_users),
        "total_present": total_present,
        "total_off": total_off,
        "total_leave": total_leave,
        "total_absent": total_absent,
        "avg_clock_in": avg_time(clock_in_minutes),
        "avg_clock_out": avg_time(clock_out_minutes),
        "total_force_closed": total_force_closed,
        "completion_rate": round((total_present / tracked_days) * 100, 1) if tracked_days else None
    }

    context = dict(
        rows=rows,
        days_in_month=days_in_month,
        day_range=range(1, days_in_month + 1),
        day_labels=day_labels,
        month=month,
        year=year,
        month_name=calendar.month_name[month],
        now=datetime.now(timezone.utc),
        summary=summary
    )

    template = "attendance_register_print.html" if print_mode else "attendance_register.html"
    return render_template(template, **context)

@app.route("/perfect_third_oct_attendance_register")
@login_required
def perfect_third_oct_attendance_register():
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month
    print_mode = request.args.get("print") == "1"

    days_in_month = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)
    today = date.today()

    day_labels = [
        calendar.day_abbr[date(year, month, d).weekday()]
        for d in range(1, days_in_month + 1)
    ]

    records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()
    records_by_user_day = {(r.user_id, r.date.day): r for r in records}

    # --- TODO: wire real Off/Leave sources here ---
    # off_lookup = {(user_id, day): True, ...}   # from Shifts/roster
    # leave_lookup = {(user_id, day): True, ...} # from Leave model
    off_lookup = {}
    leave_lookup = {}
    # ------------------------------------------------

    all_users = Users.query.order_by(func.lower(Users.staff_name)).all()

    rows = []
    for u in all_users:
        day_statuses = []
        p_count = o_count = l_count = a_count = 0

        for d in range(1, days_in_month + 1):
            this_date = date(year, month, d)
            rec = records_by_user_day.get((u.id, d))

            if this_date > today:
                status = ""  # future day — leave blank
            elif rec and rec.check_in_time:
                status = "P"
                p_count += 1
            elif leave_lookup.get((u.id, d)):
                status = "L"
                l_count += 1
            elif off_lookup.get((u.id, d)):
                status = "O"
                o_count += 1
            else:
                status = "A"
                a_count += 1

            day_statuses.append(status)

        rows.append({
            "name": u.staff_name,
            "day_statuses": day_statuses,
            "p_count": p_count,
            "o_count": o_count,
            "l_count": l_count,
            "a_count": a_count
        })

    # ... all your existing data-building logic, unchanged ...

    template = "attendance_register_print.html" if print_mode else "attendance_register.html"

    return render_template(
        template,
        rows=rows,
        days_in_month=days_in_month,
        day_range=range(1, days_in_month + 1),
        day_labels=day_labels,
        month=month,
        year=year,
        month_name=calendar.month_name[month],
        now=datetime.now(timezone.utc)
    )

@app.route("/hold_third_Oct_attendance_register")
@login_required
def hold_third_Oct_attendance_register():
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month

    days_in_month = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)
    today = date.today()

    day_labels = [
        calendar.day_abbr[date(year, month, d).weekday()]
        for d in range(1, days_in_month + 1)
    ]

    records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()
    records_by_user_day = {(r.user_id, r.date.day): r for r in records}

    # --- TODO: wire real Off/Leave sources here ---
    # off_lookup = {(user_id, day): True, ...}   # from Shifts/roster
    # leave_lookup = {(user_id, day): True, ...} # from Leave model
    off_lookup = {}
    leave_lookup = {}
    # ------------------------------------------------

    all_users = Users.query.order_by(func.lower(Users.staff_name)).all()

    rows = []
    for u in all_users:
        day_statuses = []
        p_count = o_count = l_count = a_count = 0

        for d in range(1, days_in_month + 1):
            this_date = date(year, month, d)
            rec = records_by_user_day.get((u.id, d))

            if this_date > today:
                status = ""  # future day — leave blank
            elif rec and rec.check_in_time:
                status = "P"
                p_count += 1
            elif leave_lookup.get((u.id, d)):
                status = "L"
                l_count += 1
            elif off_lookup.get((u.id, d)):
                status = "O"
                o_count += 1
            else:
                status = "A"
                a_count += 1

            day_statuses.append(status)

        rows.append({
            "name": u.staff_name,
            "day_statuses": day_statuses,
            "p_count": p_count,
            "o_count": o_count,
            "l_count": l_count,
            "a_count": a_count
        })

    return render_template(
        "attendance_register.html",
        rows=rows,
        days_in_month=days_in_month,
        day_range=range(1, days_in_month + 1),
        day_labels=day_labels,
        month=month,
        year=year,
        month_name=calendar.month_name[month],
        now=datetime.now(timezone.utc)
    )

@app.route("/hold_oct_second_attendance_register")
@login_required
def hold_oct_second_attendance_register():
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month

    days_in_month = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)

    records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()

    # Batch-fetch admin names for force-closed records (avoid N+1)
    admin_ids = {r.force_closed_by for r in records if r.force_closed_by}
    admins_by_id = (
        {u.id: u.staff_name for u in Users.query.filter(Users.id.in_(admin_ids)).all()}
        if admin_ids else {}
    )

    records_by_user = {}
    for r in records:
        records_by_user.setdefault(r.user_id, []).append(r)

    all_users = Users.query.order_by(func.lower(Users.staff_name)).all()

    rows = []
    for u in all_users:
        user_records = records_by_user.get(u.id, [])
        days = {}
        outlets_in = set()
        outlets_out = set()
        force_closed_days = {}  # day -> admin name

        for r in user_records:
            day = r.date.day
            if r.force_closed:
                admin_name = admins_by_id.get(r.force_closed_by, "Unknown")
                force_closed_days[day] = admin_name
            else:
                days[day] = days.get(day, 0) + (r.work_hours or 0)

            if r.check_in_time:
                outlets_in.add(r.outlet_id)
            if r.check_out_time:
                outlets_out.add(r.outlet_id)

        rows.append({
            "name": u.staff_name,
            "days": days,
            "outlets_in_count": len(outlets_in),
            "outlets_out_count": len(outlets_out),
            "force_closed_days": force_closed_days,
            "force_closed_count": len(force_closed_days)
        })

    return render_template(
        "attendance_register.html",
        rows=rows,
        days_in_month=days_in_month,
        day_range=range(1, days_in_month + 1),
        month=month,
        year=year,
        month_name=calendar.month_name[month],
        today_day=date.today().day if (year == date.today().year and month == date.today().month) else None,
        now=datetime.now(timezone.utc)
    )




def st_oct_verify_clock_action(action, confirmed=False):
    data = request.json
    user_lat = data.get("latitude")
    #print("user_lat", user_lat)
    user_lon = data.get("longitude")
    #print("user_lon", user_lon)
    accuracy = data.get("accuracy")
    outlet_id=None

    # Treat stored time as UTC, then convert
    #utc = pytz.utc
    #nairobi_tz = pytz.timezone("Africa/Nairobi")


    if not user_lat or not user_lon:
        return False, {"error": "Location required"}, None, None, None, None, None

    outlet = None
    distance = None

    # Step 1: If outlet_id explicitly provided, validate assignment
    if outlet_id:
        #outlet = Outlet.query.filter_by(id=outlet_id).first()
        outlet = Outlet.query.filter_by(outlet_id=outlet_id).first()
        assigned = AssignedOutlet.query.filter_by(
            user_id=current_user.id,
            outlet_id=outlet_id
        ).first()
        if not outlet or not assigned:
            return False, {"error": "You are not assigned to this outlet"}, None, None, None, None, None
    else:
        # Step 2: Try primary outlet first
       #from sqlalchemy import not_
        primary_assignment = AssignedOutlet.query.filter(
            AssignedOutlet.user_id == current_user.id,
            AssignedOutlet.primary_outlet_id.isnot(None)   # ✅ proper SQLAlchemy expression
        ).first()

        #print("main outlet assighed",primary_assignment)
        if primary_assignment:
            #outlet = Outlet.query.filter_by(id=primary_assignment.outlet_id).first()
            outlet = Outlet.query.filter_by(outlet_id=primary_assignment.outlet_id).first()
            #print("main outlet_id",outlet)
            if outlet:
                dist = haversine(float(user_lat), float(user_lon),
                                 float(outlet.latitude), float(outlet.longitude))
                if dist <= float(outlet.clock_in_radius):
                    distance = dist
                else:
                    outlet = None  # fail → fallback to other outlets

        # Step 3: Fallback to other assigned outlets
        if not outlet:
            assignments = AssignedOutlet.query.filter_by(user_id=current_user.id).all()
            for a in assignments:
                o = Outlet.query.filter_by(outlet_id=a.outlet_id).first()
                if not o:
                    continue
                dist = haversine(float(user_lat), float(user_lon),
                                 float(o.latitude), float(o.longitude))
                if dist <= float(o.clock_in_radius):
                    outlet = o
                    distance = dist
                    break

        if not outlet:
            return False, {"error": "No valid outlet found within radius"}, None, None, None, None, None


    # Step 4: Distance validation
    if distance is None:
        distance = haversine(float(user_lat), float(user_lon),
                             float(outlet.latitude), float(outlet.longitude))
    if distance > float(outlet.clock_in_radius):
        return False, {"error": f"You are not within {outlet.name} radius"}, None, None, None, None, None


    # Step 5: Check last record for this user
    last_record = Attendance.query.filter_by(user_id=current_user.id)\
                                  .order_by(Attendance.id.desc())\
                                  .first()

    if action == "clockin":
        #utc_time = utc.localize(last_record.check_in_time)
        #local_time = utc_time.astimezone(nairobi_tz)
        
        if last_record and last_record.check_out_time is None:
            # Rule 1: Already clocked in at ANY outlet
            if last_record.date == date.today():
                return False, {
                    "error": f"You are already clocked in at {last_record.outlet_name} "
                             f"since {format_local_time(last_record.check_in_time)}. Please clock out first."
                }, None, None, None, None, last_record
            else:
                # Rule 2: Previous day unclosed session
                return False, {
                    "error": f"You have an unclosed session from {last_record.date} "
                             f"at {last_record.outlet_name}. Please contact Admin Muchemi "
                             f"to be logged out before clocking in today."
                }, None, None, None, None, last_record

        return True, "Ready to clock in", distance, float(user_lat), float(user_lon), outlet.name, last_record

    # inside verify_clock_action, clockout branch, after the outlet-match check:
    elif action == "clockout":
        if not last_record or last_record.check_out_time is not None:
            return False, {"error": "You are not currently clocked in."}, None, None, None, None, last_record
       
        if last_record.date != date.today():  #and current_user.role !=1
            return False, {
                "error": f"You have an unclosed session from {last_record.date} "
                        f"at {last_record.outlet_name}. Please contact Admin Muchemi "
                        f"to have it closed before proceeding."
            }, None, None, None, None, last_record

        if last_record.outlet_id != outlet.outlet_id:
            return False, {
                "error": f"You clocked in at {last_record.outlet_name}. "
                        f"Please clock out from that outlet, not {outlet.name}."
            }, None, None, None, None, last_record
        return True, "Ready to clock out", distance, float(user_lat), float(user_lon), outlet.name, last_record   
    
    elif action == "status":
        if last_record and last_record.check_out_time is None:
            return False, {"error": f"You are already clocked in at {last_record.outlet_name} "
                                    f"since {format_local_time(last_record.check_in_time)}"}, None, None, None, None, last_record
        return True, {"success": "No active login, you can clock in"}, distance, float(user_lat), float(user_lon), outlet.name, last_record

@app.route("/st_oct_clockin", methods=["POST"])
@login_required
def st_oct_clock_in():
    #print("clocking in......918")
    payload = request.get_json(silent=True) or {}
    confirmed = payload.get("confirmed", False)
    reason = payload.get("reason")
    
    #outlet_id=None
    #primary_assignment = AssignedOutlet.query.filter(
    #        AssignedOutlet.user_id == current_user.id,
    #        AssignedOutlet.primary_outlet_id.isnot(None)   # ✅ proper SQLAlchemy expression
    #    ).first()

    #print("main outlet assighed",primary_assignment)
    #if primary_assignment:
    #    #outlet = Outlet.query.filter_by(id=primary_assignment.outlet_id).first()
    #    outlet = Outlet.query.filter_by(outlet_id=primary_assignment.outlet_id).first()
    #    outlet_id=outlet.outlet_id
        
    ok, response_data, distance, user_lat, user_lon, outletname, last_record = verify_clock_action("clockin",confirmed=confirmed)
    
    if not ok:
        return jsonify(response_data), 400

    #check_in_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    check_in_time = format_local_time(datetime.now())
    #outlet = Outlet.query.filter_by(user_id=current_user.id).first()
    outlet = Outlet.query.filter_by(name=outletname).first()

    #response_data.get("accuracy") if isinstance(response_data, dict) else accuracy
   #clockin_distance=distance,
    record = Attendance(
        user_id=current_user.id,
        date=date.today(),
        check_in_time=check_in_time,
        check_out_time=None,
        status="Clocked In",
        clockin_distance=distance,
        geo_lat=user_lat,
        geo_lon=user_lon,
        device_info="PC",
        remarks=None,
        outlet_id=outlet.outlet_id if outlet else None,
        outlet_name=outlet.name if outlet else "None",
        outlet_address=outlet.address if outlet else "None"
    )
    db.session.add(record)
    db.session.commit()

    summary = get_today_summary(current_user.id)
    return {
        "success": f"Clock-in successful at {check_in_time}, {distance:.2f}m from {outletname}",
        "summary": summary
    }

@app.route("/st_oct_clockout", methods=["POST"])
@login_required
def st_oct_clock_out():
    payload = request.get_json(silent=True) or {}
    confirmed = payload.get("confirmed", False)
    reason = payload.get("reason")
    #outlet_id = payload.get("outlet_id")

    #print ("checking arivval....1")
    ok, response_data, distance, user_lat, user_lon, outletname, last_record = verify_clock_action("clockout",confimred=confirmed)

    #print ("checking arivval....2")
    #if ok == "warning":
    #    return jsonify(response_data), 200

    #print ("checking arivval....3")
    if not ok:
        return jsonify(response_data), 400

    check_out_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    #check_out_time = format_local_time(datetime.now())
    last_record.check_out_time = check_out_time
    last_record.clockout_distance = distance

    #print ("checking arivval....")
    #if reason:
    #    last_record.clockout_note = reason  # requires this column — still unconfirmed, see below

    outlet = Outlet.query.filter_by(name=outletname).first()
    if outlet:
        last_record.outlet_id = outlet.outlet_id
        last_record.outlet_name = outlet.name
        last_record.status = 'Clocked Out'
    else:
        last_record.outlet_id = None
        last_record.outlet_name = "None"

    if last_record.check_in_time:
        check_in = last_record.check_in_time
        #check_in = format_local_time(last_record.check_in_time)    
        if check_in.tzinfo is None:
            check_in = check_in.replace(tzinfo=timezone.utc)
        delta = check_out_time - check_in
        hours_worked = round(delta.total_seconds() / 3600, 2)
        last_record.work_hours = hours_worked
        last_record.overtime_hours = max(0, hours_worked - 8)

    db.session.commit()

    summary = get_today_summary(current_user.id)
    return {
        "success": f"Clocked out {check_out_time} successfully "
                   f"at {distance:.2f}m from {outletname}",
        "summary": summary
    }

@app.route("/pending_clockout", methods=["POST"])
@login_required
def pending_clock_out():
    ok, response_data, distance, user_lat, user_lon, outletname, last_record = verify_clock_action("clockout")
    if not ok:
        return jsonify(response_data), 400

    check_out_time = datetime.now().replace(second=0, microsecond=0)
    last_record.check_out_time = check_out_time
    last_record.clockout_distance = distance

    #outlet = Outlet.query.filter_by(user_id=current_user.id).first()
    outlet = Outlet.query.filter_by(name=outletname).first()
    if outlet:
        last_record.outlet_id = outlet.outlet_id
        last_record.outlet_name = outlet.name
        last_record.status = 'Clocked Out'
    else:
        last_record.outlet_id = None
        last_record.outlet_name = "None"

    if last_record.check_in_time:
        delta = check_out_time - last_record.check_in_time
        hours_worked = round(delta.total_seconds() / 3600, 2)
        last_record.work_hours = hours_worked
        last_record.overtime_hours = max(0, hours_worked - 8)

    db.session.commit()

    summary = get_today_summary(current_user.id)
    #, worked {last_record.work_hours:.2f} hrs
    return {
        "success": f"Clocked out {check_out_time.strftime('%Y-%m-%d %H:%M')} successfully "
                   f"at {distance:.2f}m from {outletname}",
        "summary": summary
    }

@app.route("/attendance/force_close/<int:attendance_id>", methods=["POST"])
@login_required
def force_close(attendance_id):
    rec = Attendance.query.get(attendance_id)
    if rec and rec.check_out_time is None:
        rec.check_out_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        rec.remarks = (rec.remarks + " | " if rec.remarks else "") + f"Force clock-out by {current_user.username}"
        rec.status = 'Clocked Out'
        rec.force_closed = True
        rec.force_closed_by = current_user.id
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route("/st_oct_attendance/force_close/<int:attendance_id>", methods=["POST"])
@login_required
def st_oct_force_close(attendance_id):
    rec = Attendance.query.get(attendance_id)
    if rec and rec.check_out_time is None:
        rec.check_out_time = datetime.now().replace(second=0, microsecond=0)
        rec.remarks = "Force clock-out by Admin"
        rec.status = 'Clocked Out'
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route("/not_updated_outlets/details/<string:metric>")
@login_required
def not_updated_outlets_details(metric):
    if metric == "unattended":
        outlets = Outlet.query.filter(
        not_(
            exists().where(
                (Attendance.outlet_id == outlets.outlet_id) &
                (Attendance.date == date.today()) &
                (Attendance.check_in_time.isnot(None))
            )
        ))
        #outlets = Outlet.query.filter(
        #    ~Outlet.attendances.any(
        #        Attendance.date == date.today(),
        #        Attendance.check_in_time.isnot(None)
        #    )
        #).all()
        return jsonify([{"id": o.outlet_id, "name": o.name} for o in outlets])

    elif metric == "force_closure":
        records = Attendance.query.filter(
            Attendance.check_out_time.is_(None),
            Attendance.check_in_time < date.today()
        ).all()
        return jsonify([{
            "id": r.id,
            "user": r.user.username,
            "outlet": r.outlet_name,
            "clock_in": format_local_time(r.check_in_time)
        } for r in records])

    elif metric == "pending_clockouts":
        records = Attendance.query.filter(
            Attendance.date == date.today(),
            Attendance.check_in_time.isnot(None),
            Attendance.check_out_time.is_(None)
        ).all()
        return jsonify([{
            "id": r.id,
            "user": r.user.username,
            "outlet": r.outlet_name,
            "clock_in": format_local_time(r.check_in_time)
        } for r in records])

    elif metric == "clocked_in":
        records = Attendance.query.filter(
            Attendance.date == date.today(),
            Attendance.check_in_time.isnot(None),
            #Attendance.check_out_time.is_(None)
        ).all()
        return jsonify([{
            "id": r.id,
            "user": r.user.username,
            "outlet": r.outlet_name,
            "clock_in": format_local_time(r.check_in_time)
        } for r in records])

    elif metric == "clocked_out":
        records = Attendance.query.filter(
            Attendance.date == date.today(),
            Attendance.check_out_time.isnot(None)
        ).all()
        return jsonify([{
            "id": r.id,
            "user": r.user.username,
            "outlet": r.outlet_name,
            "clock_out": format_local_time(r.check_out_time)
        } for r in records])

    elif metric == "all_outlets":
        outlets = Outlet.query.all()
        data = []
    
        for o in outlets:       
            for o in outlets:
                 #Find the primary assignment for this outlet
                primary_assignment = AssignedOutlet.query.filter(
                    AssignedOutlet.outlet_id == o.outlet_id,
                    AssignedOutlet.primary_outlet_id.isnot(None)
                ).first()
        
                primary_user = None
                if primary_assignment:
                    user = Users.query.get(primary_assignment.user_id)
                    primary_user = user.username if user else None
                #primary_user = Users.query.get(o.user_id).username if o.user_id else None
                active_attendance = Attendance.query.filter_by(outlet_id=o.id, check_out_time=None).first()
                current_user = active_attendance.user.username if active_attendance else None
                data.append({
                    "outlet_id": o.id,
                    "outlet_name": o.name,
                    "primary_user": primary_user,
                    "current_user": current_user,
                    "latitude": o.latitude,
                    "longitude": o.longitude
                })
            return jsonify(data)
    # Add more metrics as needed
    return jsonify([])


@app.route("/outlets/details/<string:metric>")
@login_required
def outlets_details(metric):
    today = date.today()

    if metric == "unattended":
        outlets = Outlet.query.filter(
            not_(
                exists().where(
                    (Attendance.outlet_id == Outlet.outlet_id) &
                    (Attendance.date == today) &
                    (Attendance.check_in_time.isnot(None))
                )
            )
        ).order_by(func.lower(Outlet.name)).all()

        return jsonify([{
            "id": o.outlet_id,
            "outlet": o.name,       # matches item.outlet in your JS
            "user": "-",            # no attendance record exists, so nothing to show
            "clock_in": "-"
        } for o in outlets])

    elif metric == "force_closure":
        records = Attendance.query.filter(
            Attendance.check_out_time.is_(None),
            Attendance.check_in_time < today
        ).all()

        return jsonify([{
            "id": r.id,
            "user": r.user.username if r.user else "-",
            "outlet": r.outlet_name,
            "clock_in": format_local_time(r.check_in_time)
        } for r in records])

    elif metric == "pending_clockouts":
        records = Attendance.query.filter(
            Attendance.date == today,
            Attendance.check_in_time.isnot(None),
            Attendance.check_out_time.is_(None)
        ).all()

        return jsonify([{
            "id": r.id,
            "user": r.user.username if r.user else "-",
            "outlet": r.outlet_name,
            "clock_in": format_local_time(r.check_in_time)
        } for r in records])

    elif metric == "clocked_in":
        records = (
            Attendance.query
            .filter(
                Attendance.date == today,
                Attendance.check_in_time.isnot(None)
            )
            .order_by(Attendance.check_in_time.desc())  # newest first
            .all()
        )

        # Keep only the latest check-in per user/outlet pair
        seen = set()
        unique = []
        for r in records:
            key = (r.user_id, r.outlet_id)
            if key in seen:
                continue
            seen.add(key)
            unique.append(r)

        return jsonify([{
            "id": r.id,
            "user": r.user.username if r.user else "-",
            "outlet": r.outlet_name,
            "clock_in": format_local_time(r.check_in_time)
        } for r in unique])

    elif metric == "clocked_out":
        records = Attendance.query.filter(
            Attendance.date == today,
            Attendance.check_out_time.isnot(None)
        ).all()

        return jsonify([{
            "id": r.id,
            "user": r.user.username if r.user else "-",
            "outlet": r.outlet_name,
            "clock_out": format_local_time(r.check_out_time)
        } for r in records])

    elif metric == "all_outlets":
        outlets = Outlet.query.order_by(func.lower(Outlet.name)).all()
        data = []

        for o in outlets:
            primary_assignment = AssignedOutlet.query.filter(
                AssignedOutlet.outlet_id == o.outlet_id,
                AssignedOutlet.primary_outlet_id.isnot(None)
            ).first()
            primary_user = None
            if primary_assignment:
                user = Users.query.get(primary_assignment.user_id)
                primary_user = user.username if user else None

            # Currently clocked in (no check-out yet) today
            active_attendance = (
                Attendance.query
                .filter(
                    Attendance.outlet_id == o.outlet_id,
                    Attendance.date == today,
                    Attendance.check_out_time.is_(None),
                    Attendance.check_in_time.isnot(None)
                )
                .first()
            )
            current_user = active_attendance.user.username if active_attendance and active_attendance.user else None
            clock_in_time = format_local_time(active_attendance.check_in_time) if active_attendance else None

            # Most recent completed shift today
            last_closed = (
                Attendance.query
                .filter(
                    Attendance.outlet_id == o.outlet_id,
                    Attendance.date == today,
                    Attendance.check_out_time.isnot(None)
                )
                .order_by(Attendance.check_out_time.desc())
                .first()
            )
            clocked_out_user = last_closed.user.username if last_closed and last_closed.user else None
            clock_out_time = format_local_time(last_closed.check_out_time) if last_closed else None

            data.append({
                "outlet_id": o.outlet_id,
                "outlet_name": o.name,
                "primary_user": primary_user,
                "current_user": current_user,
                "clock_in_time": clock_in_time,
                "clocked_out_user": clocked_out_user,
                "clock_out_time": clock_out_time,
                "latitude": o.latitude,
                "longitude": o.longitude
            })

        return jsonify(data)

    # Add more metrics as needed
    return jsonify([])

@app.route("/hold_outlets/unattended")
@login_required
def hold_outlets_unattended():
    outlets = Outlet.query.filter(
        ~Outlet.attendances.any(
            Attendance.date == date.today(),
            Attendance.check_in_time.isnot(None)
        )
    ).all()
    return jsonify([{"id": o.id, "name": o.name} for o in outlets])

@app.route("/hold_outlets/force_closure")
@login_required
def hold_outlets_force_closure():
    records = Attendance.query.filter(
        Attendance.check_out_time.is_(None),
        Attendance.check_in_time < date.today()
    ).all()
    return jsonify([{
        "id": r.id,
        "user": r.user.username,
        "outlet": r.outlet_name,
        "clock_in": r.check_in_time.strftime("%Y-%m-%d %H:%M")
    } for r in records])

@app.route("/hold_force-clockout/<int:user_id>", methods=["POST"])
@login_required
def hold_force_clockout(user_id):
    # Only allow admins
    if current_user.role != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    # Find last active record for this user
    last_record = Attendance.query.filter_by(user_id=user_id)\
                                  .order_by(Attendance.id.desc())\
                                  .first()

    if not last_record or last_record.check_out_time is not None:
        return jsonify({"error": "No active session to force clock out"}), 400

    # Force clock out
    check_out_time = datetime.now().replace(second=0, microsecond=0)
    last_record.check_out_time = check_out_time
    last_record.remarks = "Force clock-out by Admin Muchemi"

    # Calculate hours worked if check_in_time exists
    if last_record.check_in_time:
        delta = check_out_time - last_record.check_in_time
        hours_worked = round(delta.total_seconds() / 3600, 2)
        last_record.work_hours = hours_worked
        last_record.overtime_hours = max(0, hours_worked - 8)

    db.session.commit()

    return jsonify({
        "success": f"User {user_id} force clocked out at {check_out_time.strftime('%Y-%m-%d %H:%M')}",
        "outlet": last_record.outlet_name,
        "check_in_time": str(last_record.check_in_time),
        "check_out_time": str(last_record.check_out_time)
    })

def get_active_or_overflow_sessions():
    today = date.today()
    return Attendance.query.filter(
        Attendance.check_out_time.is_(None)  # still active
    ).filter(
        Attendance.date < today              # overflow (previous day)
        | (Attendance.date == today)         # include today's active
    ).all()

@app.route("/admin/active-sessions")
@login_required
def active_sessions():
    if current_user.role != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    sessions = get_active_or_overflow_sessions()
    return render_template("admin_sessions.html", sessions=sessions)


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

@app.route("/check_active_login_existence", methods=["POST"])
@login_required
def check_active_login_existence():
    #print("active login checkin-1294")
    #def verify_clock_action(action, outlet_id=None):
    ok, response_data, distance, user_lat, user_lon, outletname, last_record = verify_clock_action("check_in_status")
    return jsonify(response_data)


@app.route("/alert_user_last_clockout", methods=["POST"])
@login_required
def alert_user_last_clockout():
    ok, response_data, distance, user_lat, user_lon, outletname, last_record = verify_clock_action("check_out_status")
    return jsonify(response_data)


@app.route("/not_updated_alert_user_last_clockout", methods=["POST"])
@login_required
def not_updated_alert_user_last_clockout():
    last_clockout = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.check_out_time.isnot(None)
    ).order_by(Attendance.check_out_time.desc()).first()

    latest_record = Attendance.query.filter_by(user_id=current_user.id)\
                                    .order_by(Attendance.id.desc())\
                                    .first()

    if last_clockout and latest_record and latest_record.id > last_clockout.id and latest_record.check_out_time is None:
        return jsonify({"error": f"You have a pending clock-out at {latest_record.outlet_name} since {format_local_time(latest_record.check_in_time)}"})
    elif latest_record and latest_record.check_out_time is None:
        return jsonify({"error": f"You have a pending clock-out at {latest_record.outlet_name} since {format_local_time(latest_record.check_in_time)}"})
    else:
        return jsonify({"error": "No pending clock-out found"})

@app.route("/summary", methods=["GET"])
@login_required
def today_summary():
    today = date.today()
    records = Attendance.query.filter_by(user_id=current_user.id, date=today)\
                              .order_by(Attendance.check_in_time.asc()).all()

    # Check for a scheduled Off/Leave day first — takes priority over both
    # the "no records" and normal summary paths, since it's a distinct state
    scheduled_record = next(
        (r for r in records if r.status in ("Off", "On Leave") and r.check_in_time is None),
        None
    )
    if scheduled_record:
        return jsonify({
            "alert": f"You are scheduled as {scheduled_record.status} today. "
                     f"You cannot clock in or out.",
            "status": scheduled_record.status,
            "clock_in": None,
            "clock_out": None,
            "clock_in_count": 0,
            "outlet": "None"
        })

    if not records:
        return jsonify({
            "clock_in": "You haven't clocked in today.",
            "clock_out": "No clock-out record.",
            "clock_in_count": 0,
            "outlet": "None"
        })

    summary = {}

    first_record = records[0]
    summary["clock_in"] = (
        f"You first clocked in at {format_local_time(first_record.check_in_time)} "
        f"at {first_record.outlet_name or 'None'}"
    )

    last_record = records[-1]
    if last_record.check_out_time:
        summary["clock_out"] = (
            f"You last clocked out at {format_local_time(last_record.check_out_time)} "
            f"from {last_record.outlet_name or 'None'}"
        )
    else:
        summary["clock_out"] = (
            f"You are still logged in since {format_local_time(last_record.check_in_time)} "
            f"at {last_record.outlet_name or 'None'}"
        )

    total_hours = sum((r.work_hours or 0) for r in records)
    if last_record.check_in_time and not last_record.check_out_time:
        check_in = last_record.check_in_time
        if check_in.tzinfo is None:
            check_in = check_in.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - check_in
        total_hours += delta.total_seconds() / 3600

    summary["clock_in_count"] = f"You have clocked-in {len(records)} times today."
    summary["outlet"] = f"{last_record.outlet_name or 'None'}"

    return jsonify(summary)

@app.route("/outdated_forth_dec_summary", methods=["GET"])
@login_required
def outdated_forth_dec_today_summary():
    today = date.today()
    #print("are we here 975")
    records = Attendance.query.filter_by(user_id=current_user.id, date=today)\
                              .order_by(Attendance.check_in_time.asc()).all()


    if not records:
        return jsonify({
            "clock_in": "You haven’t clocked in today.",
            "clock_out": "No clock-out record.",
            #"work_hours": "No work hours recorded.",
            "clock_in_count": 0,
            "outlet": "None"
        })

    summary = {}

    # First clock-in of the day #{first_record.check_in_time.strftime('%H:%M')}
    first_record = records[0]
    summary["clock_in"] = (
        f"You first clocked in at {format_local_time(first_record.check_in_time)}"
        f"at {first_record.outlet_name or 'None'}"
    )

    # Last record for current status
    last_record = records[-1]
    if last_record.check_out_time:
        summary["clock_out"] = (
            f"You last clocked out at {format_local_time(last_record.check_out_time)} "
            f"from {last_record.outlet_name or 'None'}"
        )
    else:
        summary["clock_out"] = (
            f"You are still logged in since {format_local_time(last_record.check_in_time)} "
            f"at {last_record.outlet_name or 'None'}"
        )

    # Total hours worked today
    total_hours = sum((r.work_hours or 0) for r in records)
    if last_record.check_in_time and not last_record.check_out_time:
        # Add running time for current session
        delta = datetime.now() - last_record.check_in_time
        total_hours += delta.total_seconds() / 3600

    #summary["work_hours"] = f"You have worked {total_hours:.2f} hours today."

    # Number of clock-ins
    summary["clock_in_count"] = f"You have clocked-in {len(records)} times today."

    # Outlet info (last record’s outlet)
    #— {last_record.outlet_address or ''}
    summary["outlet"] = (
        f"{last_record.outlet_name or 'None'}"
    )

    return jsonify(summary)


def get_today_summary(user_id):
    today = date.today()
    records = Attendance.query.filter_by(user_id=user_id, date=today)\
                              .order_by(Attendance.check_in_time.asc()).all()

    if not records:
        return {
            "clock_in": "You haven’t clocked in today.",
            "clock_out": "No clock-out record.",
            "work_hours": "No work hours recorded.",
            "clock_in_count": 0
        }

    summary = {}

    # First clock-in
    first_record = records[0]
    summary["clock_in"] = f"You first clocked in at {first_record.check_in_time.strftime('%H:%M')}"

    # Last record for current status
    last_record = records[-1]
    if last_record.check_out_time:
        summary["clock_out"] = f"You last clocked out at {last_record.check_out_time.strftime('%H:%M')}"
    else:
        summary["clock_out"] = f"You are still logged in since {last_record.check_in_time.strftime('%H:%M')}"

    # Total hours worked
    total_hours = sum((r.work_hours or 0) for r in records)
    if last_record.check_in_time and not last_record.check_out_time:
        delta = datetime.now() - last_record.check_in_time
        total_hours += delta.total_seconds() / 3600
    #summary["work_hours"] = f"You have worked {total_hours:.2f} hours today."

    # Number of clock-ins
    summary["clock_in_count"] = len(records)

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


@app.route("/settings/attendance_summary", methods=["GET", "POST"])
@login_required
def attendance_summary():
    users = retrieve_offline_users()
    #outlets = Outlet.query.all()
    outlets = Outlet.query.order_by(func.lower(Outlet.name)).all()
    #{format_local_time(latest_record.check_in_time)}
    return render_template("settings/attendance_summary.html", users=users, outlets=outlets)


@app.route("/generate_attendance_report", methods=["POST"])
@login_required
def generate_attendance_report():
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    user_ids = request.form.getlist("user_ids")
    outlet_ids = request.form.getlist("outlet_ids")

    #print("start_date",start_date)
    #print("end_date",end_date)
    #print("user_ids",user_ids)
    #print("outlet_ids",outlet_ids)
    #{format_local_time(last_record.check_in_time)}
    # Query attendance records based on filters
    records = Attendance.query.filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date,
        Attendance.user_id.in_(user_ids),
        Attendance.outlet_id.in_(outlet_ids)
    ).all()

    #print("records",records)
    data = []
    for rec in records:
        data.append({
            "user_id": rec.user_id,
            "username": rec.user.username,
            "recent_clock_in":  format_local_time(rec.check_in_time),
            "recent_clock_out": format_local_time(rec.check_out_time),
            "outlets_clocked": [rec.outlet_name],
            "status": [rec.status]
        })

    return jsonify(data)


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
   users=retrieve_offline_users()
   #outlets = Outlet.query.all()
   outlets = Outlet.query.order_by(func.lower(Outlet.name)).all()
   return render_template("settings/index.html",users=users,outlets=outlets)


@app.route("/settings/outlet", methods=["GET", "POST"])
@login_required
def outlet_settings():
    search_query = request.args.get('search', '')
    if search_query:
        outlets = Outlet.query.filter(
            Outlet.name.ilike(f"%{search_query}%") |
            Outlet.outlet_id.ilike(f"%{search_query}%")
        ).all()
    else:
        # or equivalently, ascending is default so this also works:
        #outlets = Outlet.query.all()
        outlets = Outlet.query.order_by(func.lower(Outlet.name)).all()
        #outlets = Outlet.query.order_by(Outlet.name.desc()).all()

    selected_outlet = None

    # Free reps: users with no assignments or no primary outlet
    #free_reps = Users.query.filter(
    #    ~Users.id.in_(db.session.query(AssignedOutlet.user_id))
    #).union(
    #    Users.query.filter(
    #        ~Users.id.in_(
    #            db.session.query(AssignedOutlet.user_id)
    #            .filter(AssignedOutlet.primary_outlet_id.isnot(None))
    #        )
    #    )
    #).all()


    free_reps = Users.query.filter(
        ~Users.id.in_(
            db.session.query(AssignedOutlet.user_id)
            .filter(AssignedOutlet.primary_outlet_id.isnot(None))
        )
    ).order_by(func.lower(Users.staff_name)).all()

    # Build mappings
    assigned_outlet_reps = {}             # outlet_id -> list of primary reps
    all_assigned_users_per_outlet = {}    # outlet_id -> list of all users
    assignments = AssignedOutlet.query.all()
    all_users = retrieve_offline_users()
    user_name_map = {u.id: u.staff_name for u in all_users}

    for ao in assignments:
        if ao.primary_outlet_id:
            assigned_outlet_reps.setdefault(ao.primary_outlet_id, []).append(ao.user_id)
        all_assigned_users_per_outlet.setdefault(ao.outlet_id, []).append(ao.user_id)

    if request.method == 'POST':
        action = request.form.get("action")
        outlet_id = request.form.get("outlet_id")

        if not action and outlet_id:
            selected_outlet = Outlet.query.get(outlet_id)

        # CREATE
        elif action == "create":
            last_outlet = Outlet.query.order_by(Outlet.outlet_id.desc()).first()
            next_outlet_id = (last_outlet.outlet_id + 1) if last_outlet else 1000

            new_name = request.form.get('name')
            new_address = request.form.get('address')

            # Duplicate checks
            if Outlet.query.filter_by(name=new_name).first():
                return jsonify({"error": f"⚠️ Outlet name '{new_name}' already exists."}), 400
            if Outlet.query.filter_by(address=new_address).first():
                return jsonify({"error": f"⚠️ Outlet address '{new_address}' already exists."}), 400

            new_user_id = request.form.get('user_id')

            if new_user_id:
                existing_primary = AssignedOutlet.query.filter(
                    AssignedOutlet.user_id == new_user_id,
                    AssignedOutlet.primary_outlet_id.isnot(None)
                ).first()
                if existing_primary:
                    return jsonify({
                        "error": f"⚠️ User already primarily attached to outlet ID {existing_primary.primary_outlet_id}."
                    }), 400

            new_outlet = Outlet(
                outlet_id=next_outlet_id,
                name=new_name,
                latitude=float(request.form.get('latitude')) if request.form.get('latitude') else None,
                longitude=float(request.form.get('longitude')) if request.form.get('longitude') else None,
                address=new_address,
                clock_in_radius=int(request.form.get('clock_in_radius')) if request.form.get('clock_in_radius') else 50
            )
            db.session.add(new_outlet)
            db.session.commit()

            if new_user_id:
                assignment = AssignedOutlet(
                    user_id=int(new_user_id),
                    outlet_id=new_outlet.outlet_id,
                    primary_outlet_id=new_outlet.outlet_id
                )
                db.session.add(assignment)
                db.session.commit()

            return jsonify({
                "success": f"New outlet created successfully with ID {next_outlet_id}!",
                "outlet": {
                    "outlet_id": new_outlet.outlet_id,
                    "name": new_outlet.name,
                    "address": new_outlet.address,
                    "latitude": new_outlet.latitude,
                    "longitude": new_outlet.longitude,
                    "clock_in_radius": new_outlet.clock_in_radius,
                    "user_id": int(new_user_id) if new_user_id else None
                }
            })

        elif action == "update":
            selected_outlet = Outlet.query.filter_by(outlet_id=outlet_id).first()
            if not selected_outlet:
                return jsonify({"error": "Outlet not found"}), 404

            # ✅ Handle Outlet Representative (only one allowed)
            rep_user_ids = request.form.getlist("rep_user_ids")  # from rep-checkbox
            #print("rep_user_ids",rep_user_ids)
            if rep_user_ids:
                rep_user_id = int(rep_user_ids[0])  # enforce single rep
                # Clear any existing primary rep for this outlet
                AssignedOutlet.query.filter_by(outlet_id=int(outlet_id)).update({"primary_outlet_id": None})
                # Ensure assignment exists
                assignment = AssignedOutlet.query.filter_by(user_id=rep_user_id, outlet_id=int(outlet_id)).first()
                if assignment:
                    assignment.primary_outlet_id = int(outlet_id)
                else:
                    assignment = AssignedOutlet(user_id=rep_user_id, outlet_id=int(outlet_id), primary_outlet_id=int(outlet_id))
                    db.session.add(assignment)

            # ✅ Handle Outlet Users (multi-select)
            outlet_users_ids = [int(uid) for uid in request.form.getlist("outlet_users_ids")]
            #print("outlet_users_ids",outlet_users_ids)
            # Remove users not checked
            AssignedOutlet.query.filter(
                AssignedOutlet.outlet_id == int(outlet_id),
                ~AssignedOutlet.user_id.in_(outlet_users_ids)
            ).delete(synchronize_session=False)
            # Add/update checked users
            for uid in outlet_users_ids:
                assignment = AssignedOutlet.query.filter_by(user_id=uid, outlet_id=int(outlet_id)).first()
                if not assignment:
                    db.session.add(AssignedOutlet(user_id=uid, outlet_id=int(outlet_id)))

            # Update outlet details
            selected_outlet.name = request.form.get("name")
            selected_outlet.latitude = float(request.form.get("latitude")) if request.form.get("latitude") else None
            selected_outlet.longitude = float(request.form.get("longitude")) if request.form.get("longitude") else None
            selected_outlet.address = request.form.get("address")
            selected_outlet.clock_in_radius = int(request.form.get("clock_in_radius")) if request.form.get("clock_in_radius") else 50

            db.session.commit()
            return jsonify({"success": "Outlet updated successfully!"})

        # DELETE
        elif action == "delete":
            selected_outlet = Outlet.query.filter_by(outlet_id=outlet_id).first()
            if selected_outlet:
                AssignedOutlet.query.filter_by(outlet_id=selected_outlet.outlet_id).delete()
                db.session.delete(selected_outlet)
                db.session.commit()
                return jsonify({
                    "success": "Outlet deleted successfully!",
                    "outlet": {
                        "outlet_id": selected_outlet.outlet_id,
                        "name": selected_outlet.name,
                        "address": selected_outlet.address,
                        "latitude": selected_outlet.latitude,
                        "longitude": selected_outlet.longitude,
                        "clock_in_radius": selected_outlet.clock_in_radius
                    }
                })

        # DELETE logic unchanged...
        # CREATE logic unchanged...

    last_outlet = Outlet.query.order_by(Outlet.outlet_id.desc()).first()
    next_outlet_id = (last_outlet.outlet_id + 1) if last_outlet else 1000

    return render_template("settings/outlet.html",
                           outlets=outlets,
                           selected_outlet=selected_outlet,
                           all_users=all_users,
                           free_reps=free_reps,
                           assighed_outlet_reps=assigned_outlet_reps,
                           user_name_map=user_name_map,
                           all_assighed_users_per_outlet=all_assigned_users_per_outlet,
                           search_query=search_query,
                           next_outlet_id=next_outlet_id)

def retrieve_offline_users():
  #users = Users.query.all()  # returns list of User objects
  #usernames = [u.f_namstafe for u in users]  # extract usernames
  #print("DEBUG: usernames =", usernames)
  #return usernames
  #return Users.query.all()
  #return Users.query.order_by(Users.staff_name).all()
  return Users.query.order_by(func.lower(Users.staff_name)).all()


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
        #print("tracing point 2237")
        current_password = request.form.get("current_password")  # optional
        new_password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # If current_password was provided, validate it
        if current_password:
            #print("current_password:", current_password)
            #print("new_password:", new_password)
            #print("confirm_password:", confirm_password)
            if not check_password_hash(user.password_hash, current_password):
                return jsonify({"status": "error", "message": "⚠️ Current password is incorrect."}), 400

        # Validate new password
        if new_password != confirm_password:
            return jsonify({"status": "error", "message": "⚠️ Passwords do not match."}), 400

        if len(new_password) < 5:
            return jsonify({"status": "error", "message": "⚠️ Password must be at least 5 characters long."}), 400

        # Update securely
        user.password_hash = generate_password_hash(new_password,method="pbkdf2:sha256")
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
    #outlets = Outlet.query.all()
    outlets = Outlet.query.order_by(func.lower(Outlet.name)).all()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create":
            name = request.form.get("name").upper()
            plain_password = request.form.get("password")
            existing_user = Users.query.filter_by(staff_name=name).first()
            role_user = request.form.get("role")
            privilege_user = request.form.get("privilege")

            if existing_user:
                return jsonify({"error": f"Request declined, User '{name}' already exists!"}), 400

            hashed_pw = generate_password_hash(plain_password, method="pbkdf2:sha256")
            #hashed_pw = generate_password_hash(plain_password)
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
            new_name = request.form.get("new_name").upper()
            user = Users.query.get(user_id)

            if not user:
                return jsonify({"error": "Request declined, User not found"}), 404

            if not new_name:
                new_name = user.username

            # Update user fields
            user.staff_name = new_name
            user.username = new_name
            user.is_active = bool(request.form.get("active"))
            user.role = request.form.get("roles")
            user.privileges = request.form.get("privileges")

            selected_outlet_ids = [int(oid) for oid in request.form.getlist("all_outlet_ids")]
            primary_outlet_ids = [int(oid) for oid in request.form.getlist("rep_outlet_ids")]

            # Clear existing assignments
            AssignedOutlet.query.filter_by(user_id=user.id).delete()

            force_reallocate = request.form.get("force_reallocate") == "true"

            # Conflict check unless forced
            if not force_reallocate:
                for oid in primary_outlet_ids:
                    conflict = AssignedOutlet.query.filter(
                        AssignedOutlet.primary_outlet_id == oid,
                        AssignedOutlet.user_id != user.id
                    ).first()
                    if conflict:
                        other_user = Users.query.get(conflict.user_id)
                        return jsonify({
                            "error": (
                                f"⚠️ Request declined. Outlet ID {oid} is already primarily allocated "
                                f"to user '{other_user.staff_name}'. Do you want to re-allocate?"
                            )
                        }), 400

            # Add new assignments
            for oid in selected_outlet_ids:
                if oid in primary_outlet_ids:
                    db.session.add(AssignedOutlet(user_id=user.id, outlet_id=oid, primary_outlet_id=oid))
                else:
                    db.session.add(AssignedOutlet(user_id=user.id, outlet_id=oid))

            db.session.commit()
            return jsonify({"success": f"User '{new_name}' successfully updated!"})


        elif action == "delete":
            user_id = request.form.get("username")
            print("delete user_id", user_id)
            user = Users.query.get(user_id)
            if not user:
                return jsonify({"error": "User not found"}), 404

            # Also clear assignments
            AssignedOutlet.query.filter_by(user_id=user.id).delete()

            db.session.delete(user)
            db.session.commit()
            return jsonify({"success": f"User '{user.staff_name}' deleted successfully!"})

        return jsonify({"error": "Unknown action"}), 400

    # GET request → render template
    users = Users.query.order_by(func.lower(Users.staff_name)).all()
    

    # Build a dict of {user_id: [outlet_ids]} for pre-checking
    #user_outlet_map = {
    #    #u.id: [ao.outlet_id for ao in AssignedOutlet.query.filter_by(user_id=u.id).all()]
    #    u.id: [ao.outlet_id for ao in AssignedOutlet.query.filter_by(user_id=u.id).all()]
    #    for u in users
    #}

    #print("user_outlet_map",user_outlet_map )
    #user_id = request.form.get("username")
    #new_name = request.form.get("new_name")
    #user = Users.query.get(user_id)
    #print("user_selected",user_id )
    
    #primary_outlet, outlets, unclosed_clockin_event_outlet_id= get_current_user_outlets(user_id=user_id)

    return render_template(
        "settings/manage_users.html",
        users=users,
        outlets=outlets,
        #user_outlet_map=user_outlet_map,
        roles=ROLE_LABELS.items(),
        privileges=PRIVILEGE_LABELS.items()
    )

@app.route("/get_user_privileges/<int:user_id>")
def get_user_privileges(user_id):
    user = Users.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get outlets for this user
    assigned_outlets, active_outlet_id = get_current_user_outlets(user_id=user_id)

    # 🔑 Collect all primary outlet assignments across all users
    primary_outlet_map = {}
    all_assignments = AssignedOutlet.query.all()
    for ao in all_assignments:
        if ao.primary_outlet_id:
            primary_outlet_map[ao.primary_outlet_id] = ao.user_id

    #print("selected_user_on_privilege", user_id)
    print("mapped_outlet_ids", assigned_outlets)
    print("primary_outlet_map", primary_outlet_map)

    return jsonify({
        "user_id": user.id,
        "staff_name": user.staff_name,
        "active": bool(user.is_active),
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, "Unknown"),
        "privileges": user.privileges,
        "privileges_label": PRIVILEGE_LABELS.get(user.privileges, "Unknown"),
        "mapped_outlet_ids": assigned_outlets,
        # ✅ New field: all primary outlet IDs with their owning user IDs
        "primary_outlet_map": primary_outlet_map
    })


@app.route("/14th_sep_get_user_privileges/<int:user_id>")
def th_sep_get_user_privileges(user_id):

    # Build a dict of {user_id: [outlet_ids]} for pre-checking
    #user_outlet_map = {
    #    #u.id: [ao.outlet_id for ao in AssignedOutlet.query.filter_by(user_id=u.id).all()]
    #    u.id: [ao.outlet_id for ao in AssignedOutlet.query.filter_by(user_id=u.id).all()]
    #    for u in users
    #}

    #print("user_outlet_map",user_outlet_map )

    user = Users.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    #assignments = AssignedOutlet.query.filter_by(user_id=user_id).all()
    #print("assignments", assignments)

    #outlet_list = []
    #mapped_outlet_ids = []
    #primary_outlet = None

    #for ao in assignments:
    #    outlet = Outlet.query.filter(Outlet.outlet_id == ao.outlet_id).first()
        #print("outlet-2026", outlet)

    #    if outlet:
    #        outlet_list.append({
    #            "outlet_id": outlet.outlet_id,
    #            "outlet_label": outlet.name
    #        })
    #        mapped_outlet_ids.append(outlet.outlet_id)

    #    if ao.primary_outlet_id:
    #        primary_outlet = Outlet.query.get(ao.primary_outlet_id)
    print("selected_user_on_plivirage",user_id)
    assigned_outlets,active_outlet_id = get_current_user_outlets(user_id=user_id)


    #print("user_id-2036", user.id)
    #print("primary_outlet-2037",primary_outlet)
    print("mapped_outlet_ids", assigned_outlets)

    #"outlets": outlet_list,
    #"primary_outlet": {
    #        "outlet_id": primary_outlet.outlet_id if primary_outlet else None,
    #        "outlet_label": primary_outlet.name if primary_outlet else "No primary outlet"
    return jsonify({
        "user_id": user.id,
        "staff_name": user.staff_name,
        "active": bool(user.is_active),
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, "Unknown"),
        "privileges": user.privileges,
        "privileges_label": PRIVILEGE_LABELS.get(user.privileges, "Unknown"),
        "mapped_outlet_ids": assigned_outlets
        #"primary_outlet": primary_outlet
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render sets PORT
    app.run(host="0.0.0.0", port=port, debug=True)