#!/usr/bin/env python3
"""CareerConnect Local API Server — SQLite backend"""
import sqlite3, json, os, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'careerconnect.db')

# ── DB INIT ──────────────────────────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript("""
    PRAGMA journal_mode=WAL;

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        first_name TEXT,
        last_name TEXT,
        college TEXT,
        major TEXT,
        year TEXT,
        student_id TEXT,
        company_name TEXT,
        industry TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        industry TEXT,
        hq TEXT,
        website TEXT,
        about TEXT,
        contact_name TEXT,
        contact_email TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        company_id INTEGER REFERENCES companies(id),
        type TEXT,
        location TEXT,
        deadline TEXT,
        salary TEXT,
        description TEXT,
        requirements TEXT,
        skills TEXT,
        status TEXT DEFAULT 'active',
        openings INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_name TEXT,
        student_id INTEGER REFERENCES users(id),
        job_id INTEGER REFERENCES jobs(id),
        cover_letter TEXT,
        status TEXT DEFAULT 'under_review',
        notes TEXT,
        applied_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        filename TEXT,
        doc_type TEXT,
        file_size TEXT,
        uploaded_at TEXT DEFAULT (datetime('now'))
    );
    """)

    # Seed sample data if empty
    if not cur.execute("SELECT 1 FROM companies LIMIT 1").fetchone():
        companies = [
            ('Microsoft','Software','Seattle, WA','https://microsoft.com','Leading tech company.','HR Team','recruiting@microsoft.com','approved'),
            ('Google','Technology','Mountain View, CA','https://google.com','Search and cloud leader.','Recruiting','jobs@google.com','approved'),
            ('Amazon','E-Commerce','Seattle, WA','https://amazon.com','E-commerce and AWS.','University Recruiting','university@amazon.com','approved'),
            ('Stripe','Fintech','San Francisco, CA','https://stripe.com','Payments infrastructure.','Talent Team','talent@stripe.com','approved'),
            ('Salesforce','Software','San Francisco, CA','https://salesforce.com','CRM and enterprise SaaS.','Campus Recruiting','campus@salesforce.com','approved'),
            ('TechCorp Inc.','Software','New York, NY','','Startup building dev tools.','John Smith','john@techcorp.com','pending'),
            ('FinBank LLC','Finance','New York, NY','','Regional financial services.','Jane Doe','jane@finbank.com','pending'),
            ('GreenEnergy Co.','Energy','Newark, NJ','','Renewable energy solutions.','Bob Lee','bob@greenenergy.com','pending'),
        ]
        cur.executemany("INSERT INTO companies(name,industry,hq,website,about,contact_name,contact_email,status) VALUES(?,?,?,?,?,?,?,?)", companies)
        con.commit()
        ids = {r[0]:r[1] for r in cur.execute("SELECT name, id FROM companies").fetchall()}
        jobs = [
            ('Software Engineering Intern', ids['Microsoft'], 'Internship','Seattle, WA · Hybrid','Apr 30','$30/hr','Work on real products with our engineering team.','Python, React knowledge preferred','Python,React,Git','active',3),
            ('Data Analyst Intern', ids['Google'], 'Internship','Remote','May 15','$28/hr','Analyze data to drive product decisions.','SQL proficiency required','SQL,Python,Tableau','active',2),
            ('UX Research Intern', ids['Salesforce'], 'Internship','San Francisco, CA','Apr 22','$25/hr','Conduct user research for enterprise SaaS.','UX background preferred','Figma,UX,Research','closing',1),
            ('Cloud Operations Intern', ids['Amazon'], 'Internship','Remote','May 1','$27/hr','Support AWS infrastructure operations.','Linux experience helpful','AWS,Linux,Bash','active',2),
            ('Product Management Intern', ids['Stripe'], 'Internship','New York, NY','May 10','$30/hr','Help define the product roadmap for payments.','Strong analytical skills','Product,SQL,Strategy','active',1),
        ]
        cur.executemany("INSERT INTO jobs(title,company_id,type,location,deadline,salary,description,requirements,skills,status,openings) VALUES(?,?,?,?,?,?,?,?,?,?,?)", jobs)

        users = [
            ('alex@ccny.cuny.edu','password123','student','Alex','Johnson','City College (CCNY)','Computer Science','Junior','23456789',None,None),
            ('admin@careerconnect.cuny.edu','admin123','admin','Maria','Torres',None,None,None,None,None,None),
            ('recruiting@microsoft.com','corp123','company','HR','Microsoft',None,None,None,None,'Microsoft','Software'),
        ]
        cur.executemany("INSERT INTO users(email,password,role,first_name,last_name,college,major,year,student_id,company_name,industry) VALUES(?,?,?,?,?,?,?,?,?,?,?)", users)

        uid = cur.execute("SELECT id FROM users WHERE email='alex@ccny.cuny.edu'").fetchone()[0]
        job_ids = [r[0] for r in cur.execute("SELECT id FROM jobs").fetchall()]
        apps = [
            ('Alex Johnson',uid,job_ids[0],'','under_review'),
            ('Alex Johnson',uid,job_ids[1],'','interviewing'),
            ('Alex Johnson',uid,job_ids[2],'','offer'),
        ]
        cur.executemany("INSERT INTO applications(student_name,student_id,job_id,cover_letter,status) VALUES(?,?,?,?,?)", apps)
        docs = [
            (uid,'Alex_Johnson_Resume_2025.pdf','resume','142 KB'),
            (uid,'Cover_Letter_Microsoft.docx','cover_letter','48 KB'),
            (uid,'Transcript_Spring2025.pdf','transcript','210 KB'),
        ]
        cur.executemany("INSERT INTO documents(user_id,filename,doc_type,file_size) VALUES(?,?,?,?)", docs)

    con.commit()
    con.close()

def query(sql, params=(), one=False):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql, params)
    con.commit()
    result = cur.fetchone() if one else cur.fetchall()
    con.close()
    return result

def execute(sql, params=()):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(sql, params)
    con.commit()
    lid = cur.lastrowid
    con.close()
    return lid

# ── REQUEST HANDLER ──────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass  # quiet

    def send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET,POST,PUT,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET,POST,PUT,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.end_headers()

    def read_body(self):
        length = int(self.headers.get('Content-Length',0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        p = urlparse(self.path).path.rstrip('/')
        qs = parse_qs(urlparse(self.path).query)

        if p == '/api/health':
            self.send_json({'status':'ok','db':DB_PATH})

        elif p == '/api/companies':
            rows = query("SELECT c.*, (SELECT COUNT(*) FROM jobs WHERE company_id=c.id AND status!='closed') as job_count FROM companies c ORDER BY c.name")
            self.send_json([dict(r) for r in rows])

        elif re.match(r'^/api/companies/\d+$', p):
            cid = p.split('/')[-1]
            row = query("SELECT * FROM companies WHERE id=?", (cid,), one=True)
            self.send_json(dict(row) if row else {}, 404 if not row else 200)

        elif p == '/api/jobs':
            rows = query("""
                SELECT j.*, c.name as company_name, c.industry as company_industry,
                       c.hq as company_hq, c.id as cid
                FROM jobs j LEFT JOIN companies c ON j.company_id=c.id
                WHERE j.status != 'closed'
                ORDER BY j.created_at DESC
            """)
            self.send_json([dict(r) for r in rows])

        elif re.match(r'^/api/jobs/\d+$', p):
            jid = p.split('/')[-1]
            row = query("SELECT j.*, c.name as company_name FROM jobs j LEFT JOIN companies c ON j.company_id=c.id WHERE j.id=?", (jid,), one=True)
            self.send_json(dict(row) if row else {}, 404 if not row else 200)

        elif p == '/api/applications':
            uid = qs.get('user_id',[''])[0]
            if uid:
                rows = query("""SELECT a.*, j.title as job_title, c.name as company_name
                    FROM applications a LEFT JOIN jobs j ON a.job_id=j.id
                    LEFT JOIN companies c ON j.company_id=c.id
                    WHERE a.student_id=? ORDER BY a.applied_at DESC""", (uid,))
            else:
                rows = query("""SELECT a.*, j.title as job_title, c.name as company_name
                    FROM applications a LEFT JOIN jobs j ON a.job_id=j.id
                    LEFT JOIN companies c ON j.company_id=c.id
                    ORDER BY a.applied_at DESC""")
            self.send_json([dict(r) for r in rows])

        elif p == '/api/documents':
            uid = qs.get('user_id',[''])[0]
            rows = query("SELECT * FROM documents WHERE user_id=? ORDER BY uploaded_at DESC", (uid,))
            self.send_json([dict(r) for r in rows])

        elif p == '/api/students':
            rows = query("SELECT * FROM users WHERE role='student' ORDER BY first_name")
            self.send_json([dict(r) for r in rows])

        elif p == '/api/stats':
            stats = {
                'students': query("SELECT COUNT(*) as n FROM users WHERE role='student'",one=True)['n'],
                'approved_companies': query("SELECT COUNT(*) as n FROM companies WHERE status='approved'",one=True)['n'],
                'open_jobs': query("SELECT COUNT(*) as n FROM jobs WHERE status IN ('active','closing')",one=True)['n'],
                'applications': query("SELECT COUNT(*) as n FROM applications",one=True)['n'],
                'pending_companies': query("SELECT COUNT(*) as n FROM companies WHERE status='pending'",one=True)['n'],
            }
            self.send_json(stats)

        else:
            self.send_json({'error':'Not found'}, 404)

    def do_POST(self):
        p = urlparse(self.path).path.rstrip('/')
        body = self.read_body()

        if p == '/api/auth/login':
            row = query("SELECT * FROM users WHERE email=? AND password=?", (body.get('email',''), body.get('password','')), one=True)
            if row:
                self.send_json({'success':True,'user':dict(row)})
            else:
                self.send_json({'success':False,'error':'Invalid email or password'}, 401)

        elif p == '/api/auth/register':
            try:
                lid = execute(
                    "INSERT INTO users(email,password,role,first_name,last_name,college,major,year,student_id,company_name,industry) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (body['email'],body['password'],body['role'],body.get('first_name'),body.get('last_name'),
                     body.get('college'),body.get('major'),body.get('year'),body.get('student_id'),
                     body.get('company_name'),body.get('industry'))
                )
                user = query("SELECT * FROM users WHERE id=?", (lid,), one=True)
                self.send_json({'success':True,'user':dict(user)})
            except sqlite3.IntegrityError:
                self.send_json({'success':False,'error':'Email already registered'}, 409)

        elif p == '/api/companies':
            lid = execute(
                "INSERT INTO companies(name,industry,hq,website,about,contact_name,contact_email,status) VALUES(?,?,?,?,?,?,?,?)",
                (body['name'],body.get('industry',''),body.get('hq',''),body.get('website',''),
                 body.get('about',''),body.get('contact_name',''),body.get('contact_email',''),body.get('status','pending'))
            )
            row = query("SELECT * FROM companies WHERE id=?", (lid,), one=True)
            self.send_json({'success':True,'company':dict(row)})

        elif p == '/api/jobs':
            lid = execute(
                "INSERT INTO jobs(title,company_id,type,location,deadline,salary,description,requirements,skills,status,openings) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (body['title'],body['company_id'],body.get('type','Internship'),body.get('location',''),
                 body.get('deadline',''),body.get('salary',''),body.get('description',''),
                 body.get('requirements',''),body.get('skills',''),body.get('status','active'),body.get('openings',1))
            )
            row = query("SELECT j.*, c.name as company_name FROM jobs j LEFT JOIN companies c ON j.company_id=c.id WHERE j.id=?", (lid,), one=True)
            self.send_json({'success':True,'job':dict(row)})

        elif p == '/api/applications':
            existing = query("SELECT id FROM applications WHERE student_id=? AND job_id=?", (body.get('student_id'), body.get('job_id')), one=True)
            if existing:
                self.send_json({'success':False,'error':'Already applied'}, 409)
                return
            lid = execute(
                "INSERT INTO applications(student_name,student_id,job_id,cover_letter,status) VALUES(?,?,?,?,?)",
                (body.get('student_name',''),body.get('student_id'),body.get('job_id'),'','under_review')
            )
            self.send_json({'success':True,'application_id':lid})

        elif p == '/api/documents':
            lid = execute(
                "INSERT INTO documents(user_id,filename,doc_type,file_size) VALUES(?,?,?,?)",
                (body['user_id'],body['filename'],body.get('doc_type','other'),body.get('file_size','—'))
            )
            self.send_json({'success':True,'document_id':lid})

        else:
            self.send_json({'error':'Not found'}, 404)

    def do_PUT(self):
        p = urlparse(self.path).path.rstrip('/')
        body = self.read_body()

        if re.match(r'^/api/companies/\d+$', p):
            cid = p.split('/')[-1]
            fields = {k:v for k,v in body.items() if k in ['name','industry','hq','website','about','contact_name','contact_email','status']}
            if fields:
                sets = ', '.join(f"{k}=?" for k in fields)
                execute(f"UPDATE companies SET {sets} WHERE id=?", list(fields.values())+[cid])
            row = query("SELECT * FROM companies WHERE id=?", (cid,), one=True)
            self.send_json({'success':True,'company':dict(row)})

        elif re.match(r'^/api/jobs/\d+$', p):
            jid = p.split('/')[-1]
            fields = {k:v for k,v in body.items() if k in ['title','type','location','deadline','salary','description','requirements','skills','status','openings']}
            if fields:
                sets = ', '.join(f"{k}=?" for k in fields)
                execute(f"UPDATE jobs SET {sets} WHERE id=?", list(fields.values())+[jid])
            row = query("SELECT j.*, c.name as company_name FROM jobs j LEFT JOIN companies c ON j.company_id=c.id WHERE j.id=?", (jid,), one=True)
            self.send_json({'success':True,'job':dict(row)})

        elif re.match(r'^/api/applications/\d+$', p):
            aid = p.split('/')[-1]
            fields = {k:v for k,v in body.items() if k in ['status','notes']}
            if fields:
                sets = ', '.join(f"{k}=?" for k in fields)
                execute(f"UPDATE applications SET {sets} WHERE id=?", list(fields.values())+[aid])
            self.send_json({'success':True})

        elif re.match(r'^/api/users/\d+$', p):
            uid = p.split('/')[-1]
            fields = {k:v for k,v in body.items() if k in ['first_name','last_name','major','college','year','gpa']}
            if fields:
                sets = ', '.join(f"{k}=?" for k in fields)
                execute(f"UPDATE users SET {sets} WHERE id=?", list(fields.values())+[uid])
            self.send_json({'success':True})

        else:
            self.send_json({'error':'Not found'}, 404)

    def do_DELETE(self):
        p = urlparse(self.path).path.rstrip('/')

        if re.match(r'^/api/companies/\d+$', p):
            cid = p.split('/')[-1]
            execute("DELETE FROM jobs WHERE company_id=?", (cid,))
            execute("DELETE FROM companies WHERE id=?", (cid,))
            self.send_json({'success':True})

        elif re.match(r'^/api/jobs/\d+$', p):
            jid = p.split('/')[-1]
            execute("DELETE FROM applications WHERE job_id=?", (jid,))
            execute("DELETE FROM jobs WHERE id=?", (jid,))
            self.send_json({'success':True})

        elif re.match(r'^/api/documents/\d+$', p):
            did = p.split('/')[-1]
            execute("DELETE FROM documents WHERE id=?", (did,))
            self.send_json({'success':True})

        else:
            self.send_json({'error':'Not found'}, 404)


if __name__ == '__main__':
    init_db()
    PORT = 5050
    server = HTTPServer(('localhost', PORT), Handler)
    print(f'✅ CareerConnect API running at http://localhost:{PORT}')
    print(f'📂 Database: {DB_PATH}')
    print(f'🔑 Demo logins:')
    print(f'   Student  → alex@ccny.cuny.edu / password123')
    print(f'   Admin    → admin@careerconnect.cuny.edu / admin123')
    print(f'   Employer → recruiting@microsoft.com / corp123')
    print(f'   Press Ctrl+C to stop.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n🛑 Server stopped.')
