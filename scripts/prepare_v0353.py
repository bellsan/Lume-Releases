"""Reproducibly prepare v0.3.53 from the verified v0.3.52 source archive."""
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'packages/LumePro-0.3.52.zip'
TARGET=ROOT/'packages/LumePro-0.3.53.zip'
EXPECTED='9adc7b7c946a243f99e9df7a298d2e5f9bcad3be935878536381aa0143cfe681'
assert hashlib.sha256(BASE.read_bytes()).hexdigest()==EXPECTED
with zipfile.ZipFile(BASE) as z:
    files={i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}

def get(name):
    return files['LumePro/'+name].decode('utf-8')
def put(name,src):
    files['LumePro/'+name]=src.encode('utf-8')
def replace(src,old,new,count=1):
    assert src.count(old)==count,(old[:120],src.count(old),count)
    return src.replace(old,new)

js=get('app/app.js')
# The three previously synchronous handlers now await the common accessible dialog.
for old,new in [
    ("$('bitmapAssign').onclick=()=>","$('bitmapAssign').onclick=async()=>"),
    ("$('bitmapEnable').onclick=()=>","$('bitmapEnable').onclick=async()=>"),
    ("$('resetBtn').addEventListener('click',()=>","$('resetBtn').addEventListener('click',async()=>")
]:
    js=replace(js,old,new)
js,n=re.subn(r'(?<![\w.])confirm\(', 'await askConfirm(',js)
assert n>=12,n
dialog="""
function askConfirm(message){
 const d=$('appConfirmDialog');
 if(d.open)return Promise.resolve(false);
 $('appConfirmText').textContent=message;
 d.returnValue='cancel';
 const origin=document.activeElement;
 return new Promise(resolve=>{
  const done=()=>{origin?.focus({preventScroll:true});resolve(d.returnValue==='accept')};
  d.addEventListener('close',done,{once:true});
  d.oncancel=e=>{e.preventDefault();d.close('cancel')};
  d.onkeydown=e=>e.stopPropagation();
  d.showModal();$('appConfirmCancel').focus();
 });
}
"""
js=replace(js,'const $=id=>document.getElementById(id);','const $=id=>document.getElementById(id);\n'+dialog)
js=replace(js,"document.addEventListener('keydown',e=>{\n  if(e.key==='Escape')","document.addEventListener('keydown',e=>{\n  if($('appConfirmDialog').open)return;\n  if(e.key==='Escape')")
js=replace(js,"if(!$('modalBackdrop').hidden){toast('新しいバージョンがあります。設定から確認できます。')}","if(!$('modalBackdrop').hidden||$('appConfirmDialog').open){toast('更新来てるよん。設定から確認できます。')}")
js=replace(js,"title='新しいバージョンがあります'","title='更新来てるよん'")
js=replace(js,"available?'更新可能 · v'+r.version","available?'更新来てるよん · v'+r.version")
js=replace(js,"phase==='ready'?'検証完了':phase==='applying'?'更新を適用中':'ダウンロード中'","phase==='ready'?'ダウンロード・検証完了':phase==='applying'?'再起動の準備・適用中':'ダウンロード・検証中'")
js=replace(js,"$('updateProgressText').textContent=(s.progress||0)+'%';","$('updateProgressText').textContent=phase==='applying'?'再起動中…':phase==='ready'?'準備完了':(s.progress||0)+'%';")
js=replace(js,"msg='設定を保持して再起動しています。この画面は自動で再接続します。'","msg='設定を保存し、更新ファイルを適用しています。再起動までこのままお待ちください。'")
js=replace(js,"const r=await post('/api/update/apply',{});if(!r.ok)throw Error(r.error||'更新を開始できませんでした');renderUpdate({...updateStatus,phase:'applying'});reconnectAfterUpdate(expected,previous)","renderUpdate({...updateStatus,phase:'applying'});await new Promise(requestAnimationFrame);const r=await post('/api/update/apply',{});if(!r.ok)throw Error(r.error||'更新を開始できませんでした');reconnectAfterUpdate(expected,previous)")
js=replace(js,"catch(e){renderUpdate(updateStatus);toast(e.message)}finally{updateBusy=false;$('updateAction').disabled=false}","catch(e){renderUpdate({...updateStatus,phase:'ready'});toast(e.message)}finally{updateBusy=false;$('updateAction').disabled=false}")
# Do not leave enabled controls / an artificial 100% while the helper is preparing.
js=replace(js,"$('updateProgressBar').style.width=(s.progress||0)+'%';","$('updateProgressBar').style.width=(phase==='applying'?96:Math.min(95,s.progress||0))+'%';")
js=replace(js,"$('updateProgressWrap').querySelector('[role=progressbar]').setAttribute('aria-valuenow',String(s.progress||0));","$('updateProgressWrap').querySelector('[role=progressbar]').setAttribute('aria-valuenow',String(phase==='applying'?96:Math.min(95,s.progress||0)));")
put('app/app.js',js)
html=get('app/index.html')
html=replace(html,'</body></html>','''<dialog id="appConfirmDialog" class="app-confirm-dialog" aria-labelledby="appConfirmTitle" aria-describedby="appConfirmText"><form method="dialog"><header><span class="app-confirm-brand">LUME / PRO</span><h2 id="appConfirmTitle">操作の確認</h2></header><p id="appConfirmText"></p><footer><button id="appConfirmCancel" class="button secondary" value="cancel" autofocus>キャンセル</button><button id="appConfirmAccept" class="button primary" value="accept">確認</button></footer></form></dialog></body></html>''')
html=html.replace('v0.3.49','v0.3.53')
put('app/index.html',html)
put('app/style.css',get('app/style.css')+"""
/* Shared confirmation dialog: native Lume visual language, no browser origin banner. */
.app-confirm-dialog{width:min(440px,calc(100vw - 40px));max-height:calc(100vh - 40px);padding:0;border:1px solid #484b52;border-radius:8px;background:#24262b;color:#e9eaf0;box-shadow:0 20px 70px #0009;overflow:auto}
.app-confirm-dialog::backdrop{background:#090b11a8;backdrop-filter:blur(2px)}
.app-confirm-dialog[open]{animation:updateEnter .15s ease both}
.app-confirm-dialog form{margin:0}
.app-confirm-dialog header{padding:22px 24px 0}
.app-confirm-brand{font-size:11px;letter-spacing:.12em;color:#aab6ec;font-weight:600}
.app-confirm-dialog h2{font-size:19px;font-weight:600;margin:8px 0 0}
.app-confirm-dialog p{margin:0;padding:16px 24px 24px;font-size:13px;line-height:1.8;white-space:pre-wrap;overflow-wrap:anywhere;color:#d1d3dc}
.app-confirm-dialog footer{display:flex;justify-content:flex-end;gap:9px;border-top:1px solid #393c44;padding:14px 24px;background:#202226}
.app-confirm-dialog footer .button{min-width:94px;min-height:35px}
.app-confirm-dialog footer .primary{background:#b4bef3;color:#151a2a;border-color:#b4bef3}
.update-dialog[data-phase=applying] .update-progress>div{background:linear-gradient(90deg,#7888dd,#d1d9ff,#7888dd);background-size:200% 100%;animation:lumeApplyFlow 1.4s linear infinite}
@keyframes lumeApplyFlow{to{background-position:200% 0}}
@media(prefers-reduced-motion:reduce){.app-confirm-dialog,.update-dialog[data-phase=applying] .update-progress>div{animation:none!important}}
.no-ui-motion .app-confirm-dialog,.no-ui-motion .update-dialog[data-phase=applying] .update-progress>div{animation:none!important}
""")
# Retain the external helper's validation/rollback logic; show the same application
# progress while the old process is being released and the replacement is starting.
frozen=get('app/frozen_update.py')
progress=r'''
$script:progressForm = $null
$script:progressLabel = $null
$script:progressBar = $null
$script:progressIcon = $null
function Show-Progress([string]$message,[int]$value) {
    if (-not $c.show_ui) { return }
    try {
        if (-not $script:progressForm) {
            Add-Type -AssemblyName System.Windows.Forms
            Add-Type -AssemblyName System.Drawing
            $script:progressForm = New-Object Windows.Forms.Form
            $script:progressForm.Text = 'LUME / PRO'
            $script:progressForm.ClientSize = New-Object Drawing.Size(440,136)
            $script:progressForm.StartPosition = 'CenterScreen'
            $script:progressForm.FormBorderStyle = 'FixedDialog'
            $script:progressForm.ControlBox = $false
            $script:progressForm.ShowInTaskbar = $true
            $script:progressForm.TopMost = $true
            $script:progressForm.BackColor = [Drawing.Color]::FromArgb(36,38,43)
            try { if ($c.icon -and [IO.File]::Exists([string]$c.icon)) { $script:progressIcon = New-Object Drawing.Icon([string]$c.icon); $script:progressForm.Icon = $script:progressIcon } } catch {}
            $script:progressLabel = New-Object Windows.Forms.Label
            $script:progressLabel.SetBounds(22,18,396,48)
            $script:progressLabel.ForeColor = [Drawing.Color]::FromArgb(235,237,246)
            $script:progressLabel.Font = New-Object Drawing.Font('Yu Gothic UI',11)
            $script:progressForm.Controls.Add($script:progressLabel)
            $script:progressBar = New-Object Windows.Forms.ProgressBar
            $script:progressBar.SetBounds(22,83,396,14)
            $script:progressBar.Style = 'Continuous'
            $script:progressForm.Controls.Add($script:progressBar)
            $script:progressForm.Show()
        }
        $script:progressLabel.Text = $message
        $script:progressBar.Value = [Math]::Max(0,[Math]::Min(100,$value))
        [Windows.Forms.Application]::DoEvents()
    } catch { [Console]::Error.WriteLine('Optional progress window: '+$_.Exception.Message) }
}
function Pump-Progress {
    if ($script:progressForm) { try { [Windows.Forms.Application]::DoEvents() } catch {} }
}
'''
frozen=replace(frozen,"function Get-Hash([string]$p) {",progress+"\nfunction Get-Hash([string]$p) {")
frozen=replace(frozen,"    # Wait for the worker AND the onefile bootloader/supervisor to exit.\n    Wait-ForExit 60","    Show-Progress '更新の準備中… 現在のウィンドウを閉じています。' 95\n    # Wait for the worker AND the onefile bootloader/supervisor to exit.\n    Wait-ForExit 60\n    Show-Progress '更新ファイルを確認しています…' 96")
frozen=replace(frozen,"        Start-Sleep -Milliseconds 300\n    } while","        Pump-Progress\n        Start-Sleep -Milliseconds 300\n    } while")
frozen=replace(frozen,"    $replaceAttempted = $true","    Show-Progress '新しいバージョンをインストールしています…' 97\n    $replaceAttempted = $true")
frozen=replace(frozen,"    $child = Start-Lume","    Show-Progress 'LUME / PRO を再起動しています…' 98\n    $child = Start-Lume")
frozen=replace(frozen,"        Start-Sleep -Milliseconds 350","        Pump-Progress\n        Start-Sleep -Milliseconds 350")
frozen=replace(frozen,"    Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue","""    if ($c.show_ui) {
        Show-Progress '新しい画面を読み込んでいます…' 99
        $uiMarker = Join-Path ([IO.Path]::GetDirectoryName($marker)) ('native-ui-' + $c.port + '.json')
        $uiUntil = [DateTime]::UtcNow.AddSeconds(30)
        while ([DateTime]::UtcNow -lt $uiUntil) {
            try {
                $uiInfo = Get-Content -LiteralPath $uiMarker -Raw | ConvertFrom-Json
                if ($uiInfo.hwnd -and (Get-Process -Id $uiInfo.pid -ErrorAction SilentlyContinue)) { break }
            } catch {}
            Pump-Progress
            Start-Sleep -Milliseconds 200
        }
    }
    Show-Progress '更新完了' 100
    Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue""")
frozen=replace(frozen,"    $failed = $true\n    $failure", "    Show-Progress '更新に失敗しました。元のバージョンを復元しています…' 97\n    $failed = $true\n    $failure")
frozen=replace(frozen,"    # Only clean files owned by this transaction.","    if ($script:progressForm) { try { $script:progressForm.Close(); $script:progressForm.Dispose() } catch {} }\n    if ($script:progressIcon) { try { $script:progressIcon.Dispose() } catch {} }\n    # Only clean files owned by this transaction.")
frozen=replace(frozen,"    if ($c.ready) { [IO.File]::WriteAllText([string]$c.ready,'ready') }\n    Show-Progress '更新の準備中… 現在のウィンドウを閉じています。' 95", "    Show-Progress '更新の準備中… 現在のウィンドウを閉じています。' 95\n    if ($c.ready) { [IO.File]::WriteAllText([string]$c.ready,'ready') }")
# Load the progress icon from a separate ICO, never from the locked executable.
frozen=replace(frozen,"    script=SCRIPT.replace('__CONFIG__',","""    # A progress window must not load the executable being replaced as an icon DLL.
    try:
        icon=Path(getattr(updater,'root',Path(__file__).resolve().parent.parent))/'app'/'lume-app-icon.ico'
        copy=stage.parent/'progress-icon.ico'
        copy.write_bytes(icon.read_bytes())
        config['icon']=str(copy)
    except OSError:pass
    script=SCRIPT.replace('__CONFIG__',""")
# Retry transient Explorer/Defender file locks without deleting the verified AppData backup.
frozen=replace(frozen,"function Get-Hash([string]$p) {",r"""function Remove-UpdateTemp([string]$file) {
    $until = [DateTime]::UtcNow.AddSeconds(12)
    do {
        try {
            if ([IO.File]::Exists($file)) { [IO.File]::Delete($file) }
            if (-not [IO.File]::Exists($file)) { return }
        } catch {}
        Pump-Progress
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $until)
    [Console]::Error.WriteLine('Temporary file cleanup delayed: '+$file)
}
function Get-Hash([string]$p) {""")
frozen=replace(frozen,"    # The new process must report the nonce from this launch, not stale status.","""    # The independent verified AppData backup is sufficient for rollback.
    # Release the same-directory copy before the new shell icon refresh starts.
    Remove-UpdateTemp $localBackup
    # The new process must report the nonce from this launch, not stale status.""")
frozen=replace(frozen,"            Remove-Item -LiteralPath $file -Force -ErrorAction SilentlyContinue","            Remove-UpdateTemp $file # Remove-Item -LiteralPath $file equivalent, with sharing retries")

put('app/frozen_update.py',frozen)
# Windows Explorer uses a different icon cache than the taskbar and native window.
# Refresh exact EXE paths and only .lnk files which resolve to our executable.
desktop=get('app/desktop.py')
desktop+='''
def refresh_shell_icon(root,data,version):
    """Best effort per-version Explorer refresh; never change unrelated shortcuts."""
    if not supported():return
    import base64, ctypes, shutil
    target=Path(sys.executable).resolve()
    icon_dir=data/'icons'; icon_dir.mkdir(parents=True,exist_ok=True)
    icon=icon_dir/('LumePro-'+version+'.ico')
    stamp=icon_dir/('shell-'+version+'.json')
    try:
        if json.loads(stamp.read_text('utf-8')).get('target')==str(target) and icon.is_file():return
    except (OSError,ValueError,AttributeError):pass
    shutil.copyfile(root/'lume-app-icon.ico',icon)
    shell=ctypes.windll.shell32
    shell.SHChangeNotify.argtypes=(ctypes.c_long,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p)
    def notify(path):
        buf=ctypes.create_unicode_buffer(str(path))
        shell.SHChangeNotify(0x2000,5,ctypes.cast(buf,ctypes.c_void_p),None)
    # Use a unique versioned icon file to avoid an old icon path in Explorer cache.
    cfg=base64.b64encode(json.dumps({'target':str(target),'icon':str(icon)}).encode('utf-8')).decode('ascii')
    script=r"""
$ErrorActionPreference='Stop'
$c=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__CONFIG__')) | ConvertFrom-Json
$w=New-Object -ComObject WScript.Shell
$desktop=[Environment]::GetFolderPath('DesktopDirectory')
if ($desktop -and [IO.Directory]::Exists($desktop)) {
    foreach ($file in @(Get-ChildItem -LiteralPath $desktop -Filter '*.lnk' -File -ErrorAction SilentlyContinue)) {
        try {
            $link=$w.CreateShortcut($file.FullName)
            if ($link.TargetPath -and [IO.Path]::GetFullPath($link.TargetPath) -eq [IO.Path]::GetFullPath($c.target)) {
                $link.IconLocation=$c.icon+',0'
                $link.Save()
                [Console]::WriteLine($file.FullName)
            }
        } catch { [Console]::Error.WriteLine($_.Exception.Message) }
    }
}
""".replace('__CONFIG__',cfg)
    from frozen_update import external_environment
    ps=Path(os.environ.get('SystemRoot',r'C:\\Windows'))/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe'
    result=subprocess.run([str(ps),'-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode('ascii')],env=external_environment(),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdin=subprocess.DEVNULL,capture_output=True,timeout=20)
    notify(target)
    # Clear Explorer's stale image list once per installed version/path.
    shell.SHChangeNotify(0x08000000,0,None,None)
    if result.returncode==0:
        stamp.write_text(json.dumps({'target':str(target)}),encoding='utf-8')
'''
put('app/desktop.py',desktop)
server=get('app/server.py')
server=replace(server," if instance:instance.announce(port)\n stop=threading.Event()",""" if instance:instance.announce(port)
 if desktop.supported() and not args.no_browser:
  def refresh_icon():
   try:desktop.refresh_shell_icon(ROOT,DATA,updater.version)
   except Exception:pass
  threading.Thread(target=refresh_icon,daemon=True).start()
 stop=threading.Event()""")
put('app/server.py',server)
meta=json.loads(get('app/version.json'));meta['version']='0.3.53'
put('app/version.json',json.dumps(meta)+'\n')
put('tests/test_v0320_channel.py',get('tests/test_v0320_channel.py').replace("'version':'0.3.52'","'version':'0.3.53'"))
# Browser regressions actually interact with the new dialog, rather than overriding confirm().
test=get('tests/ui_native_menu.py')
test=replace(test,"window.confirm=()=>true","window.confirm=()=>{throw Error()}")
test=replace(test,"await page.locator('#quitBtn').click();await page.wait_for_timeout(250)","""await page.locator('#quitBtn').click()
  await page.locator('#appConfirmDialog').wait_for(state='visible')
  await page.locator('#appConfirmCancel').click()
  assert not await page.evaluate('quitCalls.includes("/api/shutdown")')
  await page.locator('#quitBtn').click()
  await page.locator('#appConfirmAccept').click();await page.wait_for_timeout(250)""")
put('tests/ui_native_menu.py',test)
put('tests/ui_update.py',get('tests/ui_update.py').replace('新しいバージョンがあります','更新来てるよん'))
# Existing browser scripts that intentionally exercise successful confirmation need
# to click the in-app dialog rather than overriding the browser's global confirm.
for name in ('ui_game_mode.py','ui_workspace.py','ui_smoke.py'):
    t=get('tests/'+name)
    if 'window.confirm=()=>true;' in t:
        t=t.replace('window.confirm=()=>true;',"window.confirm=()=>{throw Error('Unexpected browser dialog')};new MutationObserver(()=>{const d=document.getElementById('appConfirmDialog');if(d?.open)document.getElementById('appConfirmAccept').click()}).observe(document.documentElement,{attributes:true,subtree:true,attributeFilter:['open']});")
        put('tests/'+name,t)
preset=get('tests/ui_preset_menu.py').replace('window.confirm=()=>true;',"window.confirm=()=>{throw Error('Unexpected browser dialog')};")
preset=replace(preset,"await page.locator('[data-preset-action=delete]').click();await page.wait_for_function", "await page.locator('[data-preset-action=delete]').click();await page.locator('#appConfirmAccept').click();await page.wait_for_function")
put('tests/ui_preset_menu.py',preset)

smoke=get('tools/smoke_exe.py')
smoke=replace(smoke,"proc=subprocess.Popen([str(target),'--no-browser','--port',str(port)],env=env)","proc=subprocess.Popen([str(target),'--port',str(port)],env=env)")
smoke=replace(smoke,"        (stage/'sha256.txt').write_text(digest,'ascii')","""        wait_for(lambda:get(port,'/api/native_ready',token)['ready'],90)
        ui_marker=data/f'native-ui-{port}.json'
        wait_for(lambda:json.loads(ui_marker.read_text('utf-8'))['hwnd'],90)
        (stage/'sha256.txt').write_text(digest,'ascii')""")
smoke=replace(smoke,"        assert get(port,'/api/shutdown',token,{})['ok'];assert proc.wait(timeout=45)==0","""        # The updater must have its own visible progress window before acknowledging.
        import ctypes
        from ctypes import wintypes
        def helper_window():
            result=[]
            user=ctypes.windll.user32
            cb=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
            @cb
            def visit(hwnd,_):
                pid=wintypes.DWORD()
                user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                if pid.value==ps.pid and user.IsWindowVisible(hwnd):
                    title=ctypes.create_unicode_buffer(256)
                    user.GetWindowTextW(hwnd,title,256)
                    if title.value=='LUME / PRO':result.append(hwnd)
                return True
            user.EnumWindows(visit,0)
            return bool(result)
        assert wait_for(helper_window,10), 'Missing visible update handoff window'
        print('Visible update handoff before old app exits passed',flush=True)
        assert get(port,'/api/shutdown',token,{})['ok'];assert proc.wait(timeout=45)==0""")
smoke=replace(smoke,"        new_token=get(port,'/api/token')['token'];assert new_token!=token\n        assert get(port,'/api/preferences',new_token)['preferences']['auto'] is False\n        assert get(port,'/api/shutdown',new_token,{})['ok']\n        wait_for(lambda:not (data/'desktop_session.json').exists(),30)","""        new_token=get(port,'/api/token')['token'];assert new_token!=token
        assert get(port,'/api/preferences',new_token)['preferences']['auto'] is False
        wait_for(lambda:get(port,'/api/native_ready',new_token)['ready'],90)
        wait_for(lambda:json.loads(ui_marker.read_text('utf-8'))['hwnd'],90)
        wait_for(lambda:(data/'icons'/('shell-'+version+'.json')).is_file(),30)
        assert (data/'icons'/('LumePro-'+version+'.ico')).read_bytes()==(root/'app/lume-app-icon.ico').read_bytes()
        print('Updated native window and desktop icon refresh passed',flush=True)
        assert get(port,'/api/shutdown',new_token,{})['ok']
        wait_for(lambda:not (data/'desktop_session.json').exists(),30)""")
# WebView2 may release profile files asynchronously after the window exits.
# Use the existing strict cleanup retry for both native test profiles.
first=smoke.index('@contextmanager\ndef released_profile():')
last=smoke.index("with released_profile() as temp:",first)
cleanup=smoke[first:last].replace("def released_profile():","def released_profile(prefix='lume-native-'):").replace("prefix='lume-native-'","prefix=prefix",1)
# Keep the default argument intact, change only mkdtemp's argument.
cleanup=smoke[first:last].replace("def released_profile():","def released_profile(prefix='lume-native-'):").replace("tempfile.mkdtemp(prefix='lume-native-')","tempfile.mkdtemp(prefix=prefix)")
smoke=smoke[:first]+smoke[last:]
smoke=replace(smoke,"with tempfile.TemporaryDirectory(prefix='lume-swap-') as temp:",cleanup+"with released_profile(prefix='lume-swap-') as temp:")
put('tools/smoke_exe.py',smoke)

put('RELEASE_NOTES_JA.md',"""## v0.3.53
- 確認ダイアログをLUME専用デザインに統一しました。
- 更新の通知を「更新来てるよん」に変更しました。
- ダウンロード後の適用・再起動ステージを見える化し、Windows更新中の進捗ウィンドウを追加しました。
- デスクトップのEXEアイコンとLUMEを指すショートカットのアイコンキャッシュを更新します。
- 配布ビルドで依存関係のキャッシュと自動ソース生成を利用します。
""")
put('CHANGELOG.md',get('RELEASE_NOTES_JA.md')+'\n'+get('CHANGELOG.md'))
with zipfile.ZipFile(TARGET,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name,data in sorted(files.items()):
        entry=zipfile.ZipInfo(name,date_time=(2026,11,25,0,0,0))
        entry.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(entry,data)
digest=hashlib.sha256(TARGET.read_bytes()).hexdigest()
(ROOT/'publish.json').write_text(json.dumps({'version':'0.3.53','sha256':digest})+'\n',encoding='utf-8')
print(TARGET,digest)
