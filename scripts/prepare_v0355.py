"""Reproducible compatibility release built on the verified v0.3.54 source."""
import hashlib,json,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'publish.json').read_text('utf-8'))
base=root/'packages/LumePro-0.3.54.zip'
assert manifest['version']=='0.3.54' and hashlib.sha256(base.read_bytes()).hexdigest()==manifest['sha256']
with zipfile.ZipFile(base) as z:
 files={i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}
def edit(path,pairs):
 key='LumePro/'+path
 s=files[key].decode('utf-8')
 for a,b in pairs:
  assert s.count(a)==1,(path,a[:100],s.count(a));s=s.replace(a,b)
 files[key]=s.encode('utf-8')

edit('app/desktop.py',[
 ('''    """Read current HID enumeration, not the stale registry inventory. None = unknown."""
    try:
        import hid
        return bool(hid.enumerate(0x046d,0xc339))
    except Exception:return None''','''    """Current Logitech HID keyboard presence; None means enumeration is inconclusive."""
    try:
        import hid
        devices=hid.enumerate(0x046d,0)
        # Preserve the known PRO X device, and recognize keyboards by their
        # standard HID usage rather than hard-coding a single product ID.
        if any(d.get('product_id')==0xc339 or
               (d.get('usage_page')==1 and d.get('usage')==6) for d in devices):
            return True
        # Some drivers expose only a vendor interface or omit usage metadata.
        # In that case do not automatically disconnect a working SDK session.
        if any(not d.get('usage_page') or not d.get('usage') or
               d.get('usage_page',0)>=0xff00 for d in devices):
            return None
        return False
    except Exception:return None''')])
edit('app/server.py',[
 ('''  if desktop.supported() and p['backend']=='logitech' and desktop.presence() is not True:return False
  if backend.kind==p['backend'] and backend.device is not None:return True''','''  if backend.kind==p['backend'] and backend.device is not None:return True
  # Do not switch away from an explicitly selected working controller.
  if backend.device is not None:return False
  present=desktop.presence() if desktop.supported() and p['backend']=='logitech' else True'''),
 ('''  ok=backend.connect(p['backend'])
  if ok:
   idx=choose_device''','''  ok=backend.connect(p['backend'])
  if ok and present is not True:
   # Detect the installed DLL but require explicit selection when the HID
   # device cannot be verified. Never silently start LED output on unknown hardware.
   backend.impl.error=('Logicoolキーボードが検出されません。USB接続・G HUBを確認してください。手動で接続先を選択できます。' if present is False else 'USB機器の自動判定ができません。G HUBでキーボードを確認し、接続先を手動で選択してください。')
   return False
  if ok:
   idx=choose_device'''),
 ("   if not p['auto'] or not p['editor']:continue","   if not p['auto']:continue"),
 ("   if backend.device is None and now-last_attempt>=12 and (p['live'] or p['device_name']):","   if backend.device is None and now-last_attempt>=12 and (p['backend']=='logitech' or p['live'] or p['device_name']):"),
 ("     if backend.device is None and not stop.is_set():auto_connect(p)","     if backend.device is None and not stop.is_set() and prefs.load()['auto']:auto_connect(prefs.load())"),
 ("'error':None if ok else '自動接続できませんでした。接続先を確認してください。'","'error':None if ok else (backend.status().get('error') or '自動接続できませんでした。接続先を確認してください。')")])
edit('app/logitech.py',[
 ("import ctypes\nimport os","import ctypes\nfrom contextlib import ExitStack\nimport os"),
 ("  self.dll=ctypes.CDLL(str(path))","""  # Resolve dependencies in the installed G HUB SDK/application directory,
  # not the current working directory or a downloaded DLL beside the EXE.
  with ExitStack() as stack:
   if os.name=='nt' and hasattr(os,'add_dll_directory'):
    for directory in (Path(path).parent,Path(path).parent.parent):
     if directory.is_dir():stack.enter_context(os.add_dll_directory(str(directory)))
   self.dll=ctypes.CDLL(str(path))"""),
 ("G HUBのLED SDK DLLが見つかりません（Pythonの32/64bitも確認）","G HUBのLED SDKが見つかりません。公式G HUBをインストールまたは修復して起動し、デバイスを再検出してください。"),
 ("LogiLedInit が失敗しました。G HUBを起動してください","LogiLedInit が失敗しました。G HUBを起動し、ゲーム・アプリによる照明制御を許可してください。接続は自動で再試行されます。"),
 ("    self._disconnect();self.error='Logicool SDK: '+str(exc)[:180];return False","""    self._disconnect()
    code=getattr(exc,'winerror',None)
    hint={126:'SDKの依存DLLが不足しています。G HUBを修復してください。',193:'SDKの32/64bitが一致しません。G HUBを修復してください。',5:'SDKへのアクセスが拒否されました。G HUBとLUMEを同じユーザー権限で起動してください。'}.get(code,'')
    self.error='Logicool SDK: '+str(exc)[:180]+(' '+hint if hint else '')
    return False""")])
edit('app/app.js',[
 ("r.error||hardware.error||'自動接続に失敗しました'","hardware.error||r.error||'自動接続に失敗しました'"),
 ("$('connectionMessage').textContent=h.error || (connected?","$('connectionMessage').textContent=h.error || (connected&&!isLive?'接続済みです。ライティング画面の「実機へ反映」をONにしてください。':connected?"),
 ("$('connectTopBtn').title=connected?'設定 · キーボード接続済み':'設定 · キーボード未接続';","$('connectTopBtn').title=connected?'設定 · キーボード接続済み':'設定 · キーボード未接続：G HUBを起動して接続を確認';")])
edit('tests/test_desktop.py',[
 ('''    fake=Mock();monkeypatch.setitem(sys.modules,'hid',fake);fake.enumerate.return_value=[{}]
    assert desktop.presence() is True;fake.enumerate.assert_called_with(0x046d,0xc339)
    fake.enumerate.return_value=[];assert desktop.presence() is False
    fake.enumerate.side_effect=OSError;assert desktop.presence() is None''','''    fake=Mock();monkeypatch.setitem(sys.modules,'hid',fake)
    fake.enumerate.return_value=[{'product_id':0xc339}]
    assert desktop.presence() is True;fake.enumerate.assert_called_with(0x046d,0)
    fake.enumerate.return_value=[{'product_id':0xc123,'usage_page':1,'usage':6}]
    assert desktop.presence() is True
    fake.enumerate.return_value=[{'product_id':0xc123,'usage_page':1,'usage':2}]
    assert desktop.presence() is False
    fake.enumerate.return_value=[{'product_id':0xc123,'usage_page':0xff00,'usage':1}]
    assert desktop.presence() is None
    fake.enumerate.return_value=[{}];assert desktop.presence() is None
    fake.enumerate.return_value=[];assert desktop.presence() is False
    fake.enumerate.side_effect=OSError;assert desktop.presence() is None''')])
edit('tests/test_v0320_channel.py',[("'version':'0.3.54'","'version':'0.3.55'")])
files['LumePro/tests/test_v0355_compatibility.py']='''import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from logitech import LogitechBackend

def test_missing_sdk_explains_required_installation():
    b=LogitechBackend(dll_finder=lambda:None)
    try:
        assert not b.connect()
        assert 'G HUB' in b.status()['error']
        assert not b.status()['active']
    finally:b.close()

def test_sdk_load_error_explains_repair():
    def fail(path):
        e=OSError('DLL load failed');e.winerror=126;raise e
    b=LogitechBackend(sdk_factory=fail,dll_finder=lambda:Path('test.dll'))
    try:
        assert b.connect()
        assert not b.select(0)
        assert 'G HUBを修復' in b.status()['error']
        assert not b.status()['active']
    finally:b.close()
'''.encode()
meta=json.loads(files['LumePro/app/version.json']);meta['version']='0.3.55'
files['LumePro/app/version.json']=(json.dumps(meta)+'\n').encode()
notes="""## v0.3.55
- C339以外のLogicoolキーボードを標準HIDキーボード情報から検出できるよう改善。
- 自動判定不能の場合は手動選択を案内し、SDKの検出結果を表示。
- G HUBの起動が遅い初回起動時にも接続を再試行。
- SDK依存DLLの検索をインストール済みG HUBのディレクトリで補助し、読み込みエラーの原因を表示。
- 実機反映OFFの場合の案内を改善。実機出力と入力監視の初期設定は変更していません。
- 発光演算・フェード時間・プリセット・送信間隔はv0.3.54のまま。
- G HUBが必要なこと、SDKの対応機器クラス全体を制御することは従来どおり。別機種の物理点灯は未確認。
"""
files['LumePro/RELEASE_NOTES_JA.md']=notes.encode()
files['LumePro/CHANGELOG.md']=notes.encode()+b'\n'+files['LumePro/CHANGELOG.md']
target=root/'packages/LumePro-0.3.55.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,data in sorted(files.items()):
  entry=zipfile.ZipInfo(name,date_time=(2026,11,28,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
  z.writestr(entry,data)
digest=hashlib.sha256(target.read_bytes()).hexdigest()
(root/'publish.json').write_text(json.dumps({'version':'0.3.55','sha256':digest})+'\n',encoding='utf-8')
print(target,digest)
