from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ==========================
# DATABASE CONFIG
# ==========================
app.config['MYSQL_HOST'] = 'roundhouse.proxy.rlwy.net'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'RPxWbUgnYIoaozUiwIwSSgasXFFaXPxx'
app.config['MYSQL_DB'] = 'railway'
app.config['MYSQL_PORT'] = 17072

mysql = MySQL(app)


# ==========================
# HOME
# ==========================
@app.route('/')
def home():
    return render_template('home.html')

# ==========================
# STUDENT REGISTER
# ==========================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form['student_id']
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        course = request.form['course']
        year = request.form['year']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM student WHERE student_id = %s", (student_id,))
        if cur.fetchone():
            cur.close()
            return "<h4 style='color:red;'>Student ID already registered ❌</h4>"

        hashed_password = generate_password_hash(password)

        cur.execute("""
            INSERT INTO student (student_id, name, email, password, course, year)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (student_id, name, email, hashed_password, course, year))

        mysql.connection.commit()
        cur.close()
        return "<h4 style='color:green;'>Registration Successful ✅</h4>"

    return render_template('register.html')

# ==========================
# STUDENT LOGIN
# ==========================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT student_id, name, password FROM student WHERE student_id = %s", (student_id,))
        student = cur.fetchone()
        cur.close()

        if not student:
            return "<h4 style='color:red;'>Student Not Found ❌</h4>"

        if check_password_hash(student[2], password):
            session.clear()
            session['student_id'] = student[0]
            session['student_name'] = student[1]
            return redirect(url_for('dashboard'))
        else:
            return "<h4 style='color:red;'>Invalid Password ❌</h4>"

    return render_template('login.html')

# ==========================
# ADMIN LOGIN
# ==========================

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT admin_id, name, password, dept_id, level
            FROM admin
            WHERE username = %s
        """, (username,))
        admin = cur.fetchone()
        cur.close()

        # ❌ Admin not found
        if not admin:
            return "<h4 style='color:red;'>Admin Not Found ❌</h4>"

        # 🔍 DEBUG (remove later)
        print("ENTERED:", password)
        print("DB HASH:", admin[2])
        print("CHECK:", check_password_hash(admin[2], password))
        
        print("DB HOST:", app.config['MYSQL_HOST'])
        print("DB NAME:", app.config['MYSQL_DB'])
        print("ADMIN ROW:", admin)
        # ✅ Password check
        if check_password_hash(admin[2], password):
            session.clear()
            session['admin_id'] = admin[0]
            session['admin_name'] = admin[1]
            session['admin_dept'] = admin[3]
            session['admin_level'] = admin[4]

            return redirect(url_for('admin_dashboard'))

        else:
            return "<h4 style='color:red;'>Invalid Password ❌</h4>"

    return render_template('admin_login.html')
#==============================
# ADMINN PASSWORD FIX (TEMPORARY)
#==============================
@app.route('/fix_admin_password')
def fix_admin_password():
    from werkzeug.security import generate_password_hash

    new_hash = generate_password_hash("admin123")

    cur = mysql.connection.cursor()
    cur.execute("UPDATE admin SET password=%s", (new_hash,))
    mysql.connection.commit()
    cur.close()

    return f"Password Updated Successfully ✅ <br>{new_hash}"

# ==========================
# ADMIN DASHBOARD (FIXED)
# ==========================
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    admin_level = session['admin_level']
    admin_dept = session['admin_dept']

    cur = mysql.connection.cursor()

    # ================= AUTO ESCALATION =================
    cur.execute("""
        SELECT grievance_id, current_level
        FROM grievance
        WHERE status != 'Resolved'
          AND DATEDIFF(CURDATE(), created_date) >= 2
    """)

    old_grievances = cur.fetchall()

    for g in old_grievances:
        gid = g[0]
        level = g[1]

        if level < 3:
            cur.execute("""
                UPDATE grievance
                SET current_level = current_level + 1,
                    status = 'Auto Escalated'
                WHERE grievance_id = %s
            """, (gid,))

            cur.execute("""
                INSERT INTO grievance_log
                (grievance_id, action_by, status, remarks)
                VALUES (%s, %s, %s, %s)
            """, (gid, None,
                  'Auto Escalated',
                  'System auto-escalated after 2 days delay'))

    mysql.connection.commit()

    # ================= SUPER ADMIN =================
    if admin_level == 4:
        cur.execute("""
            SELECT grievance_id, student_id, category, severity_level,
                   priority_score, status, created_date, description
            FROM grievance
            ORDER BY grievance_id DESC
        """)
        grievances = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM grievance")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM grievance WHERE status='Pending'")
        pending = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM grievance WHERE status='In Progress'")
        in_progress = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM grievance WHERE status='Resolved'")
        resolved = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM grievance WHERE status='Rejected'")
        rejected = cur.fetchone()[0]

    # ================= DEAN =================
    elif session.get('admin_name') == 'Dean':

        cur.execute("""
            SELECT grievance_id, student_id, category, severity_level,
                   priority_score, status, created_date, description
            FROM grievance
            WHERE current_level = 3
            ORDER BY grievance_id DESC
        """)
        grievances = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM grievance WHERE current_level = 3")
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM grievance
            WHERE current_level = 3 AND status='Pending'
        """)
        pending = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM grievance
            WHERE current_level = 3 AND status='In Progress'
        """)
        in_progress = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM grievance
            WHERE current_level = 3 AND status='Resolved'
        """)
        resolved = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM grievance
            WHERE current_level = 3 AND status='Rejected'
        """)
        rejected = cur.fetchone()[0]

    # ================= OTHER ADMINS =================
    else:

        # 🔥 FIXED: removed current_level filter
        cur.execute("""
            SELECT grievance_id, student_id, category, severity_level,
                   priority_score, status, created_date, description
            FROM grievance
            WHERE dept_id = %s
            ORDER BY grievance_id DESC
        """, (admin_dept,))
        grievances = cur.fetchall()

        cur.execute("""
            SELECT COUNT(*) FROM grievance
            WHERE dept_id = %s
        """, (admin_dept,))
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM grievance
            WHERE dept_id = %s AND status='Pending'
        """, (admin_dept,))
        pending = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM grievance
            WHERE dept_id = %s AND status='In Progress'
        """, (admin_dept,))
        in_progress = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM grievance
            WHERE dept_id = %s AND status='Resolved'
        """, (admin_dept,))
        resolved = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM grievance
            WHERE dept_id = %s AND status='Rejected'
        """, (admin_dept,))
        rejected = cur.fetchone()[0]

    cur.close()

    return render_template(
        'admin_dashboard.html',
        grievances=grievances,
        name=session['admin_name'],
        total=total,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved,
        rejected=rejected
    )
# ==========================
# ADMIN PERFORMANCE MONITORING (SUPER ADMIN)
# ==========================
@app.route('/admin_performance')
def admin_performance():

    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    # Only Super Admin allowed
    if session.get('admin_level') != 4:
        return "Access Denied ❌"

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT 
        a.name,
        d.dept_name,

        COUNT(gl.log_id) AS total_actions,

        COALESCE(SUM(CASE 
            WHEN LOWER(gl.status) = 'resolved' 
            THEN 1 ELSE 0 
        END), 0) AS resolved_count,

        COALESCE(SUM(CASE 
            WHEN LOWER(gl.status) = 'rejected' 
            THEN 1 ELSE 0 
        END), 0) AS rejected_count,

        COALESCE(SUM(CASE 
            WHEN LOWER(gl.status) = 'escalated' 
            THEN 1 ELSE 0 
        END), 0) AS escalated_count

    FROM admin a

    LEFT JOIN department d 
        ON a.dept_id = d.dept_id

    LEFT JOIN grievance_log gl 
        ON gl.action_by = a.admin_id

    WHERE a.level != 4

    GROUP BY a.admin_id, a.name, d.dept_name

    ORDER BY total_actions DESC
    """)

    performance = cur.fetchall()
    cur.close()

    return render_template(
        "admin_performance.html",
        performance=performance
    )
# ==========================
# RESOLVE / REJECT GRIEVANCE
# ==========================
@app.route('/resolve/<int:gid>', methods=['POST'])
def resolve_grievance(gid):

    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    action = request.form['action']
    remarks = request.form['remarks']
    admin_id = session['admin_id']

    if not remarks.strip():
        return "<h4 style='color:red;'>Remarks cannot be empty ❌</h4>"

    cur = mysql.connection.cursor()

    # Update grievance status
    cur.execute("""
        UPDATE grievance
        SET status = %s
        WHERE grievance_id = %s
    """, (action, gid))

    # Insert log entry
    cur.execute("""
        INSERT INTO grievance_log
        (grievance_id, action_by, status, remarks, updated_date)
        VALUES (%s, %s, %s, %s, NOW())
    """, (gid, admin_id, action, remarks))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('admin_dashboard'))
# ==========================
# ESCALATE
# ==========================
@app.route('/escalate/<int:gid>')
def escalate_grievance(gid):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    cur = mysql.connection.cursor()

    # Get current level of grievance
    cur.execute("""
        SELECT current_level
        FROM grievance
        WHERE grievance_id = %s
    """, (gid,))
    result = cur.fetchone()

    if not result:
        cur.close()
        return redirect(url_for('admin_dashboard'))

    current_level = result[0]

    # 🔥 Escalate only till level 3
    if current_level < 3:
        new_level = current_level + 1

        cur.execute("""
            UPDATE grievance
            SET current_level = %s,
                status = 'In Progress'
            WHERE grievance_id = %s
        """, (new_level, gid))

        cur.execute("""
            INSERT INTO grievance_log (grievance_id, action_by, status, remarks)
            VALUES (%s, %s, %s, %s)
        """, (gid, session['admin_id'], 'Escalated', 'Escalated to next level'))

    else:
        # Already at dean level → cannot escalate further
        cur.execute("""
            UPDATE grievance
            SET status = 'In Progress'
            WHERE grievance_id = %s
        """, (gid,))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('admin_dashboard'))
# ==========================
# UPDATE SEVERITY (ADMIN OVERRIDE)
# ==========================
@app.route('/update_severity/<int:gid>', methods=['POST'])
def update_severity(gid):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    new_severity = request.form['severity_level']

    # Update priority based on severity
    priority_score = 3 if new_severity == "High" else 2 if new_severity == "Medium" else 1

    cur = mysql.connection.cursor()

    # Update grievance table
    cur.execute("""
        UPDATE grievance
        SET severity_level=%s, priority_score=%s
        WHERE grievance_id=%s
    """, (new_severity, priority_score, gid))

    # Insert log entry
    cur.execute("""
        INSERT INTO grievance_log (grievance_id, status, remarks)
        VALUES (%s, %s, %s)
    """, (gid, "Severity Updated", f"Severity changed to {new_severity} by admin"))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('admin_dashboard'))
# ==========================
# VIEW HISTORY(ADMIN)
# ==========================
@app.route('/view_history/<int:gid>')
def view_history(gid):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT status, remarks, updated_date
        FROM grievance_log
        WHERE grievance_id = %s
        ORDER BY updated_date ASC
    """, (gid,))

    logs = cur.fetchall()
    cur.close()

    return render_template("view_history.html",
                           logs=logs,
                           grievance_id=gid)
# ==========================
# STUDENT DASHBOARD
# ==========================
@app.route('/dashboard')
def dashboard():

    if 'student_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT student_id, name, course, year
        FROM student
        WHERE student_id = %s
    """, (session['student_id'],))

    student = cur.fetchone()

    cur.close()

    return render_template(
        'dashboard.html',
        student=student
    )

def smart_detect(description):

    text = description.lower()

    # ==========================
    # DEPARTMENT KEYWORDS
    # ==========================
    dept_keywords = {

        "Academic": ["class", "syllabus", "assignment", "attendance", "course"],
        "Faculty": ["teacher", "faculty", "mentor", "professor"],
        "Examination": ["exam", "marks", "result", "grade", "revaluation"],
        "Hostel": ["hostel", "room", "warden", "mess", "water", "electricity"],
        "Library": ["library", "books", "librarian", "study"],
        "Transport": ["bus", "transport", "driver", "route"],
        "Finance": ["fee", "payment", "refund", "scholarship"],
        "Infrastructure": ["building", "classroom", "lab", "maintenance"],
        "Placement": ["placement", "internship", "company", "recruitment"]
    }

    # ==========================
    # SEVERITY KEYWORDS
    # ==========================

    high_severity = [
        "harassment","urgent","violence","marks wrong",
        "result error","fee error","exam issue"
    ]

    medium_severity = [
        "wifi","internet","hostel","transport",
        "library","lab","water"
    ]

    # ==========================
    # DETECT DEPARTMENT
    # ==========================

    detected_dept = "Others"

    for dept, words in dept_keywords.items():
        for word in words:
            if word in text:
                detected_dept = dept
                break

    # ==========================
    # DETECT SEVERITY
    # ==========================

    severity = "Low"
    priority = 1

    for word in high_severity:
        if word in text:
            severity = "High"
            priority = 3
            break

    for word in medium_severity:
        if word in text and severity != "High":
            severity = "Medium"
            priority = 2

    return detected_dept, severity, priority

# ==========================
# RAISE GRIEVANCE
# ==========================
@app.route('/raise_grievance', methods=['GET', 'POST'])
def raise_grievance():

    if 'student_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':

        category = request.form['category']
        description = request.form['description']
        issue_type = request.form.get('issue_type', 'general')

        # 🔥 AI detection
        detected_dept, severity_level, auto_priority = smart_detect(description)

        # 🔥 Synchronize severity with AI priority
        if auto_priority == 3:
           severity_level = "High"
        elif auto_priority == 2:
           severity_level = "Medium"
        else:
           severity_level = "Low"

        student_id = session['student_id']

        # 🔥 If AI cannot detect department → fallback to selected category
        dept_name = detected_dept if detected_dept != "Others" else category

        cur = mysql.connection.cursor()

        # 🔥 Fetch department id
        cur.execute(
            "SELECT dept_id FROM department WHERE dept_name=%s",
            (dept_name,)
        )

        dept = cur.fetchone()

        if not dept:
            cur.close()
            return "<h4 style='color:red;'>Department Not Found ❌</h4>"

        dept_id = dept[0]

        # Priority determined by AI
        priority_score = auto_priority

        # 🔥 Multi-level routing logic
        if dept_id in (1, 4, 6):  # Academic / Faculty / Examination
            if issue_type == "general":
                start_level = 1
            elif issue_type == "mentor":
                start_level = 2
            elif issue_type == "hod":
                start_level = 3
            else:
                start_level = 1
        else:
            start_level = 1

        # 🔥 Insert grievance
        cur.execute("""
            INSERT INTO grievance
            (description, category, priority_score, status,
             severity_level, created_date, student_id, dept_id, current_level)
            VALUES (%s,%s,%s,%s,%s,CURDATE(),%s,%s,%s)
        """, (
            description,
            dept_name,   # ✅ store detected department
            priority_score,
            "Pending",
            severity_level,
            student_id,
            dept_id,
            start_level
        ))

        # 🔥 Get inserted grievance ID
        cur.execute("SELECT LAST_INSERT_ID()")
        gid = cur.fetchone()[0]

        # 🔥 Insert log entry
        cur.execute("""
            INSERT INTO grievance_log
            (grievance_id, action_by, status, remarks)
            VALUES (%s,%s,%s,%s)
        """, (
            gid,
            None,
            'Created',
            'Grievance submitted by student'
        ))

        mysql.connection.commit()
        cur.close()

        return "<h4 style='color:green;'>Grievance Routed to " + dept_name + " Department ✅</h4>"

    return render_template('raise_grievance.html')

# ==========================
# MY GRIEVANCES
# ==========================
@app.route('/my_grievances')
def my_grievances():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT grievance_id, category, severity_level,
               status, created_date, description
        FROM grievance
        WHERE student_id=%s
        ORDER BY grievance_id DESC
    """, (session['student_id'],))

    grievances = cur.fetchall()
    cur.close()

    return render_template('my_grievances.html', grievances=grievances)
# ==========================
# VIEW HISTORY (STUDENT)
# ==========================
@app.route('/history/<int:gid>')
def student_history(gid):
    if 'student_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT status, remarks, updated_date
        FROM grievance_log
        WHERE grievance_id=%s
        ORDER BY log_id ASC
    """, (gid,))

    history = cur.fetchall()
    cur.close()

    return render_template('history.html', history=history)

# ==========================
# LOGOUT
# ==========================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================
# EXPORT PDF REPORT (SUPER ADMIN)
# ==========================
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import pagesizes
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import io
from datetime import datetime

@app.route('/export_pdf')
def export_pdf():

    if 'admin_id' not in session or session['admin_level'] != 4:
        return redirect(url_for('admin_dashboard'))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=pagesizes.A4)
    elements = []

    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph("<b>Student Grievance Management Report</b>", styles['Title']))
    elements.append(Spacer(1, 0.3 * inch))

    # Date
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 0.3 * inch))

    cur = mysql.connection.cursor()

    # Overall Stats
    cur.execute("SELECT COUNT(*) FROM grievance")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM grievance WHERE status='Pending'")
    pending = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM grievance WHERE status='In Progress'")
    in_progress = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM grievance WHERE status='Resolved'")
    resolved = cur.fetchone()[0]

    data = [
        ["Metric", "Count"],
        ["Total Grievances", total],
        ["Pending", pending],
        ["In Progress", in_progress],
        ["Resolved", resolved]
    ]

    table = Table(data, colWidths=[3 * inch, 2 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER')
    ]))

    elements.append(table)
    elements.append(Spacer(1, 0.5 * inch))

    # Department-wise Summary
    elements.append(Paragraph("<b>Department-wise Summary</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.2 * inch))

    cur.execute("""
        SELECT d.dept_name, COUNT(g.grievance_id)
        FROM grievance g
        JOIN department d ON g.dept_id = d.dept_id
        GROUP BY d.dept_name
    """)

    dept_data = [["Department", "Total Grievances"]]

    for row in cur.fetchall():
        dept_data.append([row[0], row[1]])

    cur.close()

    dept_table = Table(dept_data, colWidths=[3 * inch, 2 * inch])
    dept_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER')
    ]))

    elements.append(dept_table)

    doc.build(elements)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="Grievance_Report.pdf",
        mimetype='application/pdf'
    )
if __name__ == '__main__':
    app.run(host='0.0.0.0' , port=10000)