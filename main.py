import os, json, uuid, time, secrets, threading
from fastapi import FastAPI, Form, File, UploadFile, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DATA_DIR", BASE)  # Railway Volume uchun: DATA_DIR=/data
UP = os.path.join(DATA, "static", "uploads")
os.makedirs(UP, exist_ok=True)
DB = os.path.join(DATA, "db.json")
lock = threading.Lock()
tokens = set()

def seed():
    j = lambda t, co, s, l, ty, k, cat: dict(id=uuid.uuid4().hex[:8], title=t, company=co, salary=s, location=l,
        type=ty, kind=k, category=cat, desc="Batafsil ma'lumot uchun bog'laning.", phone="+998 90 000 00 00",
        receipt="", status="active", created=time.time(), user="admin")
    return dict(admin=dict(surname="isakov", name="isakov", password=""), theme="dark", users={}, chats=[], jobs=[
        j("Frontend dasturchi", "TechUz", "$800-1200", "Toshkent", "Remote", "employer", "IT"),
        j("Qurilish ustasi", "BuildPro", "5 000 000 so'm", "Samarqand", "Full-time", "employer", "Qurilish"),
        j("Matematika o'qituvchisi", "Bilim Markazi", "4 000 000 so'm", "Toshkent", "Part-time", "employer", "Ta'lim"),
        j("Kuryer", "FastGo", "Kunlik 150 000", "Toshkent", "Kunlik", "employer", "Xizmat"),
        j("Ish izlayapman: dizayner", "Aziz K.", "$500", "Remote", "Stajirovka", "seeker", "IT")])

def load():
    if not os.path.exists(DB):
        save(seed())
    with open(DB, encoding="utf-8") as f:
        return json.load(f)

def save(d):
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)

def admin_only(x_token):
    if x_token not in tokens:
        raise HTTPException(401, "Admin huquqi kerak")

app = FastAPI()
app.mount("/static", StaticFiles(directory=os.path.join(DATA, "static")), name="static")

@app.get("/")
def index():
    return FileResponse(os.path.join(BASE, "templates", "index.html"))

class Name(BaseModel):
    name: str
    login: str = ""

@app.post("/api/login")
def login(p: Name):
    name = p.name.strip()
    if not name:
        raise HTTPException(400, "Ism kiriting")
    with lock:
        d = load()
        d["users"][name] = dict(name=name, login=p.login, last=time.time(), visits=d["users"].get(name, {}).get("visits", 0) + 1)
        save(d)
    return dict(name=name)

@app.get("/api/settings")
def settings():
    return dict(theme=load()["theme"])

@app.get("/api/jobs")
def jobs():
    return sorted([j for j in load()["jobs"] if j["status"] == "active"], key=lambda j: -j["created"])

@app.post("/api/jobs")
async def add_job(title: str = Form(...), desc: str = Form(""), salary: str = Form(""), phone: str = Form(...),
                  company: str = Form(""), location: str = Form(""), type: str = Form("Full-time"),
                  kind: str = Form("employer"), category: str = Form("IT"), user: str = Form("mehmon"),
                  receipt: UploadFile = File(...)):
    if not (receipt.content_type or "").startswith("image/"):
        raise HTTPException(400, "Faqat rasm yuklang")
    fn = uuid.uuid4().hex + os.path.splitext(receipt.filename or "x.jpg")[1][:5]
    with open(os.path.join(UP, fn), "wb") as f:
        f.write(await receipt.read())
    job = dict(id=uuid.uuid4().hex[:8], title=title, desc=desc, salary=salary, phone=phone, company=company or user,
               location=location, type=type, kind=kind, category=category, user=user,
               receipt="/static/uploads/" + fn, status="pending", created=time.time())
    with lock:
        d = load(); d["jobs"].append(job); save(d)
    return dict(ok=True)

class AdminLogin(BaseModel):
    surname: str
    name: str
    password: str = ""

@app.post("/api/admin/login")
def admin_login(p: AdminLogin):
    a = load()["admin"]
    if p.surname.strip().lower() == a["surname"] and p.name.strip().lower() == a["name"] and p.password == a["password"]:
        t = secrets.token_hex(16); tokens.add(t)
        return dict(token=t)
    raise HTTPException(401, "Ism yoki familiya noto'g'ri")

@app.get("/api/admin/pending")
def pending(x_token: str = Header("")):
    admin_only(x_token)
    return [j for j in load()["jobs"] if j["status"] == "pending"]

@app.post("/api/admin/jobs/{jid}/{action}")
def moderate(jid: str, action: str, x_token: str = Header("")):
    admin_only(x_token)
    with lock:
        d = load()
        if action == "approve":
            for j in d["jobs"]:
                if j["id"] == jid: j["status"] = "active"
        else:
            d["jobs"] = [j for j in d["jobs"] if j["id"] != jid]
        save(d)
    return dict(ok=True)

@app.get("/api/admin/stats")
def stats(x_token: str = Header("")):
    admin_only(x_token)
    d = load()
    return dict(users=sorted(d["users"].values(), key=lambda u: -u["last"]),
                active=sum(j["status"] == "active" for j in d["jobs"]),
                pending=sum(j["status"] == "pending" for j in d["jobs"]))

class Sett(BaseModel):
    theme: str = ""
    surname: str = ""
    name: str = ""
    password: str = None

@app.post("/api/admin/settings")
def set_settings(p: Sett, x_token: str = Header("")):
    admin_only(x_token)
    with lock:
        d = load()
        if p.theme in ("dark", "light"): d["theme"] = p.theme
        if p.surname: d["admin"]["surname"] = p.surname.strip().lower()
        if p.name: d["admin"]["name"] = p.name.strip().lower()
        if p.password is not None: d["admin"]["password"] = p.password
        save(d)
    return dict(ok=True)

# ---- Chat ----
class Msg(BaseModel):
    user: str
    text: str

@app.post("/api/chat")
def chat_send(m: Msg):
    with lock:
        d = load(); d["chats"].append(dict(user=m.user, frm="user", text=m.text, t=time.time(), read=False)); save(d)
    return dict(ok=True)

@app.get("/api/chat/{user}")
def chat_get(user: str):
    with lock:
        d = load()
        for c in d["chats"]:
            if c["user"] == user and c["frm"] == "admin": c["read"] = True
        save(d)
    return [c for c in d["chats"] if c["user"] == user]

@app.get("/api/admin/chats")
def admin_chats(user: str = "", x_token: str = Header("")):
    admin_only(x_token)
    with lock:
        d = load()
        if user:
            for c in d["chats"]:
                if c["user"] == user and c["frm"] == "user": c["read"] = True
            save(d)
    users = {}
    for c in d["chats"]:
        u = users.setdefault(c["user"], dict(user=c["user"], unread=0, last=""))
        u["last"] = c["text"]
        if c["frm"] == "user" and not c["read"]: u["unread"] += 1
    return dict(users=list(users.values()), msgs=[c for c in d["chats"] if c["user"] == user])

@app.post("/api/admin/chat")
def admin_reply(m: Msg, x_token: str = Header("")):
    admin_only(x_token)
    with lock:
        d = load(); d["chats"].append(dict(user=m.user, frm="admin", text=m.text, t=time.time(), read=False)); save(d)
    return dict(ok=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
