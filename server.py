#!/usr/bin/env python3
"""TravelBloom backend: SQLite database + JSON API + static page. Standard library only.
Run:  python server.py     then open http://localhost:8000
Default admin login: admin@travelbloom.com / Admin@123  (change it after first login)"""
import hashlib, hmac, json, os, re, secrets, sqlite3, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(HERE, 'travelbloom.db')
PORT = int(os.environ.get('PORT', 8000))
CATS = ('hotels', 'flights', 'trains', 'buses', 'cruises', 'holidays')
SESSION_TTL = 30 * 86400


def db():
    c = sqlite3.connect(DB_FILE)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c


def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + '$' + hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), 200_000).hex()


def check_pw(pw, stored):
    return hmac.compare_digest(hash_pw(pw, stored.split('$')[0]), stored)


def put_item(c, i):
    c.execute('INSERT INTO items(id,category,name,sub,rating,badge,img,features,old_price,new_price,note,meta) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
              (i['id'], i['category'], i['name'], i.get('sub', ''), i.get('rating', ''), i.get('badge', ''), i.get('img', ''),
               json.dumps(i.get('features', [])), i.get('oldPrice', ''), i.get('newPrice', ''), i.get('note', ''), json.dumps(i.get('meta', {}))))


def item_out(r):
    return {'id': r['id'], 'category': r['category'], 'name': r['name'], 'sub': r['sub'], 'rating': r['rating'], 'badge': r['badge'],
            'img': r['img'], 'features': json.loads(r['features'] or '[]'), 'oldPrice': r['old_price'], 'newPrice': r['new_price'],
            'note': r['note'], 'meta': json.loads(r['meta'] or '{}')}


def init():
    c = db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT,
        password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, created REAL);
    CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY, category TEXT NOT NULL, name TEXT NOT NULL, sub TEXT, rating TEXT, badge TEXT,
        img TEXT, features TEXT, old_price TEXT, new_price TEXT, note TEXT, meta TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS bookings(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        item_id TEXT, title TEXT, price TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY, user_id INTEGER, name TEXT, email TEXT, phone TEXT, method TEXT,
        category TEXT, urgency TEXT, booking TEXT, details TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS payments(id TEXT PRIMARY KEY, booking_id TEXT NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        amount INTEGER NOT NULL, method TEXT NOT NULL, detail TEXT, status TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
    for col in ("status TEXT NOT NULL DEFAULT 'Confirmed'", 'traveller_name TEXT', 'traveller_email TEXT', 'traveller_phone TEXT'):
        try: c.execute('ALTER TABLE bookings ADD COLUMN ' + col)  # upgrade older databases; ignored if the column exists
        except sqlite3.OperationalError: pass
    if not c.execute('SELECT 1 FROM items LIMIT 1').fetchone():
        for i in json.load(open(os.path.join(HERE, 'seed.json'), encoding='utf-8')):
            put_item(c, i)
    if not c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        c.execute("INSERT INTO users(name,email,password,role) VALUES('Admin','admin@travelbloom.com',?,'admin')", (hash_pw('Admin@123'),))
    c.commit()
    c.close()


BANKS = ('SBI', 'HDFC Bank', 'ICICI Bank', 'Axis Bank', 'Kotak Mahindra Bank')


def luhn(n):
    tot, alt = 0, False
    for ch in reversed(n):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9: d -= 9
        tot += d
        alt = not alt
    return tot % 10 == 0


class Err(Exception):
    def __init__(self, code, msg):
        self.code, self.msg = code, msg


def need(cond, msg, code=400):
    if not cond:
        raise Err(code, msg)


def user_out(u):
    return {'id': u['id'], 'name': u['name'], 'email': u['email'], 'role': u['role']}


def new_session(c, uid):
    t = secrets.token_urlsafe(32)
    c.execute('INSERT INTO sessions(token,user_id,created) VALUES(?,?,?)', (t, uid, time.time()))
    c.commit()
    return t


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, obj=None, raw=None, ctype='application/json'):
        data = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code)
        for k, v in (('Content-Type', ctype + '; charset=utf-8'), ('Content-Length', str(len(data))), ('Access-Control-Allow-Origin', '*'),
                     ('Access-Control-Allow-Headers', 'Content-Type, Authorization'), ('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS')):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        try:
            return json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
        except ValueError:
            raise Err(400, 'Invalid JSON')

    def user(self, c):
        t = (self.headers.get('Authorization') or '').replace('Bearer ', '')
        r = c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.created>?', (t, time.time() - SESSION_TTL)).fetchone()
        return r

    def handle_any(self, m):
        p = urlparse(self.path).path
        if m == 'OPTIONS':
            return self.send(204, raw=b'')
        if m == 'GET' and p in ('/', '/index.html'):
            return self.send(200, raw=open(os.path.join(HERE, 'index.html'), 'rb').read(), ctype='text/html')
        need(p.startswith('/api/'), 'Not found', 404)
        c = db()
        try:
            u = self.user(c)
            b = self.body() if m == 'POST' else {}
            r = self.api(c, m, p, u, b)
            c.commit()
            self.send(200, r)
        finally:
            c.close()

    def api(self, c, m, p, u, b):
        s = lambda k: str(b.get(k) or '').strip()
        if (m, p) == ('POST', '/api/register'):
            name, email, pw = s('name'), s('email').lower(), s('password')
            need(name and re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$', email), 'Enter a valid name and email address.')
            need(len(pw) >= 6, 'Password must be at least 6 characters.')
            need(not c.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone(), 'An account with this email already exists.', 409)
            uid = c.execute('INSERT INTO users(name,email,phone,password) VALUES(?,?,?,?)', (name, email, s('phone'), hash_pw(pw))).lastrowid
            return {'token': new_session(c, uid), 'user': user_out(c.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())}
        if (m, p) == ('POST', '/api/login'):
            ident = s('identifier').lower()
            r = c.execute('SELECT * FROM users WHERE email=? OR (phone!="" AND phone=?)', (ident, ident)).fetchone()
            need(r and check_pw(s('password'), r['password']), 'Incorrect email/mobile or password.', 401)
            return {'token': new_session(c, r['id']), 'user': user_out(r)}
        if (m, p) == ('POST', '/api/google'):  # demo only: real Google OAuth needs a client ID
            r = c.execute("SELECT * FROM users WHERE email='googleuser@gmail.com'").fetchone()
            if not r:
                c.execute("INSERT INTO users(name,email,password) VALUES('Google Traveler','googleuser@gmail.com',?)", (hash_pw(secrets.token_hex(8)),))
                r = c.execute("SELECT * FROM users WHERE email='googleuser@gmail.com'").fetchone()
            return {'token': new_session(c, r['id']), 'user': user_out(r)}
        if (m, p) == ('POST', '/api/reset'):  # demo: no email delivery, so it resets directly
            need(len(s('password')) >= 6, 'Password must be at least 6 characters.')
            n = c.execute('UPDATE users SET password=? WHERE email=?', (hash_pw(s('password')), s('email').lower())).rowcount
            need(n, 'No account found with that email.', 404)
            return {'ok': True}
        if (m, p) == ('GET', '/api/items'):
            return {'items': [item_out(r) for r in c.execute('SELECT * FROM items ORDER BY created_at, rowid')]}
        if (m, p) == ('POST', '/api/tickets'):
            tid = s('id') or 'TBS-%d' % secrets.randbelow(900000 + 100000)
            c.execute('INSERT OR REPLACE INTO tickets(id,user_id,name,email,phone,method,category,urgency,booking,details) VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (tid, u and u['id'], s('name'), s('email'), s('phone'), s('method'), s('category'), s('urgency'), s('booking'), s('details')))
            return {'id': tid}
        need(u, 'Please log in first.', 401)
        if (m, p) == ('GET', '/api/me'):
            return {'user': user_out(u)}
        if (m, p) == ('POST', '/api/logout'):
            c.execute('DELETE FROM sessions WHERE user_id=?', (u['id'],)); return {'ok': True}
        if (m, p) == ('GET', '/api/bookings'):
            return {'bookings': [dict(r) for r in c.execute('''SELECT b.id, b.item_id, b.title, b.price, b.created_at AS date, b.status,
                p.id AS paymentId, p.detail AS paidWith, p.status AS paymentStatus
                FROM bookings b LEFT JOIN payments p ON p.booking_id=b.id WHERE b.user_id=? ORDER BY b.rowid DESC''', (u['id'],))]}
        if (m, p) == ('POST', '/api/bookings'):
            it = c.execute('SELECT * FROM items WHERE id=?', (s('item_id'),)).fetchone()
            need(it, 'That listing is no longer available.', 404)
            bid = 'TB-%06d' % (100000 + secrets.randbelow(900000))
            c.execute('INSERT INTO bookings(id,user_id,item_id,title,price) VALUES(?,?,?,?,?)', (bid, u['id'], it['id'], it['name'], it['new_price']))
            return {'id': bid, 'title': it['name'], 'price': it['new_price'], 'date': time.strftime('%Y-%m-%d')}
        if (m, p) == ('POST', '/api/checkout'):  # payment + booking are created together, only if payment succeeds (TEST MODE: simulated gateway)
            it = c.execute('SELECT * FROM items WHERE id=?', (s('item_id'),)).fetchone()
            need(it, 'That listing is no longer available.', 404)
            amount = int(re.sub(r'\D', '', it['new_price'] or '') or 0)
            need(amount, 'Missing booking details.')
            t = b.get('traveller') if isinstance(b.get('traveller'), dict) else {}
            tn, te, tp = str(t.get('name') or '').strip(), str(t.get('email') or '').strip(), re.sub(r'[\s\-().]', '', str(t.get('phone') or ''))
            need(tn, 'Enter the traveller name.')
            need(re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$', te), 'Enter a valid email for the voucher.')
            method = s('method')
            if method == 'upi':
                upi = s('upi')
                need(re.match(r'^[\w.\-]{2,}@[a-zA-Z]{2,}$', upi), 'Enter a valid UPI ID, like name@okbank.')
                detail = 'UPI ' + re.sub(r'^(.{2}).*(@.*)$', r'\1***\2', upi)
            elif method == 'card':
                cd = b.get('card') if isinstance(b.get('card'), dict) else {}
                n = re.sub(r'\s', '', str(cd.get('number') or ''))
                need(re.match(r'^\d{13,19}$', n) and luhn(n), 'That card number is not valid.')
                mm = re.match(r'^(\d{2})/(\d{2})$', str(cd.get('expiry') or ''))
                need(mm and 1 <= int(mm.group(1)) <= 12 and (2000 + int(mm.group(2)), int(mm.group(1))) >= (time.localtime().tm_year, time.localtime().tm_mon),
                     'Card expiry is invalid or in the past.')
                need(re.match(r'^\d{3,4}$', str(cd.get('cvv') or '')), 'Enter the 3 or 4 digit CVV.')
                need(str(cd.get('name') or '').strip(), 'Enter the name on the card.')
                need(not n.endswith('0002'), 'Your bank declined this card. Try another payment method.', 402)  # test: simulated decline
                detail = {'4': 'Visa', '5': 'Mastercard', '3': 'Amex'}.get(n[0], 'Card') + ' \u2022\u2022\u2022\u2022 ' + n[-4:]  # never store full number or CVV
            elif method == 'netbanking':
                need(s('bank') in BANKS, 'Choose your bank.')
                detail = 'Net Banking \u2013 ' + s('bank')
            else:
                raise Err(400, 'Choose a payment method.')
            bid, pid = 'TB-%06d' % (100000 + secrets.randbelow(900000)), 'PAY-%06d' % (100000 + secrets.randbelow(900000))
            price = '\u20b9' + format(amount, ',')
            c.execute('INSERT INTO bookings(id,user_id,item_id,title,price,status,traveller_name,traveller_email,traveller_phone) VALUES(?,?,?,?,?,?,?,?,?)',
                      (bid, u['id'], it['id'], it['name'], price, 'Confirmed', tn[:120], te, tp or None))
            c.execute('INSERT INTO payments(id,booking_id,user_id,amount,method,detail,status) VALUES(?,?,?,?,?,?,?)', (pid, bid, u['id'], amount, method, detail, 'Paid'))
            return {'booking': {'id': bid, 'title': it['name'], 'price': price, 'date': time.strftime('%Y-%m-%d'), 'status': 'Confirmed'},
                    'payment': {'id': pid, 'amount': price, 'method': detail, 'status': 'Paid'}}
        if (m, p) == ('POST', '/api/bookings/cancel'):
            n = c.execute("UPDATE bookings SET status='Cancelled' WHERE id=? AND user_id=? AND status='Confirmed'", (s('id'), u['id'])).rowcount
            need(n, 'Booking not found or already cancelled.', 404)
            c.execute("UPDATE payments SET status='Refund initiated' WHERE booking_id=?", (s('id'),))
            return {'ok': True}
        if p.startswith('/api/items'):
            need(u['role'] == 'admin', 'Admin access required.', 403)
            if (m, p) == ('POST', '/api/items'):
                need(s('category') in CATS and s('name') and s('newPrice'), 'Category, name and price are required.')
                i = {k: b.get(k) for k in ('name', 'sub', 'rating', 'badge', 'img', 'features', 'oldPrice', 'newPrice', 'note', 'meta')}
                i.update(category=s('category'), id=s('category')[0] + '_' + secrets.token_hex(3))
                i['features'] = [str(f)[:80] for f in (i['features'] or [])][:12]
                i['meta'] = i['meta'] if isinstance(i['meta'], dict) else {}
                put_item(c, i)
                return item_out(c.execute('SELECT * FROM items WHERE id=?', (i['id'],)).fetchone())
            if m == 'DELETE':
                n = c.execute('DELETE FROM items WHERE id=?', (p.rsplit('/', 1)[1],)).rowcount
                need(n, 'Listing not found.', 404)
                return {'ok': True}
        raise Err(404, 'Not found')

    def run(self, m):
        try:
            self.handle_any(m)
        except Err as e:
            self.send(e.code, {'error': e.msg})
        except Exception as e:
            self.send(500, {'error': 'Server error: %s' % e})

    do_GET = lambda self: self.run('GET')
    do_POST = lambda self: self.run('POST')
    do_DELETE = lambda self: self.run('DELETE')
    do_OPTIONS = lambda self: self.run('OPTIONS')


if __name__ == '__main__':
    init()
    print('TravelBloom running at http://localhost:%d  (database: %s)' % (PORT, DB_FILE))
    ThreadingHTTPServer(('0.0.0.0', PORT), H).serve_forever()
