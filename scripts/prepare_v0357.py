"""Build v0.3.57: local, bounded, privacy-minimized lighting diagnostic log."""
import hashlib,json,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'publish.json').read_text('utf-8'))
base=root/'packages/LumePro-0.3.56.zip'
assert manifest['version']=='0.3.56' and hashlib.sha256(base.read_bytes()).hexdigest()==manifest['sha256']
with zipfile.ZipFile(base) as z: files={i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}
def edit(path,pairs):
 key='LumePro/'+path;s=files[key].decode('utf-8')
 for a,b in pairs:
  assert s.count(a)==1,(path,a[:110],s.count(a));s=s.replace(a,b)
 files[key]=s.encode('utf-8')

files['LumePro/app/lighting_log.py']=b'''"""Local session-only diagnostic events. Never record keys, paths, tokens or request bodies."""
from collections import deque
from datetime import datetime,timezone
from threading import Lock
import time

class LightingLog:
 def __init__(self,limit=200):
  self.entries=deque(maxlen=limit);self.lock=Lock();self.recent={}
 def add(self,event,**fields):
  # Only fixed internal event identifiers and numeric/boolean/null data.
  data={k:v for k,v in fields.items() if v is None or type(v) in (int,float,bool)}
  with self.lock:
   self.entries.append({'time':datetime.now(timezone.utc).isoformat(timespec='seconds'),'event':event,**data})
 def changed(self,event,**fields):
  data=tuple(sorted(fields.items()))
  with self.lock:
   now=time.monotonic();last=self.recent.get(event)
   if last and (last[0]==data or now-last[1]<2):return
   self.recent[event]=(data,now)
   self.entries.append({'time':datetime.now(timezone.utc).isoformat(timespec='seconds'),'event':event,**{k:v for k,v in fields.items() if v is None or type(v) in (int,float,bool)}})
 def snapshot(self):
  with self.lock:return [dict(x) for x in self.entries]
 def clear(self):
  with self.lock:self.entries.clear();self.recent.clear()
  self.add('log_cleared')

log=LightingLog()
'''
edit('app/logitech.py',[
 ('from keyhook import SCAN_CODE','from keyhook import SCAN_CODE\nfrom lighting_log import log'),
 ("self._disconnect();self.path=self.find();self.error=", "self._disconnect();self.path=self.find();log.add('sdk_dll_search',found=bool(self.path));self.error="),
 ("    s=self.factory(self.path)\n", "    log.add('sdk_load_start')\n    s=self.factory(self.path)\n    log.add('sdk_loaded',hid=bool(s.hid),scan=bool(s.scan),bitmap=bool(getattr(s,'bitmap',None)))\n"),
 ("     if s.init():break","     ready=bool(s.init());log.add('sdk_init',attempt=attempt+1,accepted=ready)\n     if ready:break"),
 ("     if s.target(4):break","     ready=bool(s.target(4));log.add('sdk_target_per_key',attempt=attempt+1,accepted=ready)\n     if ready:break"),
 ("self.saved=bool(s.save and s.save());self.device=s;","self.saved=bool(s.save and s.save());log.add('sdk_selected',saved_previous=self.saved);self.device=s;"),
 ("    code=getattr(exc,'winerror',None)","    code=getattr(exc,'winerror',None)\n    log.add('sdk_select_failed',winerror=code if type(code) is int else None)"),
 ("     try:self._write(f)\n     except Exception as exc:self.error='SDK送信失敗: '+str(exc)[:180];self.cache.clear()","     before=self.accepted\n     try:\n      self._write(f)\n      log.changed('sdk_frame_result',accepted=self.accepted>before,rejected=bool(self.failed),bitmap=self.output_mode=='bitmap',nonblack=any(v.lower()!='#000000' for v in f.values()))\n     except Exception as exc:\n      self.error='SDK送信失敗: '+str(exc)[:180];self.cache.clear();log.changed('sdk_write_exception',winerror=getattr(exc,'winerror',None))")
])
edit('app/server.py',[
 ('import pathlib\n','import pathlib\nimport platform\nfrom lighting_log import log\n'),
 ('updater=Updater(ROOT.parent,DATA)','updater=Updater(ROOT.parent,DATA)\nlog.add("session_start",windows=os.name=="nt",frozen=bool(getattr(sys,"frozen",False)))'),
 ("  present=desktop.presence() if desktop.supported() and p['backend']=='logitech' else True","  present=desktop.presence() if desktop.supported() and p['backend']=='logitech' else True\n  log.add('auto_connect_attempt',manual=manual,hid_present=present,live=p['live'],input_enabled=p['hook'],auto=p['auto'])"),
 ("  return ok\n\nresident_tray", "  log.add('auto_connect_result',accepted=bool(ok),active=backend.device is not None)\n  return ok\n\nresident_tray"),
 ("  try:self.post_api()\n  except (ValueError,TypeError,KeyError,IndexError,AttributeError,OverflowError,RecursionError):return self.send_json({'error':'invalid request'},400)","  try:self.post_api()\n  except (ValueError,TypeError,KeyError,IndexError,AttributeError,OverflowError,RecursionError):return self.send_json({'error':'invalid request'},400)"),
 (" def send_json(self,obj,status=200):\n  data=",''' def send_json(self,obj,status=200):
  # Record only selected lighting operations, never the body or typed keys.
  if self.command=='POST':
   event={'/api/auto_connect':'auto_connect_api','/api/connect':'connect_api','/api/select':'select_api','/api/lighting_reconnect':'repair_api','/api/led_test':'led_test_api','/api/live':'live_api','/api/keyhook':'input_enable_api','/api/bitmap_config':'bitmap_config_api'}.get(urlparse(self.path).path)
   if event and status!=403 and isinstance(obj,dict):
    h=obj.get('hardware') or {};e=obj.get('engine') or {}
    log.add(event,http=status,accepted=obj.get('ok') is True,active=h.get('active',e.get('active')),error=bool(obj.get('error') or h.get('error')))
  data='''),
 ("  if path=='/api/diagnostic':",'''  if path=='/api/lighting_log':
   p=prefs.load();h=backend.status();e=engine.status();info=h.get('device_info') or {}
   # Current HID check, independent of stored preferences. No device paths/serials.
   present=desktop.presence() if desktop.supported() else None
   snapshot={'version':updater.version,'os':platform.system(),'os_version':platform.version(),'architecture_bits':64 if sys.maxsize>2**32 else 32,'frozen':bool(getattr(sys,'frozen',False)),
    'settings':{k:p[k] for k in ('auto','live','hook','backend','method','bitmap_enabled','motion_profile')},
    'hid_present':present,'sdk':{'dll_found':bool(info.get('dll')),'connected':h.get('connected'),'active':h.get('active'),'hid_api':info.get('hid_available'),'scan_api':info.get('scan_available'),'bitmap_api':h.get('bitmap_available'),'output_mode':h.get('output_mode'),'sent':h.get('sent',0),'accepted_calls':h.get('accepted_calls',0),'failed_count':len(h.get('failed_keys') or {}),'error_present':bool(h.get('error'))},
    'engine':{k:e.get(k) for k in ('active','running','frames','lit_keys','target_fps')},'engine_error_present':bool(e.get('error')),'input_enabled':bool(keys.enabled),'physical_led_verified':False}
   return self.send_json({'snapshot':snapshot,'events':log.snapshot()})
  if path=='/api/diagnostic':'''),
 ("  if path=='/api/lighting_reconnect':","  if path=='/api/lighting_log_clear':\n   log.clear();return self.send_json({'ok':True})\n  if path=='/api/lighting_reconnect':")
])
edit('app/index.html',[
 ('<div id="sdkMethodRow" class="setting-line" hidden>', '''<details id="lightingLogPanel"><summary>接続・点灯ログ</summary><p class="field-help">光らない場合にログを開き、コピーして送ってください。入力したキー、個人名、ファイルパスは記録しません。ログは現在の起動中だけ保存されます。</p><div class="diag-buttons"><button type="button" id="lightingLogRefresh" class="button secondary">更新</button><button type="button" id="lightingLogCopy" class="button secondary">ログをコピー</button><button type="button" id="lightingLogClear" class="button secondary">クリア</button></div><textarea id="lightingLogText" aria-label="接続・点灯ログ" readonly spellcheck="false" rows="12"></textarea><p id="lightingLogStatus" class="field-help" role="status" aria-live="polite"></p></details><div id="sdkMethodRow" class="setting-line" hidden>''')
])
edit('app/app.js',[
 ('function setupEvents(){', '''async function refreshLightingLog(){
 const response=await apiFetch('/api/lighting_log');
 if(!response.ok)throw Error('ログを取得できません');
 const data=await response.json();
 $('lightingLogText').value=JSON.stringify(data,null,2);
 return $('lightingLogText').value;
}
function setupLightingLog(){
 const status=$('lightingLogStatus');
 async function refresh(){try{await refreshLightingLog();status.textContent='ログを更新しました'}catch(e){status.textContent=e.message}}
 $('lightingLogPanel').addEventListener('toggle',()=>{if($('lightingLogPanel').open)refresh()});
 $('lightingLogRefresh').onclick=refresh;
 $('lightingLogCopy').onclick=async()=>{try{const value=await refreshLightingLog();try{await navigator.clipboard.writeText(value);status.textContent='コピーしました'}catch{$('lightingLogText').focus();$('lightingLogText').select();status.textContent='選択しました。Ctrl+Cでコピーしてください。'}}catch(e){status.textContent=e.message}};
 $('lightingLogClear').onclick=async()=>{try{await post('/api/lighting_log_clear',{});await refresh()}catch(e){status.textContent=e.message}};
}
function setupEvents(){
 setupLightingLog();''')
])
files['LumePro/app/style.css']+=b'\n#lightingLogText{display:block;width:100%;box-sizing:border-box;min-height:180px;resize:vertical;margin-top:10px;padding:10px;border:1px solid #484b52;border-radius:6px;background:#16181d;color:#e2e5ee;font:12px/1.6 Consolas,monospace;white-space:pre;}\n'
edit('tests/test_v0320_channel.py',[("'version':'0.3.56'","'version':'0.3.57'")])
edit('tests/test_server.py',[
 ("'/api/status','/api/preferences','/api/token'","'/api/status','/api/preferences','/api/lighting_log','/api/token'"),
 ("   assert status['hardware']['active'] is False","   assert status['hardware']['active'] is False\n   log=request(port,'/api/lighting_log',token)\n   assert log['snapshot']['version']=='0.3.57' and log['snapshot']['physical_led_verified'] is False\n   assert any(x['event']=='session_start' for x in log['events'])\n   assert 'token' not in json.dumps(log) and 'device_info' not in json.dumps(log)\n   assert request(port,'/api/lighting_log_clear',token,{})['ok']\n   assert request(port,'/api/lighting_log',token)['events'][0]['event']=='log_cleared'")
])
files['LumePro/tests/test_v0357_lighting_log.py']=b'''import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from lighting_log import LightingLog,log
from logitech import LogitechBackend
from test_logitech import FakeSDK

def test_bounded_log_and_no_string_payloads():
 l=LightingLog(3)
 for i in range(5):l.add('test',attempt=i,secret='not included')
 assert [x['attempt'] for x in l.snapshot()]==[2,3,4]
 assert all('secret' not in x for x in l.snapshot())
 l.clear();assert [x['event'] for x in l.snapshot()]==['log_cleared']

def test_sdk_attempts_recorded_without_paths():
 log.clear()
 b=LogitechBackend(FakeSDK,lambda:Path('private-user-path.dll'))
 try:
  assert b.connect() and b.select(0)
  events=log.snapshot()
  assert any(x['event']=='sdk_dll_search' and x['found'] for x in events)
  assert any(x['event']=='sdk_init' and x['accepted'] for x in events)
  assert any(x['event']=='sdk_target_per_key' and x['accepted'] for x in events)
  assert 'private-user-path' not in str(events)
 finally:b.close()
'''
meta=json.loads(files['LumePro/app/version.json']);meta['version']='0.3.57'
files['LumePro/app/version.json']=(json.dumps(meta)+'\n').encode()
notes="""## v0.3.57
- 設定に「接続・点灯ログ」を追加。SDKの検出・初期化・ターゲット指定、接続と点灯命令の成否、実機反映状態を確認できます。
- ログの更新・コピー・クリアに対応。現在の起動中の最大200件のみ保持し、キー入力内容・ファイルパス・認証情報は収集しません。
- SDKの成功は物理点灯を保証しないため、実機での発光確認が必要です。
- v0.3.56の点灯修復を含みます。既存エフェクト・速度・フェードは変更していません。
"""
files['LumePro/RELEASE_NOTES_JA.md']=notes.encode()
files['LumePro/CHANGELOG.md']=notes.encode()+b'\n'+files['LumePro/CHANGELOG.md']
target=root/'packages/LumePro-0.3.57.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,data in sorted(files.items()):
  entry=zipfile.ZipInfo(name,date_time=(2026,11,28,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,data)
digest=hashlib.sha256(target.read_bytes()).hexdigest()
(root/'publish.json').write_text(json.dumps({'version':'0.3.57','sha256':digest})+'\n',encoding='utf-8')
print(target,digest)
