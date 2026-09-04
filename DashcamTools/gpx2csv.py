import sys, os, subprocess
import xml.etree.ElementTree as ET

if __name__ == "__main__":
    gpx = ET.parse(sys.argv[1]).getroot().findall('.//{*}trkpt')
    cols = ['No', 'lat', 'lon'] + list({e.tag.split('}')[-1] for p in gpx for e in p.iter() if e.tag.split('}')[-1] not in ('trkpt', 'extensions')})
    t = gpx[-1].find('{*}time')
    
    time_str = f"{t.text[11:13]}h{t.text[14:16]}m{t.text[17:19]}s" if t is not None else '00h00m00s'
    csv_name = sys.argv[1].replace('.gpx', f" [{len(gpx)}] end_{time_str}.csv")
    row_func = lambda i, p: (f"{i}" if c == 'No' else f"{p.get(c, next((e.text for e in p.iter() if e.tag.endswith('}' + c)), '') or '')}".replace('.', ',') for c in cols)
    
    open(csv_name, 'w', encoding='utf-8-sig').write(";".join(cols) + "\n" + "\n".join(";".join(row_func(idx, pt)) for idx, pt in enumerate(gpx, start=1)))
    
    if os.path.exists(sys.argv[1].replace('.gpx', '.mp4')):
        cmd = os.path.abspath('ffprobe.exe') if os.path.exists('ffprobe.exe') else 'ffprobe'
        
        d = float(subprocess.check_output([cmd, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', sys.argv[1].replace('.gpx', '.mp4')]).decode().strip())
        h, m, s, ms = int(d // 3600), int((d % 3600) // 60), int(d % 60), int(round((d % 1) * 1000))
        
        txt_name = sys.argv[1].replace('.gpx', f" {d:.3f} czas = {h}h{m:02d}m{s:02d}s{ms:03d}ms.txt")
        open(txt_name, 'w').write('')
