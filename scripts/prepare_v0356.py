"""v0.3.56: explicit one-click lighting recovery and SDK readiness retries."""
import hashlib,json,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'publish.json').read_text('utf-8'))
base=root/'packages/LumePro-0.3.55.zip'
assert manifest['version']=='0.3.55' and hashlib.sha256(base.read_bytes()).hexdigest()==manifest['sha256']
with zipfile.ZipFile(base) as z:
 files={i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}
def edit(path,pairs):
 key='LumePro/'+path
 s=files[key].decode('utf-8')
 for a,b in pairs:
  assert s.count(a)==1,(path,a[:100],s.count(a));s=s.replace(a,b)
 files[key]=s.encode('utf-8')

edit('app/logitech.py',[
 ("""   p=Path(root)/'LGHUB'/'sdks'/name
   if p.is_file():return p""","""   for folder in (Path(root)/'LGHUB'/'sdks',Path(root)/'LGHUB'):
    p=folder/name
    if p.is_file():return p"""),
 ("""    if not s.init():raise RuntimeError('LogiLedInit が失敗しました。 G HUBを起動し、ゲーム・アプリによる照明制御を許可してください。接続は自動で再試行されます。')""".replace("。 G","。G"),"""    # The agent can be alive before its lighting IPC is ready.
    for attempt in range(3):
     if s.init():break
     if attempt<2:time.sleep(.45)
    else:raise RuntimeError('LogiLedInit が失敗しました。G HUBを起動し、ゲーム・アプリによる照明制御を許可してください。接続は自動で再試行されます。')"""),
 ("""    if not s.target(4):raise RuntimeError('per-key RGB のターゲット指定に失敗しました')""","""    for attempt in range(5):
     if s.target(4):break
     if attempt<4:time.sleep(.35)
    else:raise RuntimeError('per-key RGB のターゲット指定に失敗しました。G HUBのキーボード認識・照明制御の許可を確認してください。')""")
])
edit('app/server.py',[
 ("def auto_connect(p):\n if not p['auto']:return False","def auto_connect(p,manual=False):\n if not p['auto'] and not manual:return False"),
 ("  if backend.kind==p['backend'] and backend.device is not None:return True\n  # Do not switch away from an explicitly selected working controller.\n  if backend.device is not None:return False","  if backend.kind==p['backend'] and backend.device is not None and not manual:return True\n  # Explicit repair may reinitialize the same controller, never another one.\n  if backend.device is not None and (not manual or backend.kind!=p['backend']):return False"),
 ("  if ok and present is not True:","  if ok and present is not True and not manual and not (present is None and p['device_name'] and p['live']):"),
 ("    if present is not True:continue","    if present is not True and not (present is None and p['device_name'] and p['live']):continue"),
 ("  if path=='/api/connect':","""  if path=='/api/lighting_reconnect':
   # Explicit user action. No input monitoring is enabled by this endpoint.
   if obj.get('confirm') is not True:return self.send_json({'ok':False,'error':'点灯修復の確認が必要です'},400)
   with connection_lock:
    p=prefs.load()
    if p['backend']!='logitech' or (backend.device is not None and backend.kind!='logitech'):
     return self.send_json({'ok':False,'error':'この修復はLogicool SDK専用です。設定で接続方式を確認してください。'},400)
    ok=auto_connect(p,manual=True)
    # Restore-saved may have restarted the animation; stop before the explicit
    # uniform test, so it cannot overwrite the test frame immediately.
    engine.enable(False)
    return self.send_json({'ok':ok,'hardware':backend.status(),'error':None if ok else backend.status().get('error')})
  if path=='/api/connect':""")
])
edit('app/index.html',[
 ('<div class="connection-msg" id="connectionMessage">','<div class="settings-actions"><button type="button" id="repairLighting" class="button secondary">接続・点灯を修復</button></div><div class="connection-msg" id="repairLightingResult" role="status" aria-live="polite" hidden></div><div class="connection-msg" id="connectionMessage">')
])
edit('app/app.js',[
 ("async function setLive(on){","""let repairBusy=false;
function reactiveNeedsInput(){const layers=state.layers.filter(l=>l.enabled&&(soloLayerId==null||soloLayerId===l.id));return layers.length>0&&layers.every(l=>REACTIVE.has(l.type))&&!Object.keys(state.keyColors||{}).length}
function repairMessage(msg){const el=$('repairLightingResult');el.hidden=false;el.textContent=msg;toast(msg)}
async function repairLighting(){
 if(repairBusy||connectionBusy||liveBusy)return false;
 if(preferences.backend!=='logitech'){navigate('settings');toast('Logicool SDKを選択してください');return false}
 const needsHook=reactiveNeedsInput()&&!isHook;
 if(!await askConfirm('Logicool SDKに再接続し、キーボード全体を一時的に点灯してから現在のエフェクトを再開します。対応RGB機器全体に送信されます。'+(needsHook?' 現在のエフェクトはキー入力が必要です。入力反応も有効にします（入力内容は保存しません）。':'')))return false;
 repairBusy=true;connectionBusy=true;$('repairLighting').disabled=true;$('liveToggle').disabled=true;
 try{
  const r=await post('/api/lighting_reconnect',{confirm:true});hardware=r.hardware;isLive=false;$('liveToggle').checked=false;updateConnectionUI();updateDiag();
  if(!r.ok)throw Error(r.error||hardware.error||'SDKに接続できません');
  const t=await post('/api/led_test',{index:null,color:'#606060'});hardware=t.hardware;updateConnectionUI();
  if(!t.ok)throw Error(hardware.error||'SDKが全体点灯を拒否しました');
  await new Promise(resolve=>setTimeout(resolve,1200));
  if(needsHook){await toggleHook(true);if(!isHook)throw Error('入力反応を開始できませんでした')}
  if(!state.running)togglePlayback();
  if(!await setLive(true))throw Error('実機反映を開始できませんでした');
  await savePreferences({live:true,hook:isHook,editor:editorSnapshot()});
  if(reactiveNeedsInput()||state.layers.some(l=>l.enabled&&REACTIVE.has(l.type)))await post('/api/pulse',{code:'KeyG'});
  repairMessage('SDKが点灯要求を受理し、実機反映を開始しました。光らなかった場合はG HUBのゲーム・アプリの照明制御許可と、Windowsの動的ライティングの優先順位を確認してください。');
  return true;
 }catch(e){
  // Never leave the diagnostic colour active after a failed repair.
  try{if(hardware.active){await post('/api/led_test',{index:null,color:'#000000'});}}catch{}
  repairMessage('点灯修復: '+e.message);navigate('settings');return false;
 }finally{repairBusy=false;connectionBusy=false;$('repairLighting').disabled=false;$('liveToggle').disabled=false;updateConnectionUI()}
}
async function setLive(on){"""),
 ("$('connectionMessage').textContent=h.error || (connected&&!isLive?", "$('repairLighting').hidden=preferences.backend!=='logitech';\n $('connectionMessage').textContent=h.error || (connected&&isLive&&reactiveNeedsInput()&&!isHook?'実機反映ONですが、現在のエフェクトは入力反応OFFのため点灯しません。「接続・点灯を修復」を押してください。':connected&&!isLive?"),
 ("if(on&&!hardware.active){e.target.checked=false;toast('設定画面でキーボードに接続してください');navigate('settings');return}","if(on&&preferences.backend==='logitech'&&(!hardware.active||(reactiveNeedsInput()&&!isHook))){e.target.checked=isLive;await repairLighting();return}if(on&&!hardware.active){e.target.checked=false;toast('設定画面でキーボードに接続してください');navigate('settings');return}"),
 ("$('autoConnect').onchange=async()=>", "$('repairLighting').onclick=()=>repairLighting();\n $('autoConnect').onchange=async()=>")
])
edit('tests/test_v0320_channel.py',[("'version':'0.3.55'","'version':'0.3.56'")])
files['LumePro/tests/test_v0356_recovery.py']=b'''import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from logitech import LogitechBackend
from test_logitech import FakeSDK

class LateSDK(FakeSDK):
    def __init__(self,path):
        super().__init__(path)
        self.inits=0
        self.targets=0
    def init(self):
        self.inits+=1
        return self.inits>=2
    def target(self,kind):
        self.targets+=1
        assert kind==4
        return self.targets>=3

def test_agent_ready_after_initial_rejection(monkeypatch):
    import logitech
    monkeypatch.setattr(logitech.time,'sleep',lambda _:None)
    b=LogitechBackend(LateSDK,lambda:Path('dummy.dll'))
    try:
        assert b.connect() and b.select(0)
        assert b.sdk.inits==2 and b.sdk.targets==3
        assert b.test_led(None,'#606060')
        assert b.sdk.calls[-1]==('all',38,38,38)
    finally:b.close()

class NeverReady(LateSDK):
    def target(self,kind):
        self.targets+=1
        return False

def test_target_retry_bounded_and_failure_not_active(monkeypatch):
    import logitech
    monkeypatch.setattr(logitech.time,'sleep',lambda _:None)
    instances=[]
    def factory(path):
        s=NeverReady(path);instances.append(s);return s
    b=LogitechBackend(factory,lambda:Path('dummy.dll'))
    try:
        assert b.connect() and not b.select(0)
        assert instances[0].targets==5 and not b.status()['active']
        assert 'G HUB' in b.status()['error']
        assert ('shutdown',) in instances[0].calls
    finally:b.close()
'''
meta=json.loads(files['LumePro/app/version.json']);meta['version']='0.3.56'
files['LumePro/app/version.json']=(json.dumps(meta)+'\n').encode()
notes="""## v0.3.56
- 設定に「接続・点灯を修復」を追加。SDK再接続、短い点灯テスト、現在のエフェクトの再開を一度の操作で行えます。
- 実機反映をONにする際、未接続または入力反応が必要な場合に案内します。入力検出は明示的な確認を得てから開始します。
- G HUBが起動直後の場合のSDK初期化とターゲット指定を再試行。
- G HUBの標準インストール先にあるSDK探索を補強。USB情報が不明でも手動の修復操作から接続可能。
- エフェクトの速度、色、フェード、プリセットの設定は変更していません。
- SDKの応答だけでは実際の発光を確認できないため、物理点灯はユーザーによる確認が必要です。
"""
files['LumePro/RELEASE_NOTES_JA.md']=notes.encode()
files['LumePro/CHANGELOG.md']=notes.encode()+b'\n'+files['LumePro/CHANGELOG.md']
target=root/'packages/LumePro-0.3.56.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,data in sorted(files.items()):
  entry=zipfile.ZipInfo(name,date_time=(2026,11,28,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
  z.writestr(entry,data)
digest=hashlib.sha256(target.read_bytes()).hexdigest()
(root/'publish.json').write_text(json.dumps({'version':'0.3.56','sha256':digest})+'\n',encoding='utf-8')
print(target,digest)
