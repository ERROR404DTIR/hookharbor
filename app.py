#!/usr/bin/env python3
"""HookHarbor: loopback-only webhook inbox."""
import argparse, json, sqlite3, threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

MAX_BODY = 1_000_000
PAGE = r"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HookHarbor</title><style>
*{box-sizing:border-box}body{margin:0;background:#101522;color:#e6edf7;font:14px system-ui}header{padding:22px 4vw;background:#171f30;border-bottom:1px solid #34425b;display:flex;justify-content:space-between;align-items:center}h1{margin:0;color:#89b4fa;letter-spacing:2px}.layout{display:grid;grid-template-columns:minmax(250px,35%) 1fr;min-height:80vh}.list{border-right:1px solid #34425b;padding:18px}.detail{padding:20px;min-width:0}.event{padding:13px;margin:8px 0;background:#1b2639;border:1px solid #34425b;border-radius:10px;cursor:pointer}.event:hover{border-color:#89b4fa}.muted{color:#a6adc8}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0b1020;padding:16px;border-radius:10px;max-height:55vh;overflow:auto}button{background:#263751;color:white;border:1px solid #52698b;border-radius:8px;padding:8px 12px;cursor:pointer}@media(max-width:700px){.layout{grid-template-columns:1fr}.list{border-right:0;border-bottom:1px solid #34425b}}</style>
<header><div><h1>HOOKHARBOR</h1><span class="muted">Private local webhook inbox</span></div><button onclick="load()">Refresh</button></header><main class="layout"><section class="list"><h3>Incoming events</h3><div id="events"></div></section><section class="detail"><h3 id="title">Select an event</h3><div id="meta" class="muted"></div><h4>Headers</h4><pre id="headers">—</pre><h4>Body</h4><pre id="body">—</pre></section></main>
<script>
async function load(){let a=await fetch('/api/events').then(r=>r.json());let box=document.querySelector('#events');box.replaceChildren();a.forEach(e=>{let d=document.createElement('div');d.className='event';d.textContent='#'+e.id+' · '+e.method+' '+e.path+' · '+e.created;d.onclick=()=>show(e.id);box.append(d)})}
async function show(id){let e=await fetch('/api/events/'+id).then(r=>r.json());document.querySelector('#title').textContent='#'+e.id+' '+e.method+' '+e.path;document.querySelector('#meta').textContent=e.created+' · '+e.content_type+' · '+e.size+' bytes';document.querySelector('#headers').textContent=JSON.stringify(e.headers,null,2);document.querySelector('#body').textContent=e.body_text||'(binary or empty body)'}
load();setInterval(load,5000)
</script>"""
def connect(db):
    c=sqlite3.connect(db, timeout=10)
    c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,created TEXT,method TEXT,path TEXT,headers TEXT,body BLOB,content_type TEXT,client TEXT)")
    c.commit()
    return c
def save_event(db, method, path, headers, body, content_type, client):
    with connect(db) as c:
        cur=c.execute("INSERT INTO events(created,method,path,headers,body,content_type,client) VALUES(?,?,?,?,?,?,?)",
          (datetime.now(timezone.utc).isoformat(timespec="seconds"),method,path,json.dumps(dict(headers)),body,content_type,client))
        return cur.lastrowid
def event_list(db, limit=100):
    with connect(db) as c:
        rows=c.execute("SELECT id,created,method,path,content_type,length(body) FROM events ORDER BY id DESC LIMIT ?",(max(1,min(int(limit),500)),)).fetchall()
    return [dict(id=r[0],created=r[1],method=r[2],path=r[3],content_type=r[4],size=r[5] or 0) for r in rows]
def event_detail(db, ident):
    with connect(db) as c:
        row=c.execute("SELECT id,created,method,path,headers,body,content_type,client FROM events WHERE id=?",(ident,)).fetchone()
    if not row:return None
    body=row[5] or b""
    try: text=body.decode("utf-8")
    except UnicodeDecodeError: text=""
    return dict(id=row[0],created=row[1],method=row[2],path=row[3],headers=json.loads(row[4]),body_text=text,content_type=row[6],client=row[7],size=len(body))
def handler_for(db):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send_json(self, code, obj):
            data=json.dumps(obj,ensure_ascii=False).encode()
            self.send_response(code);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            path=urlparse(self.path)
            if path.path=="/":
                data=PAGE.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
            if path.path=="/api/events": self.send_json(200,event_list(db,parse_qs(path.query).get("limit",[100])[0]));return
            if path.path.startswith("/api/events/"):
                try: item=event_detail(db,int(path.path.rsplit("/",1)[1]))
                except ValueError:item=None
                self.send_json(200 if item else 404,item or {"error":"not found"});return
            self.send_json(404,{"error":"not found"})
        def do_POST(self):
            length=int(self.headers.get("Content-Length","0") or 0)
            if length<0 or length>MAX_BODY:self.send_json(413,{"error":"body limit is 1 MB"});return
            body=self.rfile.read(length)
            ident=save_event(db,"POST",self.path,self.headers,body,self.headers.get("Content-Type",""),self.client_address[0])
            self.send_json(202,{"ok":True,"id":ident})
        do_PUT=do_POST
        do_PATCH=do_POST
        do_DELETE=do_POST
    return Handler
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--port",type=int,default=8765);p.add_argument("--db",default="hookharbor.sqlite3");a=p.parse_args()
    connect(a.db).close()
    server=ThreadingHTTPServer(("127.0.0.1",a.port),handler_for(a.db));server.daemon_threads=True
    print(f"HookHarbor: http://127.0.0.1:{a.port}  (loopback only; Ctrl+C to stop)")
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=="__main__":main()
