"""Windows connection chooser; does not probe the radio or key TX."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import webbrowser
from serial.tools import list_ports
import sounddevice as sd

ROOT=Path(__file__).resolve().parent
CONFIG=ROOT/'windows-settings.json'
URL='http://127.0.0.1:7100'
try: saved=json.loads(CONFIG.read_text())
except (OSError,ValueError): saved={}
app=tk.Tk()
app.title('HamTech M0FXB Modification — IC-7100')
app.geometry('740x480');app.minsize(640,440)
app.configure(bg='#10141b')
style=ttk.Style();style.theme_use('clam')
style.configure('TFrame',background='#10141b')
style.configure('TLabel',background='#10141b',foreground='#e1eaff',font=('Segoe UI',11))
style.configure('TButton',font=('Segoe UI',11),padding=8)
frame=ttk.Frame(app,padding=24);frame.pack(fill='both',expand=True)
ttk.Label(frame,text='HamTech M0FXB Modification',font=('Segoe UI',20,'bold')).pack(anchor='w')
ttk.Label(frame,text='IC-7100 • Windows 11 • IC-705 photo console').pack(anchor='w',pady=(4,18))
port_var=tk.StringVar();audio_var=tk.StringVar();baud_var=tk.StringVar(value=str(saved.get('baud',19200)))
address_var=tk.StringVar(value=saved.get('address','88'))
ports={};audio={}
def row(label,variable):
    ttk.Label(frame,text=label).pack(anchor='w')
    box=ttk.Combobox(frame,textvariable=variable,state='readonly');box.pack(fill='x',pady=(3,9));return box
port_box=row('Radio CI-V COM port (A interface)',port_var)
audio_box=row('Radio receive-audio input',audio_var)
options=ttk.Frame(frame);options.pack(fill='x',pady=5)
ttk.Label(options,text='CI-V baud').pack(side='left')
ttk.Combobox(options,textvariable=baud_var,values=['4800','9600','19200'],state='readonly',width=9).pack(side='left',padx=10)
ttk.Label(options,text='Address (hex)').pack(side='left',padx=(20,5))
ttk.Entry(options,textvariable=address_var,width=6).pack(side='left')
status=tk.StringVar(value='Select the CI-V port and USB audio input. Close other radio-control apps.')
ttk.Label(frame,textvariable=status,wraplength=680).pack(anchor='w',pady=12)
def refresh():
    oldport=ports.get(port_var.get(),saved.get('port'));oldaudio=audio.get(audio_var.get(),saved.get('audio_device','auto'))
    ports.clear();audio.clear();audio['Automatic USB audio detection']='auto'
    for p in list_ports.comports():
        ports[f'{p.device} — {p.description} — {p.serial_number or ""}']=p.device
    try:
        for i,d in enumerate(sd.query_devices()):
            if d['max_input_channels']>0:
                host=sd.query_hostapis(d['hostapi'])['name']
                audio[f'{i}: {d["name"]} ({host})']=str(i)
    except Exception as exc: status.set('Audio enumeration: '+str(exc))
    port_box['values']=list(ports);audio_box['values']=list(audio)
    port_var.set(next((k for k,v in ports.items() if v==oldport),next(iter(ports),'')))
    audio_var.set(next((k for k,v in audio.items() if v==str(oldaudio)),'Automatic USB audio detection'))
def start():
    if not port_var.get() or port_var.get() not in ports:
        return messagebox.showerror('Choose COM port','Install the Icom driver, connect/power the radio and click Refresh.')
    try:
        address=int(address_var.get(),16)
        if not 0<=address<=255: raise ValueError()
        config={'port':ports[port_var.get()],'audio_device':audio[audio_var.get()],'baud':int(baud_var.get()),'address':f'{address:02X}'}
        CONFIG.write_text(json.dumps(config,indent=2))
    except Exception as exc: return messagebox.showerror('Settings',str(exc) or 'Enter a valid hexadecimal address.')
    # Reuse only a server exposing this application's settings API.
    try:
        with urllib.request.urlopen(URL+'/api/settings',timeout=1) as response:
            data=json.load(response)
        if 'serial_port' in data and 'settings' in data:
            status.set('Panel already running. Stop its server with Ctrl+C to change connections.')
            webbrowser.open(URL);return
    except Exception: pass
    try:
        process=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--port',config['port'],'--audio-device',config['audio_device'],'--baud',str(config['baud']),'--address',config['address']],cwd=ROOT,creationflags=subprocess.CREATE_NEW_CONSOLE)
    except Exception as exc: return messagebox.showerror('Could not start',str(exc))
    start_button.configure(state='disabled');status.set('Starting panel. Keep the new server console open.')
    def wait_ready():
        result='Server did not become ready. Read its console for errors.'
        for _ in range(40):
            if process.poll() is not None: break
            try:
                with urllib.request.urlopen(URL+'/api/settings',timeout=.5) as response:
                    data=json.load(response)
                if 'serial_port' in data:
                    webbrowser.open(URL);result='Panel open. Stop it with Ctrl+C in the server console before changing connections.';break
            except Exception: time.sleep(.25)
        app.after(0,lambda:finish(result))
    threading.Thread(target=wait_ready,daemon=True).start()
def finish(text):
    status.set(text);start_button.configure(state='normal')
buttons=ttk.Frame(frame);buttons.pack(fill='x',pady=8)
start_button=ttk.Button(buttons,text='START PANEL',command=start);start_button.pack(side='left')
ttk.Button(buttons,text='REFRESH DEVICES',command=refresh).pack(side='left',padx=8)
ttk.Button(buttons,text='ICOM USB DRIVER',command=lambda:webbrowser.open('https://www.icomjapan.com/support/firmware_driver/1974/')).pack(side='left')
ttk.Label(frame,text='Power/SWR read during TX. RF sweep retunes the receiver. No demo mode.',wraplength=680).pack(anchor='w',pady=6)
refresh();app.mainloop()
