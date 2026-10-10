from pathlib import Path
import sys,platform,importlib,traceback
lines=['Python: '+sys.version,'Executable: '+sys.executable,'Platform: '+platform.platform()]
for name in ('tkinter','serial','numpy','sounddevice'):
    try:
        module=importlib.import_module(name)
        lines.append(name+': OK')
        if name=='serial':
            from serial.tools import list_ports
            lines.extend(str(p.device)+' '+str(p.description)+' '+str(p.serial_number) for p in list_ports.comports())
        if name=='sounddevice': lines.append(str(module.query_devices()))
    except Exception: lines.append(name+': FAILED\n'+traceback.format_exc())
text='\n'.join(lines)
print(text)
path=Path(__file__).parent/'diagnostics.txt'
path.write_text(text,encoding='utf-8')
print('Saved:',path)
