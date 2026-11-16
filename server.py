import os
from flask import Flask, send_file, Response, request
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

rooms = {}

@app.route('/')
def index():
    # index.html'e DOKUNMUYORUZ. Sadece servis anında script ekliyoruz.
    with open('index.html', 'r', encoding='utf-8') as f:
        html = f.read()
    inject = '<script src="/online.js"></script>'
    if '</body>' in html:
        html = html.replace('</body>', inject + '\n</body>', 1)
    else:
        html += inject
    return Response(html, mimetype='text/html')

@app.route('/online.js')
def online_js():
    return send_file('online.js', mimetype='application/javascript')

@app.route('/health')
def health():
    return 'ok', 200

def _payload(rid):
    return [{'id': s, 'name': n} for s, n in rooms[rid]['players'].items()]

def _find_room(sid):
    for rid, r in rooms.items():
        if sid in r['players']:
            return rid
    return None

def _remove(sid):
    rid = _find_room(sid)
    if not rid:
        return
    del rooms[rid]['players'][sid]
    leave_room(rid)
    if not rooms[rid]['players']:
        del rooms[rid]
    else:
        socketio.emit('room-update', {'roomId': rid, 'players': _payload(rid)}, to=rid)

@socketio.on('join-room')
def on_join(data):
    rid = str(data.get('roomId', '')).strip()
    name = str(data.get('name', '')).strip() or 'Oyuncu'
    if not rid:
        emit('join-result', {'ok': False, 'error': 'Oda kodu gerekli'})
        return
    r = rooms.setdefault(rid, {'players': {}})
    if len(r['players']) >= 8:
        emit('join-result', {'ok': False, 'error': 'Oda dolu'})
        return
    join_room(rid)
    r['players'][request.sid] = name
    emit('join-result', {'ok': True, 'roomId': rid}, to=request.sid)
    socketio.emit('room-update', {'roomId': rid, 'players': _payload(rid)}, to=rid)

@socketio.on('game-action')
def on_action(data):
    rid = _find_room(request.sid)
    if not rid:
        return
    socketio.emit('game-action', {
        'from': request.sid,
        'name': rooms[rid]['players'].get(request.sid, '?'),
        'type': data.get('type'),
        'payload': data.get('payload'),
    }, to=rid)

@socketio.on('disconnect')
def on_dc():
    _remove(request.sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
