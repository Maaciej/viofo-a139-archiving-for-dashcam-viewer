#!/usr/bin/env python
# coding: utf-8

# """
# The script sets the $recode and $timelapse flags depending on the mode parameter.
# Mode:
# Selects the script's operating mode:
# 0 - Recode Only (Default)
# 1 - Timelapse Only
# 2 - Both processes (Recode + Timelapse)
# """

import argparse, os, re, subprocess, sys, shutil
from datetime import datetime, timedelta
import winsound

jupyter_runtime = 0
if 'get_ipython' in globals() and type(get_ipython()).__name__ == 'ZMQInteractiveShell':
    jupyter_runtime = 1

parser = argparse.ArgumentParser()
parser.add_argument('mode', type=int, choices=[0, 1, 2], default=0, nargs='?')
args = parser.parse_known_args()[0] if jupyter_runtime else parser.parse_args()

if jupyter_runtime:
    os.chdir(r"c:\\temp\\")
print(os.getcwd())

recode, timelapse, msg = {
    0: (True, False, "=== MODE 0: Recode ==="),
    1: (False, True, "=== MODE 1: ONLY Timelapse ==="),
    2: (True, True, "=== MODE 2: Recode and Timelapse ===")
}[args.mode]

print(msg) 

def set_viofo_time(start_dt: str, video_file: str) -> None:
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_file]
        duration = float(subprocess.check_output(cmd, text=True).strip())
        
        end_time = datetime.strptime(start_dt, "%Y%m%d_%H%M%S") + timedelta(seconds=int(duration + 0.999))
        
        os.utime(video_file, (os.path.getatime(video_file), end_time.timestamp()))
        print(f"\033[92mSuccess: Updated {os.path.basename(video_file)} to {end_time.strftime('%Y-%m-%d %H:%M:%S')}\033[0m")
        
    except Exception as e:
        print(f"\033[91mError processing {video_file}: {e}\033[0m")

print("WORK FOLDER:", os.getcwd())

# Get project name from current directory and list sorted MP4 files matching criteria
project_name = os.path.basename(os.getcwd())
print(f"Project name: {project_name}")

temp_folder = os.path.join(os.getcwd(), "temp")

files = sorted([
    f for f in os.listdir('.') 
    if f.lower().endswith('.mp4') 
    and not f.lower().endswith('_timelapse.mp4') 
    and not f.lower().endswith('_org.mp4') 
    and f.lower() != f"{project_name}.mp4".lower()
])
if not files: raise FileNotFoundError("No mp4 files found.")

# Check and warn if the folder path contains non-ASCII characters
if not temp_folder.isascii():
    print(f"\033[91m[WARNING] Folder path contains non-ASCII characters:\n  -> {temp_folder}\033[0m\n")

# Check and warn if any filenames contain non-ASCII characters
if bad_files := [f for f in files if not f.isascii()]:
    print(
        f"\033[91m[WARNING] Non-ASCII characters detected in filenames:\n"
        f"{'\n'.join(f'  - {f}' for f in bad_files)}\033[0m\n"
    )

# Extract day and 6-digit time string using regex from the first file name, example nam 320_243313.mp4
base_name = os.path.splitext(files[0])[0]
day = base_name[1:3]
hour = match.group(1) if (match := re.search(r'.*(\d{6})', base_name)) else "000000"
print("hour =", hour, "day =", day)

os.makedirs(temp_folder, exist_ok=True)

fmt = lambda s: f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d}.{int(round((s%1)*1000)):03d}"

start_sec, total_duration_sec = 0.0, 0.0
lines_normal, lines_timelapse = [], []

for f in files:
    dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).decode().strip())
    
    lines_normal.append(f"{fmt(start_sec)} {os.path.splitext(f)[0]}")
    if timelapse: lines_timelapse.append(f"{fmt(start_sec / 18)} {os.path.splitext(f)[0]}")
    
    start_sec += dur
    total_duration_sec += dur
    
open(os.path.join(temp_folder, f"{project_name}_files.txt"), 'w', encoding='utf-8').write('\n'.join(lines_normal) + '\n')
if timelapse:
    open(os.path.join(temp_folder, f"{project_name}_timelapse_chapters.txt"), 'w', encoding='utf-8').write('\n'.join(lines_timelapse) + '\n')

output_file = os.path.join(temp_folder, f"{project_name}_ORG.mp4")
print("\033[92mCareful merging video files with GPS data\033[0m")

merge_cmd = f'"mp4_merge-windows64.exe" ' + ' '.join(f'"{f}"' for f in files) + f' --out "{output_file}"'
subprocess.run(merge_cmd, shell=True)

if timelapse:
    print("\033[92mEXIFTOOL extracting gpx from merged video file, ORG GPX\033[0m")
    out_gpx = os.path.join(temp_folder, f"{project_name}_ORG.gpx")
    
    has_bad_chars = not output_file.isascii() or "'" in output_file
    safe_video = os.path.join(temp_folder, "temp_input.mp4") if has_bad_chars else output_file
    if has_bad_chars: os.rename(output_file, safe_video)
    
    try:
        exif = shutil.which("exiftool.exe")
        fmt = os.path.join(os.path.dirname(exif), "gpxVIOFO_A139.fmt") if exif else "gpxVIOFO_A139.fmt"
        
        for flag in ("-ee3", "-ee"):
            with open(out_gpx, "w", encoding="utf-8") as out, open(os.devnull, "w") as devnull:
                subprocess.run(["exiftool.exe", "-charset", "utf8", "-p", fmt, flag, safe_video], stdout=out, stderr=devnull)
            if os.path.exists(out_gpx) and os.path.getsize(out_gpx) >= 200: break
        else:
            open(os.path.join(temp_folder, f"{project_name}_ORG_gpx_ERROR.txt"), 'w', encoding='utf-8').write(f"ERROR, no GPS info in file {project_name}_ORG.mp4.\n")
    finally:
        if has_bad_chars: os.rename(safe_video, output_file)

merged_dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', output_file]).decode().strip())
bad_time_file = os.path.join(temp_folder, f"{project_name}_BADTIME.mp4")

if abs(merged_dur - total_duration_sec) > 0.5:
    print(f"\033[96mVideo Duration mismatch detected! Input files time is {total_duration_sec} s, but merged file time is {merged_dur} s.\033[0m")
    os.rename(output_file, bad_time_file)
    
    concat_list = os.path.join(temp_folder, "ffmpeg_concat_list.txt")
    open(concat_list, 'w', encoding='ascii').write('\n'.join(f"file '../{f.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for f in files) + '\n')
    
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', 'ffmpeg_concat_list.txt', '-c', 'copy', output_file, '-y'], cwd=temp_folder)
    if os.path.exists(concat_list): os.remove(concat_list)
    
    print("\033[92mMerge finished safely! Output saved to: " + output_file + "\033[0m")

print("\033[92mChapters in place for the merged video\033[0m")
_ = subprocess.run(['mp4box.exe', '-noprog', '-chapqt', os.path.join(temp_folder, f"{project_name}_files.txt"), output_file])

if recode:
    print("\033[92mExtracting original audio\033[0m")
    # Run ffmpeg to extract raw audio track without re-encoding and suppress all outputs
    subprocess.run(['ffmpeg.exe', '-hide_banner', '-y', '-i', os.path.join(temp_folder, f"{project_name}_ORG.mp4"), '-vn', '-acodec', 'copy', os.path.join(temp_folder, f"{project_name}_ORG.aac")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Define paths required for the timelapse and transcoding
org_mp4 = os.path.join(temp_folder, f"{project_name}_ORG.mp4")
tl_mp4 = os.path.join(temp_folder, f"{project_name}_timelapse.mp4")
tl_chaps = os.path.join(temp_folder, f"{project_name}_timelapse_chapters.txt")
stream = os.path.join(temp_folder, "stream.265")
time_stamp = f"202603{day}_{hour}"

if timelapse:
    print("\033[92mGenerating timelapse with chapters\033[0m")
    
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'info', '-stats', '-y', '-i', org_mp4, '-map_chapters', '-1', '-vf', 'scale=in_range=full:out_range=full:in_color_matrix=bt709:out_color_matrix=bt709,format=yuv420p10le,setpts=PTS/18,fps=25', '-an', '-c:v', 'libx265', '-crf', '36', '-preset', 'slow', '-x265-params', 'log=0:colorprim=bt709:transfer=bt709:colormatrix=bt709:range=full', tl_mp4])
    
    subprocess.run(['ffmpeg', '-loglevel', 'warning', '-y', '-i', tl_mp4, '-vcodec', 'copy', '-an', stream], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['ffmpeg', '-loglevel', 'warning', '-y', '-r', '25', '-i', stream, '-c', 'copy', '-fflags', '+genpts', tl_mp4], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    subprocess.run(['mp4box.exe', '-noprog', '-chapqt', tl_chaps, tl_mp4], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#    subprocess.run(['viofo_settime.bat', time_stamp, tl_mp4])
    set_viofo_time(time_stamp, tl_mp4)
    
    for f in (tl_chaps, stream): 
        if os.path.exists(f): os.remove(f)

if recode:
    print("\033[92mStarting HandBrake compression\033[0m")
    final_mp4 = os.path.join(temp_folder, f"{project_name}.mp4")
    
    # Run local profile batch script for handbrake transcoding and apply metadata timestamp
    #subprocess.run(['handbrake_profileviofo.bat', '-i', org_mp4, '-o', final_mp4], stderr=subprocess.DEVNULL)
    # Locate HandBrakeCLI in PATH or local directory, then find adjacent preset JSON
    hb_exe = "HandBrakeCLI.exe" if os.path.exists("HandBrakeCLI.exe") else (shutil.which("HandBrakeCLI.exe") or "HandBrakeCLI.exe")
    hb_json = os.path.join(os.path.dirname(hb_exe), "viofo1080slow32h265bit10.json") if os.path.isabs(hb_exe) else "viofo1080slow32h265bit10.json"

    # Execute HandBrakeCLI directly with arguments, suppressing stderr
    subprocess.run([hb_exe, "--verbose", "0", "--preset-import-file", hb_json, "-Z", "viofo1080slow32h265bit10", "-i", org_mp4, "-o", final_mp4], stderr=subprocess.DEVNULL)

    print("\033[92mChapters in place for the final recoded video\033[0m")
    # Inject QuickTime chapters into the final recoded video file using mp4box
    subprocess.run(['mp4box.exe', '-noprog', '-chapqt', os.path.join(temp_folder, f"{project_name}_files.txt"), final_mp4], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#    subprocess.run(['viofo_settime.bat', time_stamp, final_mp4])
    set_viofo_time(time_stamp, final_mp4)

if (gpx_script := subprocess.getoutput("where viofo2one_gpx.py").strip()) and not gpx_script.startswith("INFO:"):
    
    cmd = f'python -u "{gpx_script}"'
    os.makedirs(temp_folder, exist_ok=True)
    log_path = os.path.join(temp_folder, "gpx2one.log")
    process = subprocess.Popen(
        cmd, 
        shell=True, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True
    )
    with open(log_path, "w", encoding="utf-8") as log_file:
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()    
            log_file.write(line)  
            
    process.wait()

winsound.MessageBeep()

print("\033[92mFINISHED\033[0m")