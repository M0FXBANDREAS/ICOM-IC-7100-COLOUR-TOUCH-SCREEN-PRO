#!/usr/bin/env python3
"""Local IC-7100 receive control panel. No transmit commands implemented."""
import argparse
import json
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

TONES = [670,693,719,744,770,797,825,854,885,915,948,974,1000,1035,1072,1109,1148,1188,1230,1273,1318,1365,1413,1462,1514,1567,1598,1622,1655,1679,1713,1738,1773,1799,1835,1862,1899,1928,1966,1995,2035,2065,2107,2181,2257,2291,2336,2418,2503,2541]

MODES = {'LSB': 0, 'USB': 1, 'AM': 2, 'CW': 3, 'RTTY': 4, 'FM': 5, 'CW-R': 7, 'RTTY-R': 8, 'DV': 0x17}

# IC-7100 Advanced Instructions 20-3/20-4. Values are raw CI-V units.
SETTINGS = {
 'nr': {'label':'Noise reduction', 'cmd':0x16,'sub':0x40,'options':{'0':'Off','1':'On'}},
 'nb': {'label':'Noise blanker', 'cmd':0x16,'sub':0x22,'options':{'0':'Off','1':'On'}},
 'nr_level': {'label':'Noise reduction strength','cmd':0x14,'sub':0x06,'max':255},
 'nb_level': {'label':'Noise blanker level','cmd':0x14,'sub':0x12,'max':255},
 'preamp': {'label':'Preamplifier','cmd':0x16,'sub':0x02,'options':{'0':'Off','1':'Preamp 1 / VHF-UHF On','2':'Preamp 2'}},
 'attenuator': {'label':'Attenuator','cmd':0x11,'sub':None,'options':{'0':'Off','18':'12 dB'}},
 'agc': {'label':'AGC speed','cmd':0x16,'sub':0x12,'options':{'1':'Fast','2':'Mid','3':'Slow'}},
 'auto_notch': {'label':'Auto notch','cmd':0x16,'sub':0x41,'options':{'0':'Off','1':'On'}},
 'manual_notch': {'label':'Manual notch','cmd':0x16,'sub':0x48,'options':{'0':'Off','1':'On'}},
 'notch_width': {'label':'Manual notch width','cmd':0x16,'sub':0x57,'options':{'0':'Wide','1':'Mid','2':'Narrow'}},
 'notch_position': {'label':'Manual notch position','cmd':0x14,'sub':0x0D,'max':255},
 'filter_shape': {'label':'DSP filter shape','cmd':0x16,'sub':0x56,'options':{'0':'Sharp','1':'Soft'}},
 'af_level': {'label':'Radio AF volume','cmd':0x14,'sub':0x01,'max':255},
 'rf_gain': {'label':'RF gain','cmd':0x14,'sub':0x02,'max':255},
 'squelch': {'label':'Squelch','cmd':0x14,'sub':0x03,'max':255},
 'pbt_inner': {'label':'Twin PBT inner','cmd':0x14,'sub':0x07,'max':255},
 'pbt_outer': {'label':'Twin PBT outer','cmd':0x14,'sub':0x08,'max':255},
 'cw_pitch': {'label':'CW pitch (300–900 Hz)','cmd':0x14,'sub':0x09,'max':255},
 'dial_lock': {'label':'Radio dial lock','cmd':0x16,'sub':0x50,'options':{'0':'Off','1':'On'}},
 'twin_peak': {'label':'RTTY twin peak filter','cmd':0x16,'sub':0x4F,'options':{'0':'Off','1':'On'}},
 'tone_enabled': {'label':'CTCSS transmit tone','cmd':0x16,'sub':0x42,'options':{'0':'Off','1':'On'}},
 'tone_squelch': {'label':'CTCSS receive tone squelch','cmd':0x16,'sub':0x43,'options':{'0':'Off','1':'On'}},
 'vsc': {'label':'Voice squelch control','cmd':0x16,'sub':0x4C,'options':{'0':'Off','1':'On'}}
}

def encode_frequency(hz):
    hz = int(hz)
    if not (30000 <= hz <= 199999999 or 400000000 <= hz <= 470000000):
        raise ValueError('Frequency outside IC-7100 receive ranges')
    return bytes(int(f'{hz:010d}'[i:i+2], 16) for i in range(8, -1, -2))

def decode_frequency(data):
    if len(data) != 5 or any(b >> 4 > 9 or b & 15 > 9 for b in data):
        raise ValueError('Invalid frequency BCD')
    return int(''.join(f'{b:02x}' for b in reversed(data)))

class Radio:
    def __init__(self, args):
        self.lock = threading.RLock()
        self.state_lock = threading.Lock()
        self.stop = threading.Event()
        self.args = args
        self.setting_index = 0
        self.poll_index = 0
        self.sweep_stop = threading.Event()
        self.sweep_thread = None
        self.sweep_gate = threading.Lock()
        self.port = None
        self.address = args.address
        self.state = dict(frequency=None, mode='UNKNOWN', filter=None, connected=False, source='NO AUDIO INPUT', sample_id=0, bins=[], error='', audio_error='', audio_rms_db=None, audio_peak_db=None, audio_time=0, settings={k:None for k in SETTINGS}, setting_errors={}, meters={'s':None,'power':None,'swr':None}, meter_errors={}, tx=None, operation='UNKNOWN', memory_bank=None, memory_channel=None, duplex=None, offset_hz=None, tone_tenths=None, tsql_tenths=None, repeater_error='', sweep={'running':False,'points':[],'progress':0,'error':'','center':None,'step':1000,'span':60000})
        if args.port:
            try:
                import serial
                self.port = serial.Serial(args.port, args.baud, timeout=.08)
                self.refresh()
            except Exception as exc:
                self.state['error'] = str(exc)
        if not args.port: self.state['error']='CI-V device not uniquely detected. Select the CI-V serial port in the launcher or supply --port COM5 (Windows) / --port /dev/serial/by-id/YOUR_DEVICE (Linux).'
        if args.audio_device is not None:
            try:
                import numpy as np
                import sounddevice as sd
                device = args.audio_device
                if device == 'auto':
                    inputs = [(i, d) for i, d in enumerate(sd.query_devices()) if d['max_input_channels'] > 0]
                    matches = [(i,d) for i,d in inputs if any(x in d['name'].lower() for x in ('icom', 'ic-7100', 'usb audio codec', 'usb audio'))]
                    if len(matches) != 1:
                        raise ValueError('Select the Icom input using --audio-device INDEX; automatic matching was ambiguous or unavailable.')
                    device = matches[0][0]
                else:
                    device = int(device)
                def callback(data, frames, timing, status):
                    spectrum = np.abs(np.fft.rfft(data[:, 0] * np.hanning(frames))) / (frames / 2)
                    db = 20 * np.log10(np.maximum(spectrum, 1e-8))
                    selected = db[:int(3000 * frames / 48000) + 1]
                    with self.state_lock:
                        self.state['bins'] = np.interp(np.linspace(0, len(selected)-1, 512), np.arange(len(selected)), selected).tolist()
                        self.state['audio_time'] = time.monotonic()
                        self.state['audio_rms_db'] = float(20*np.log10(max(float(np.sqrt(np.mean(data[:,0]**2))),1e-8)))
                        self.state['audio_peak_db'] = float(20*np.log10(max(float(np.max(np.abs(data[:,0]))),1e-8)))
                        self.state['sample_id'] += 1
                        self.state['source'] = 'LIVE AF · 0–3 kHz'
                        self.state['audio_error'] = str(status) if status else ''
                self.stream = sd.InputStream(device=device, channels=1, samplerate=48000, blocksize=4096, callback=callback)
                self.stream.start()
            except Exception as exc:
                self.state['audio_error'] = str(exc)

    def snapshot(self, spectrum=False):
        with self.state_lock:
            if spectrum:
                return {key: self.state[key] for key in ('bins', 'sample_id', 'source', 'audio_error', 'audio_rms_db', 'audio_peak_db', 'audio_time')}
            return json.loads(json.dumps({key:value for key,value in self.state.items() if key != 'bins'}))

    def poll(self):
        while not self.stop.is_set():
            with self.state_lock:
                sweeping = self.state['sweep']['running']
            if self.port and not sweeping:
                self.refresh()
                if self.state['connected']:
                    self.read_meters()
                    self.poll_index += 1
                    if self.poll_index % 3 == 0:
                        names=list(SETTINGS)
                        self.read_setting(names[self.setting_index % len(names)])
                        self.setting_index += 1
                    if self.poll_index % 10 == 0:
                        self.read_repeater()
            self.stop.wait(.25)

    def reconnect(self):
        if self.state['sweep']['running']:
            raise ValueError('Stop RF sweep before reconnecting USB')
        with self.lock:
            if self.port:
                try: self.port.close()
                except Exception: pass
            self.port = None
            try:
                import serial
                self.port = serial.Serial(self.args.port, self.args.baud, timeout=.08)
            except Exception as exc:
                with self.state_lock:
                    self.state.update(connected=False, frequency=None, mode='UNKNOWN', filter=None, error=str(exc))
                return
            self.refresh()

    def read_setting(self, key):
        spec = SETTINGS[key]
        prefix = b'' if spec['sub'] is None else bytes([spec['sub']])
        try:
            with self.lock:
                reply = self.exchange(spec['cmd'], prefix, response_command=spec['cmd'])
            if not reply.startswith(prefix):
                raise ValueError('Unexpected setting response')
            data = reply[len(prefix):]
            if 'max' in spec:
                if len(data) != 2 or any((b >> 4)>9 or (b & 15)>9 for b in data):
                    raise ValueError('Invalid BCD level')
                value = int(''.join(f'{b:02x}' for b in data))
                if not 0 <= value <= spec['max']: raise ValueError('Level outside range')
            else:
                if len(data)!=1 or str(data[0]) not in spec['options']:
                    raise ValueError('Unsupported setting response')
                value = data[0]
            with self.state_lock:
                self.state['settings'][key] = value
                self.state['setting_errors'].pop(key, None)
        except Exception as exc:
            with self.state_lock:
                self.state['settings'][key] = None
                self.state['setting_errors'][key] = str(exc)

    def write_setting(self, key, value):
        spec = SETTINGS[key]
        if type(value) is not int:
            raise ValueError('Setting value must be integer')
        if 'max' in spec:
            if not 0 <= value <= spec['max']: raise ValueError('Level outside range')
            data = bytes.fromhex(f'{value:04d}')
        else:
            if str(value) not in spec['options']: raise ValueError('Unsupported setting option')
            data = bytes([value])
        prefix = b'' if spec['sub'] is None else bytes([spec['sub']])
        self.exchange(spec['cmd'], prefix + data)

    def exchange(self, command, payload=b'', response_command=None):
        self.port.reset_input_buffer()
        self.port.write(bytes([0xfe, 0xfe, self.address, 0xe0, command]) + payload + b'\xfd')
        deadline = time.monotonic() + 1.2
        buffer = bytearray()
        while time.monotonic() < deadline:
            buffer.extend(self.port.read(max(1, min(128, self.port.in_waiting))))
            while 0xfd in buffer:
                end = buffer.index(0xfd)
                frame = bytes(buffer[:end+1]); del buffer[:end+1]
                start = frame.find(b'\xfe\xfe')
                frame = frame[start:] if start >= 0 else b''
                if len(frame) < 6 or frame[2:4] != bytes([0xe0, self.address]):
                    continue
                if frame[4] == 0xfa:
                    raise ValueError('Radio rejected command')
                if frame[4] == (response_command if response_command is not None else 0xfb):
                    return frame[5:-1]
        raise TimeoutError('No CI-V reply. Check port, baud, address and radio power.')

    @staticmethod
    def bcd_value(data):
        if not data or any((b >> 4)>9 or (b & 15)>9 for b in data):
            raise ValueError('Invalid BCD reply')
        return int(''.join(f'{b:02x}' for b in data))

    def tx_status(self):
        reply = self.exchange(0x1c, b'\x00', response_command=0x1c)
        if len(reply)!=2 or reply[0]!=0 or reply[1] not in (0,1):
            raise ValueError('Invalid RX/TX status')
        return bool(reply[1])

    def meter_raw(self, sub):
        reply = self.exchange(0x15, bytes([sub]), response_command=0x15)
        if len(reply)!=3 or reply[0]!=sub:
            raise ValueError('Invalid meter response')
        value = self.bcd_value(reply[1:])
        if value>255: raise ValueError('Meter outside range')
        return value

    def read_meters(self):
        values={'s':None,'power':None,'swr':None}; errors={};tx=None
        with self.lock:
            try: tx=self.tx_status()
            except Exception as exc: errors['status']=str(exc)
            for key,sub in [('s',2),('power',0x11),('swr',0x12)]:
                if key in ('power','swr') and tx is not True: continue
                try: values[key]=self.meter_raw(sub)
                except Exception as exc: errors[key]=str(exc)
        with self.state_lock:
            self.state.update(meters=values,meter_errors=errors,tx=tx)

    def read_repeater(self):
        try:
            with self.lock:
                duplex=self.exchange(0x0f, response_command=0x0f)
                if len(duplex)!=1 or duplex[0] not in (0,1,0x10,0x11,0x12):
                    raise ValueError('Invalid duplex reply')
                offset=self.exchange(0x0c,response_command=0x0c)
                if len(offset)!=3: raise ValueError('Invalid offset reply')
                offset_hz=self.bcd_value(offset[::-1])*100
                tones=[]
                for sub in (0,1):
                    data=self.exchange(0x1b,bytes([sub]),response_command=0x1b)
                    if not data.startswith(bytes([sub])): raise ValueError('Invalid tone reply')
                    body=data[1:]
                    # Read format includes an extra fixed 00 before the 2-byte tone.
                    if len(body) not in (2,3): raise ValueError('Invalid tone length')
                    tones.append(self.bcd_value(body[-2:]))
            with self.state_lock:
                self.state.update(duplex=duplex[0],offset_hz=offset_hz,tone_tenths=tones[0],tsql_tenths=tones[1],repeater_error='')
        except Exception as exc:
            with self.state_lock: self.state['repeater_error']=str(exc)

    def memory_preview(self, bank, channel):
        if bank not in range(1,6) or channel not in range(1,100):
            raise ValueError('Select bank A–E and channel 1–99')
        prefix=bytes([0,bank])+bytes.fromhex(f'{channel:04d}')
        with self.lock:
            if self.state['sweep']['running']: raise ValueError('Stop sweep before browsing memories')
            reply=self.exchange(0x1a,prefix,response_command=0x1a)
        if not reply.startswith(prefix): raise ValueError('Unexpected memory reply')
        data=reply[len(prefix):]
        if len(data)<8 or data[:1]==b'\xff':
            return {'bank':bank,'channel':channel,'empty':True}
        frequency=decode_frequency(data[1:6])
        mode=next((name for name,code in MODES.items() if code==data[6]),'UNKNOWN')
        name=''
        if len(data)>=24:
            tail=data[-16:]
            if all(32<=b<127 for b in tail): name=tail.decode('ascii').strip()
        return {'bank':bank,'channel':channel,'frequency':frequency,'mode':mode,'filter':data[7], 'name':name,'empty':False}

    def start_sweep(self, step):
        if type(step) is not int or step not in (100,500,1000,5000,10000):
            raise ValueError('Invalid RF sweep step')
        with self.sweep_gate:
            if self.sweep_thread and self.sweep_thread.is_alive():
                raise ValueError('Sweep already active or restoring the centre')
            with self.lock:
                if not self.port: raise ValueError('Radio disconnected')
                if self.tx_status(): raise ValueError('RF sweep requires receive mode')
                self.exchange(7)  # Sweeping always uses VFO; stored memories are not written.
                center=decode_frequency(self.exchange(3,response_command=3))
                for i in (-30,30): encode_frequency(center+i*step)
                with self.state_lock:
                    self.state.update(operation='VFO',memory_bank=None,memory_channel=None)
                    self.state['sweep']={'running':True,'points':[], 'progress':0,'error':'','center':center,'step':step,'span':60*step}
            self.sweep_stop.clear()
            self.sweep_thread=threading.Thread(target=self.run_sweep,args=(center,step),daemon=True)
            self.sweep_thread.start()

    def run_sweep(self, center, step):
        error='';points=[]
        try:
            for i in range(-30,31):
                if self.stop.is_set() or self.sweep_stop.is_set(): break
                frequency=center+i*step
                with self.lock:
                    transmitting=self.tx_status()
                    with self.state_lock: self.state['tx']=transmitting
                    if transmitting: raise ValueError('TX detected; RF sweep stopped')
                    self.exchange(5,encode_frequency(frequency))
                    self.sweep_stop.wait(.12)
                    if self.stop.is_set() or self.sweep_stop.is_set(): break
                    transmitting=self.tx_status()
                    with self.state_lock: self.state['tx']=transmitting
                    if transmitting: raise ValueError('TX detected; RF sweep stopped')
                    raw=self.meter_raw(2)
                points.append({'frequency':frequency,'raw':raw})
                with self.state_lock:
                    self.state['sweep'].update(points=list(points),progress=len(points))
        except Exception as exc: error=str(exc)
        finally:
            # Keep controls blocked until centre restoration finishes; never retune during TX.
            restored=False
            while not restored:
                try:
                    with self.lock:
                        if not self.tx_status():
                            self.exchange(5,encode_frequency(center));restored=True
                    if not restored and self.stop.is_set():
                        error=(error+' · ' if error else '')+'Centre restoration deferred: radio transmitting during shutdown'
                        break
                    if not restored:
                        with self.state_lock: self.state['sweep']['error']='Waiting for RX to restore sweep centre'
                        self.stop.wait(.5)
                except Exception as exc:
                    error=(error+' · ' if error else '')+'Centre restore failed: '+str(exc)
                    break
            with self.state_lock: self.state['sweep'].update(running=False,error=error,points=list(points))
            if restored: self.refresh()

    def refresh(self):
        with self.lock:
            try:
                frequency = decode_frequency(self.exchange(3, response_command=3))
                mode = self.exchange(4, response_command=4)
                current_mode = next((k for k,v in MODES.items() if mode and v == mode[0]), 'UNKNOWN')
                current_filter = mode[1] if len(mode) > 1 and mode[1] in (1, 2, 3) else None
                with self.state_lock:
                    self.state.update(frequency=frequency, mode=current_mode, filter=current_filter, connected=True, error='')
            except Exception as exc:
                with self.state_lock:
                    self.state.update(connected=False, error=str(exc))

    def set(self, changes):
        allowed = {'frequency', 'mode', 'filter', 'tune_steps', 'step_hz','operation','memory_bank','memory_channel','duplex','offset_hz','tone_tenths','tsql_tenths'} | set(SETTINGS)
        if set(changes) - allowed or not changes:
            raise ValueError('Unsupported receive control')
        if self.state['sweep']['running']:
            raise ValueError('Stop RF sweep and wait for centre restoration before changing radio controls')
        if 'operation' in changes and changes['operation'] not in ('VFO','VFOA','VFOB','MEMORY'):
            raise ValueError('Unsupported VFO/memory selection')
        if ('memory_bank' in changes) != ('memory_channel' in changes):
            raise ValueError('Memory recall requires bank and channel')
        if 'memory_bank' in changes and (type(changes['memory_bank']) is not int or changes['memory_bank'] not in range(1,6) or type(changes['memory_channel']) is not int or changes['memory_channel'] not in range(1,100)):
            raise ValueError('Memory bank A–E and channel 1–99 required')
        if 'duplex' in changes and changes['duplex'] not in ('OFF','-','+'):
            raise ValueError('Invalid duplex direction')
        if 'offset_hz' in changes and (type(changes['offset_hz']) is not int or not 0<=changes['offset_hz']<=99999900 or changes['offset_hz']%100):
            raise ValueError('Offset must be 0–99.9999 MHz in 100 Hz steps')
        for name in ('tone_tenths','tsql_tenths'):
            if name in changes and changes[name] not in TONES: raise ValueError('Unsupported CTCSS tone')
        if 'frequency' in changes:
            encoded = encode_frequency(changes['frequency'])
        if 'mode' in changes and changes['mode'] not in MODES:
            raise ValueError('Unsupported mode')
        if 'filter' in changes and (type(changes['filter']) is not int or changes['filter'] not in (1,2,3)):
            raise ValueError('Filter must be FIL1, FIL2 or FIL3')
        relative = 'tune_steps' in changes or 'step_hz' in changes
        if relative:
            if set(changes) != {'tune_steps','step_hz'}:
                raise ValueError('Relative tuning requires only tune_steps and step_hz')
            if type(changes['tune_steps']) is not int or abs(changes['tune_steps']) > 1000:
                raise ValueError('Invalid tuning movement')
            if changes['step_hz'] not in (1,10,100,1000,10000,25000):
                raise ValueError('Invalid tuning step')
        with self.lock:
            if not self.port:
                raise ValueError('IC-7100 USB connection unavailable')
            operation=changes.get('operation')
            if operation in ('VFO','VFOA','VFOB'):
                self.exchange(7)
                if operation!='VFO': self.exchange(7,bytes([0 if operation=='VFOA' else 1]))
                with self.state_lock: self.state.update(operation=operation,memory_bank=None,memory_channel=None)
            elif operation=='MEMORY':
                self.exchange(8)
                with self.state_lock: self.state['operation']='MEMORY'
            if 'memory_channel' in changes:
                preview=self.memory_preview(changes['memory_bank'],changes['memory_channel'])
                if preview['empty']: raise ValueError('This memory channel is empty')
                self.exchange(8)
                self.exchange(8,bytes([0xa0,changes['memory_bank']]))
                self.exchange(8,bytes.fromhex(f"{changes['memory_channel']:04d}"))
                with self.state_lock: self.state.update(operation='MEMORY',memory_bank=changes['memory_bank'],memory_channel=changes['memory_channel'])
            if 'duplex' in changes: self.exchange(0x0f,bytes([{'OFF':0x10,'-':0x11,'+':0x12}[changes['duplex']]]))
            if 'offset_hz' in changes:
                self.exchange(0x0d,bytes.fromhex(f"{changes['offset_hz']//100:06d}")[::-1])
            for name,sub in [('tone_tenths',0),('tsql_tenths',1)]:
                if name in changes: self.exchange(0x1b,bytes([sub])+bytes.fromhex(f"{changes[name]:04d}"))
            for key in changes:
                if key in SETTINGS:
                    self.write_setting(key, changes[key])
            if relative:
                current = decode_frequency(self.exchange(3, response_command=3))
                self.exchange(5, encode_frequency(current + changes['tune_steps'] * changes['step_hz']))
            if 'frequency' in changes:
                self.exchange(5, encoded)
            if 'mode' in changes or 'filter' in changes:
                # Query mode first so a filter-only change preserves the radio mode.
                current_mode = self.exchange(4, response_command=4)
                if not current_mode:
                    raise ValueError('Missing radio mode response')
                mode_code = MODES[changes['mode']] if 'mode' in changes else current_mode[0]
                payload = bytes([mode_code])
                if 'filter' in changes:
                    payload += bytes([changes['filter']])
                self.exchange(6, payload)
        self.refresh()
        for key in changes:
            if key in SETTINGS: self.read_setting(key)
        if set(changes)&{'duplex','offset_hz','tone_tenths','tsql_tenths'}: self.read_repeater()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent / 'web'), **kwargs)
    def respond(self, status, value):
        data = json.dumps(value).encode()
        self.send_response(status); self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(data)))
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        parsed=urlsplit(self.path)
        route = parsed.path
        if route == '/api/memory':
            try:
                query=parse_qs(parsed.query)
                return self.respond(200,self.server.radio.memory_preview(int(query.get('bank',['1'])[0]),int(query.get('channel',['1'])[0])))
            except Exception as exc: return self.respond(400,{'error':str(exc)})
        if route == '/api/settings':
            return self.respond(200, {'settings':SETTINGS, 'serial_port':self.server.radio.args.port, 'baud':self.server.radio.args.baud, 'address':f'{self.server.radio.args.address:02X}', 'audio_device':self.server.radio.args.audio_device, 'tones':TONES})
        if route == '/api/state':
            return self.respond(200, self.server.radio.snapshot())
        if route == '/api/spectrum':
            return self.respond(200, self.server.radio.snapshot(spectrum=True))
        super().do_GET()
    def do_POST(self):
        if self.path not in ('/api/control', '/api/reconnect','/api/sweep'): return self.respond(404, {'error':'Not found'})
        # Local browser origin only; reject cross-site control requests.
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host',''):
            return self.respond(403, {'error':'Origin rejected'})
        if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            return self.respond(415, {'error':'JSON required'})
        try:
            length = int(self.headers.get('Content-Length',0))
            if not 0 < length < 1024: raise ValueError('Invalid request size')
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict): raise ValueError('Object required')
            if self.path == '/api/sweep':
                if value.get('action')=='start' and set(value)<={'action','step'}:
                    self.server.radio.start_sweep(value.get('step',1000))
                elif value=={'action':'stop'}:
                    self.server.radio.sweep_stop.set()
                else: raise ValueError('Invalid sweep request')
            elif self.path == '/api/reconnect':
                if value: raise ValueError('Reconnect expects an empty object')
                self.server.radio.reconnect()
            else:
                self.server.radio.set(value)
            return self.respond(200, self.server.radio.snapshot())
        except Exception as exc:
            return self.respond(400, {'error':str(exc)})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='auto', help='CI-V device, preferably /dev/serial/by-id/...')
    parser.add_argument('--baud', type=int, default=19200)
    parser.add_argument('--address', type=lambda s:int(s,16), default=0x88)
    parser.add_argument('--audio-device', default='auto', help='Icom audio input index or auto')
    parser.add_argument('--http-port', type=int, default=7100)
    args = parser.parse_args()
    if args.port=='auto':
        import os
        if os.name=='nt':
            from serial.tools import list_ports
            ports=list(list_ports.comports())
            matches=[p.device for p in ports if 'IC-7100' in ((p.description or '')+' '+(p.serial_number or '')) and (p.serial_number or '').endswith('_A')]
            args.port=matches[0] if len(matches)==1 else None
        candidates=sorted(Path('/dev/serial/by-id').glob('*IC-7100*_A-if00-port0'))
        if not candidates: candidates=sorted(Path('/dev/serial/by-id').glob('*IC-7100*'))
        if os.name!='nt': args.port=str(candidates[0]) if len(candidates)==1 else None
    server = ThreadingHTTPServer(('127.0.0.1', args.http_port), Handler)
    server.radio = Radio(args)
    polling = threading.Thread(target=server.radio.poll, daemon=True)
    polling.start()
    print(f'Open http://127.0.0.1:{args.http_port} — IC-7100 live USB control')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.radio.stop.set()
        if server.radio.sweep_thread: server.radio.sweep_thread.join(timeout=3)
        polling.join(timeout=3)
        server.server_close()
        if server.radio.port: server.radio.port.close()
        if hasattr(server.radio,'stream'): server.radio.stream.close()

if __name__ == '__main__': main()
