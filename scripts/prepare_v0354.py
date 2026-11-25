"""Generate Lume v0.3.54 from the existing verified v0.3.53 generator output."""
import hashlib,json,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'publish.json').read_text('utf-8'))
base=root/'packages/LumePro-0.3.53.zip'
assert manifest['version']=='0.3.53' and hashlib.sha256(base.read_bytes()).hexdigest()==manifest['sha256']
with zipfile.ZipFile(base) as z:
 files={i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}
def edit(path,pairs):
 key='LumePro/'+path
 s=files[key].decode('utf-8')
 for a,b in pairs:
  assert s.count(a)==1,(path,a[:80],s.count(a));s=s.replace(a,b)
 files[key]=s.encode('utf-8')
edit('app/engine.py',[
 ('def render(scene,pulses,t,volume=0.):','def render(scene,pulses,t,volume=0.,*,float_output=False):'),
 ('  out[code]=encode(composite)','  out[code]=composite if float_output else encode(composite)'),
 ('MOTION_PROFILES={"responsive":(.006,.018),"balanced":(.014,.045),"smooth":(.034,.085)}','MOTION_PROFILES={"responsive":(.009,.028),"balanced":(.026,.070),"smooth":(.045,.115)}\nRENDER_PERIOD=1/60\ndef target_rgb(value):return color(value) if isinstance(value,str) else value'),
 ('def filter_frame(frame,memory,dt,profile="balanced"):', 'def filter_frame(frame,memory,dt,profile="balanced",output_period=0.):'),
 (' dt=clamp(dt,0,.25);up=-math.expm1(-dt/attack);down=-math.expm1(-dt/release)',' # Match the low-pass envelope to actual transmission capacity, not UI FPS.\n if profile!="responsive":\n  period=clamp(output_period,0,.12);attack=max(attack,period*.55);release=max(release,period*1.10)\n dt=clamp(dt,0,.25);up=-math.expm1(-dt/attack);down=-math.expm1(-dt/release)'),
 ('  target=color(hx);prev=memory.get(code,target)','  target=target_rgb(hx);prev=memory.get(code,target)'),
 ('  current=tuple(w if abs(v-w)<.65 else v for v,w in zip(current,target))','  current=tuple(w if abs(v-w)<.25 else v for v,w in zip(current,target))'),
 ('def crossfade_frame(source,target,progress):\n weight=smooth(progress)\n return {key:encode(mix(color(source.get(key,\'#000000\')),color(value),weight)) for key,value in target.items()}', 'def crossfade_frame(source,target,progress,*,float_output=False):\n weight=smooth(progress)\n result={key:mix(target_rgb(source.get(key,\'#000000\')),target_rgb(value),weight) for key,value in target.items()}\n return result if float_output else {key:encode(value) for key,value in result.items()}'),
 ('if self.scene is None or self.scene[0]!=scene[0]:self.pulses.clear();self.filtered.clear();self.transition=None','if self.scene is None or self.scene[0]!=scene[0]:self.pulses.clear();self.filtered.clear();self.transition=None;self.last_frame=None;self.raw_frame=None'),
 ("else 'balanced';self.last_frame=None\n  self.wake.set()", "else 'balanced'\n  self.wake.set()"),
 (' def _loop(self):\n  while self.alive:', ' def _loop(self):\n  deadline=0.\n  while self.alive:'),
 ('self.audio.status() if has_audio else 0.)','self.audio.status() if has_audio else 0.,float_output=True)'),
 ('else:frame=crossfade_frame(source,frame,progress)','else:frame=crossfade_frame(source,frame,progress,float_output=True)'),
 ('''       if self.transition or self.unmasked_frame!=frame or any(self.filtered.get(k)!=color(v) for k,v in frame.items()):
        frame=filter_frame(frame,self.filtered,dt,"responsive" if has_audio else self.motion_profile)
       self.unmasked_frame=frame''','''       # Keep sub-byte precision until the final output. Do not temporally dither LEDs.
       profile=self.motion_profile
       if has_audio and profile=='balanced':profile='responsive'
       if not animated and not self.transition and profile=='balanced':profile='smooth'
       period=getattr(self.backend,'output_period',0.)
       if not isinstance(period,(int,float)):period=0.
       if self.transition or any(self.filtered.get(k)!=target_rgb(v) for k,v in frame.items()):
        frame=filter_frame(frame,self.filtered,dt,profile,period)
       else:frame={k:encode(target_rgb(v)) for k,v in frame.items()}
       self.unmasked_frame=frame'''),
 ('''   period=1/60 if self.active else .5
   self.wake.wait(max(.001,period-(time.monotonic()-start)));self.wake.clear()''','''   if self.active:
    # Absolute cadence avoids accumulating scheduler jitter. Windows 3.12 sleep
    # uses a high-resolution timer; Event.wait can have a coarser timeout.
    deadline=deadline+RENDER_PERIOD if deadline else start+RENDER_PERIOD
    now=time.monotonic()
    if deadline<=now:deadline+=RENDER_PERIOD*(int((now-deadline)/RENDER_PERIOD)+1)
    time.sleep(max(0.,deadline-time.monotonic()))
   else:
    deadline=0.;self.wake.wait(.5)
   self.wake.clear()''')])
edit('app/app.js',[
 ('const MOTION_PROFILES={responsive:[.006,.018],balanced:[.014,.045],smooth:[.034,.085]};','const MOTION_PROFILES={responsive:[.009,.028],balanced:[.026,.070],smooth:[.045,.115]};'),
 ('Math.abs(n-target[i])<.65','Math.abs(n-target[i])<.25'),
 ("state.layers.some(l=>l.enabled&&AUDIO.has(l.type)&&(soloLayerId==null||soloLayerId===l.id))?'responsive':motionProfile", "motionProfile==='balanced'&&state.layers.some(l=>l.enabled&&AUDIO.has(l.type)&&(soloLayerId==null||soloLayerId===l.id))?'responsive':motionProfile")])
edit('app/logitech.py',[
 ('return max(1/60,min(.25,max(0.,latency_ms)*.001*1.5))','return max(1/60,min(.25,max(0.,latency_ms)*.001*1.20))'),
 ('self.frame_interval_ms=0.;self.retry_after={}','self.frame_interval_ms=0.;self.send_intervals=[];self.retry_after={}'),
 ('self.cache.clear();self.retry_after.clear();self.last_result.clear();self.bitmap_cache=None\n  if self.sdk:', 'self.cache.clear();self.retry_after.clear();self.last_result.clear();self.bitmap_cache=None\n  self.last_frame_at=0.;self.latency_ms=0.;self.frame_interval_ms=0.;self.send_intervals.clear()\n  if self.sdk:'),
 (' def _worker(self):',' @property\n def output_period(self):return frame_period(self.latency_ms)\n def _worker(self):'),
 ('   delay=frame_period(self.latency_ms)-(time.monotonic()-self.last_frame_at)','   if not self.event.is_set():continue\n   delay=self.output_period-(time.monotonic()-self.last_frame_at)'),
 ('     if self.last_frame_at:self.frame_interval_ms=(started-self.last_frame_at)*1000','''     if self.last_frame_at:
      interval=(started-self.last_frame_at)*1000
      if interval<500:
       self.send_intervals=(self.send_intervals+[interval])[-60:]
       self.frame_interval_ms=sum(self.send_intervals)/len(self.send_intervals)
      else:self.send_intervals.clear();self.frame_interval_ms=0.'''),
 ('self.latency_ms=max(measured,self.latency_ms*.82+measured*.18)','self.latency_ms=max(measured,self.latency_ms*.90+measured*.10)'),
 ("'send_ms':round(self.latency_ms,2),", "'send_ms':round(self.latency_ms,2),'send_target_fps':round(1/self.output_period,1),'send_jitter_ms':round(max(self.send_intervals)-min(self.send_intervals),2) if len(self.send_intervals)>1 else 0.,'color_steps':256 if self.output_mode=='bitmap' else 101,")])
edit('app/hardware.py', [(' def _worker(self):',' @property\n def output_period(self):return .055\n def _worker(self):')])
edit('tests/test_v0329_motion.py', [('frame_period(20)==pytest.approx(.03)','frame_period(20)==pytest.approx(.024)'),('frame_period(70)==pytest.approx(.105)','frame_period(70)==pytest.approx(.084)')])
edit('tests/test_v0320_channel.py',[("'version':'0.3.53'","'version':'0.3.54'")])
meta=json.loads(files['LumePro/app/version.json']);meta['version']='0.3.54'
files['LumePro/app/version.json']=(json.dumps(meta)+'\n').encode()
files['LumePro/tests/test_v0354_led_smooth.py']=b'''import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from engine import render, validate, filter_frame, crossfade_frame
from logitech import percent, frame_period

def test_fractional_light_survives_render_and_crossfade():
    scene=validate({'keys':[{'code':'KeyA','x':1,'y':1}], 'layers':[{'type':'static','color':'#ff0000','brightness':12.5}]})
    raw=render(scene,[],1,float_output=True)
    assert raw['KeyA']==(31.875,0.,0.)
    assert render(scene,[],1)['KeyA']=='#200000'
    mid=crossfade_frame({'KeyA':'#000000'},raw,.5,float_output=True)
    assert mid['KeyA']==(15.9375,0.,0.)

def test_brightness_fade_is_monotonic_and_settles_at_sdk_precision():
    m={'KeyA':(255.,0.,0.)};levels=[100]
    for _ in range(180):
        levels.append(percent(filter_frame({'KeyA':(0.,0.,0.)},m,1/60,'smooth')['KeyA'])[0])
    assert all(a>=b for a,b in zip(levels,levels[1:]))
    assert len(set(levels))>=20 and max(a-b for a,b in zip(levels,levels[1:]))<=14
    assert levels[-20:]==[0]*20
    m={'KeyA':(0.,0.,0.)}
    low=[percent(filter_frame({'KeyA':(4.5,0.,0.)},m,1/60,'smooth')['KeyA'])[0] for _ in range(180)]
    assert all(a<=b for a,b in zip(low,low[1:])) and len(set(low[-20:]))==1

def test_slow_transport_adapts_without_delaying_responsive_mode():
    target={'KeyA':(255.,0.,0.)}
    def step(profile,period):return percent(filter_frame(target,{'KeyA':(0.,0.,0.)},1/60,profile,period)['KeyA'])[0]
    assert step('balanced',.10)<step('balanced',1/60)
    assert step('responsive',.10)==step('responsive',1/60)
    assert frame_period(40)==.048
'''
notes="""## v0.3.54
- 実機ライティングの中間計算を小数精度のまま保持し、最終出力直前まで8ビットに丸めないよう変更。
- 明るさの変化を滑らかに補間し、静的な明るさ調整ではより緩やかなフェードを使用。
- 実際のSDK送信速度に合わせた補間、絶対時刻基準の60 FPS描画、送信待機の改善。
- 低輝度の時間ディザリングは使用しません。対応済みビットマップ出力のマッピングは維持し、未知のキー割り当ては行いません。
- 送信速度・間隔のばらつき・API色段階数の診断を追加。
- 物理LEDのPWM・ファームウェア・G HUBによる制約は実機での確認が必要です。
"""
files['LumePro/RELEASE_NOTES_JA.md']=notes.encode()
files['LumePro/CHANGELOG.md']=notes.encode()+b'\n'+files['LumePro/CHANGELOG.md']
target=root/'packages/LumePro-0.3.54.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,data in sorted(files.items()):
  entry=zipfile.ZipInfo(name,date_time=(2026,11,25,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
  z.writestr(entry,data)
digest=hashlib.sha256(target.read_bytes()).hexdigest()
(root/'publish.json').write_text(json.dumps({'version':'0.3.54','sha256':digest})+'\n',encoding='utf-8')
print(target,digest)
