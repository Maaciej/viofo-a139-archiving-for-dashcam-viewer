#!/usr/bin/env python
# coding: utf-8
 
import os
import re
import sys
import io
import glob
import struct
import subprocess
import shutil
from datetime import datetime, timezone, timedelta
import pandas as pd
import math
from pandasql import sqldf
pysqldf   = lambda q: sqldf(q, globals() )
pysqldf_l = lambda q: sqldf(q, locals() )
import numpy as np

from IPython.display import display, HTML, Javascript
from tabulate import tabulate
from contextlib import redirect_stdout
from pathlib import Path
import json

print("VIOFO2ONE_GPX Working folser is:", os.getcwd())

import warnings
warnings.filterwarnings("ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated",
    category=FutureWarning,
)

jupyter_runtime = 0
if 'get_ipython' in globals() and type(get_ipython()).__name__ == 'ZMQInteractiveShell':
    jupyter_runtime = 1

if jupyter_runtime:
    os.chdir(r"c:\\temp\\")
print("Aktualny katalog to:", os.getcwd())

working_folder = os.getcwd()
working_name = os.path.basename(working_folder)
print(f"Working name: {working_name}")

temp_folder = os.path.join(working_folder, "temp")

timelapse = 0
if jupyter_runtime:
    timelapse = 0
    print( "in jupyterlab, timelapse mode is set manually")
else:
    if len(sys.argv) > 1:
        timelapse = 1

# normal run: write individual and merged gpx files with extracted GPS and if timelapse video exists make the timelapse gpx also
# timelapse run: do no twrite individual gpx files and norlal megrad gpx

if timelapse:
    print( "GPX2ONE TIMELAPSE MODE")
else:
    print( "GPX2ONE ONE, extract MODE (maybe there will be timelapse")

exiftool_gpx_sub_folder = os.path.join(temp_folder, f"{working_name} exiftool gpx")
skrypt_gpx_sub_folder = os.path.join(temp_folder, f"{working_name} skrypt gpx")
if not timelapse:
    os.makedirs(exiftool_gpx_sub_folder, exist_ok=True)
    os.makedirs(skrypt_gpx_sub_folder, exist_ok=True)

pattern_skip = re.compile(rf"(_timelapse| timelapse|_ORG|{re.escape(working_name)})\.mp4$", re.IGNORECASE)

mp4_files = []
for file in sorted(glob.glob("*.mp4")):
    if not pattern_skip.search(file):
        print(file)
        mp4_files.append(file)

if not mp4_files:
    print("No mp4 files found.")
    sys.exit(1)
    
# Check and warn if the folder path contains non-ASCII characters
if not temp_folder.isascii():
    print(f"\033[91m[WARNING] Folder path contains non-ASCII characters:\n  -> {temp_folder}\033[0m\n")

# Check and warn if any filenames contain non-ASCII characters
if bad_files := [f for f in mp4_files if not f.isascii()]:
    print(
        f"\033[91m[WARNING] Non-ASCII characters detected in filenames:\n"
        f"{'\n'.join(f'  - {f}' for f in bad_files)}\033[0m\n"
    )

print( "working folder = ", working_folder, "\nTemp folder    = ", temp_folder )
print( "exiftool_gpx_sub_folder = ", exiftool_gpx_sub_folder, "\nskrypt_gpx_sub_folder    = ", skrypt_gpx_sub_folder )

def gpx_extract_with_exiftool( mp4name ):

    mp4_basename, _ = os.path.splitext( mp4name )
    tmp_gpx_path   = os.path.join(exiftool_gpx_sub_folder, f"{mp4_basename}_exiftool.gpx")
    failed_gpx_path = os.path.join(exiftool_gpx_sub_folder, f"{mp4_basename}_FAILED_GPX.gpx")

    Path(tmp_gpx_path).unlink(missing_ok=True)
    Path(failed_gpx_path).unlink(missing_ok=True)

    if not( mp4_basename.isascii() ): #filename with special characters, exiftool script does not like it, making temporary file
        temp_mp4_path = os.path.join( working_folder, "exif_temp.mp4" )
        shutil.copy2(os.path.abspath( mp4name ), temp_mp4_path)
        target_file_arg = temp_mp4_path

    temp_data = ""
    try:
        exif = "exiftool.exe" if os.path.exists("exiftool.exe") else (shutil.which("exiftool.exe") or "exiftool.exe")
        fmt = os.path.join(os.path.dirname(exif), "gpxVIOFO_A139.fmt") if os.path.isabs(exif) else "gpxVIOFO_A139.fmt"
        
        base_cmd = [exif, "-charset", "utf8", "-p", fmt]
        
        result = subprocess.run(base_cmd + ["-ee3", os.path.abspath(mp4name)], capture_output=True, text=True, check=False)
        temp_data = result.stdout

        if not temp_data or len(temp_data.splitlines()) < 5:
            result = subprocess.run(base_cmd + ["-ee", os.path.abspath(mp4name)], capture_output=True, text=True, check=False)
            temp_data = result.stdout

    except Exception as e:
        print(f"Exiftool error for {mp4name}: {e}")


    if not( mp4_basename.isascii() ): #delete temporary file without special characters in name
        if os.path.isfile( temp_mp4_path ):
            os.remove( temp_mp4_path )

    if temp_data and "<trkpt" in temp_data:
            
        with open(tmp_gpx_path, "w", encoding="utf-8") as f:
            f.write(temp_data)
    else:
        with open(failed_gpx_path, "w", encoding="utf-8") as f:
            f.write("")

    return

def build_frame_array(mp4_path):

    file_size = os.path.getsize(mp4_path)
    video_offsets = []
    fps = 30.0

    # frames addresses
    with open(mp4_path, "rb") as f:
        seek_size = min(file_size, 15 * 1024 * 1024)
        tail_start_pos = file_size - seek_size
        f.seek(tail_start_pos)
        tail_data = f.read(seek_size)

        co64_idx = tail_data.find(b'co64')
        
        header_ok = True
        total_video_frames = 0

        if co64_idx == -1:
            print(f"\033[31m[ WARNING] No co64 tag in: {os.path.basename(mp4_path)}. Switching to workaround.\0330m")
            header_ok = False
        else:
            co64_absolute_pos = tail_start_pos + co64_idx
            f.seek(co64_absolute_pos + 8)
            raw_count = f.read(4)

            if len(raw_count) == 4:
                total_video_frames = struct.unpack(">I", raw_count)[ 0]
                
                if total_video_frames > 500000 or total_video_frames <= 0:
                    print(f"\033[31m[ WARNIG] Frame counter incorrect ({total_video_frames}). Switching to workaround.\033[0m")
                    header_ok = False

        if header_ok and total_video_frames > 0:
            current_position = f.tell()
            max_bytes = file_size - current_position
            needed_bytes = total_video_frames * 8

            if needed_bytes > max_bytes:
                print(f"[ Warning] Address table is physically truncated in the file. I'm trimming it to actual size..")
                needed_bytes = (max_bytes // 8) * 8
                total_video_frames = needed_bytes // 8

            raw_table = f.read(needed_bytes)
            if len(raw_table) == needed_bytes:
                video_offsets = list(struct.unpack(f">{total_video_frames}Q", raw_table))

        else:
            cmd = [
                'ffprobe', '-v', 'error', 
                '-select_streams', 'v:0', 
                '-count_packets', 
                '-show_entries', 'stream=nb_read_packets,r_frame_rate', 
                '-of', 'json', mp4_path
            ]
            try:
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                data = json.loads(result.stdout)

                total_video_frames = int(data[ 'streams'][ 0][ 'nb_read_packets'])
                
                if 'r_frame_rate' in data[ 'streams'][ 0]:
                    num, den = map(int, data[ 'streams'][ 0][ 'r_frame_rate'].split('/'))
                    if den > 0:
                        fps = num / den

            except Exception as e:
                pass

            if total_video_frames > 0:
                step = file_size / total_video_frames
                video_offsets = [ int(i * step) for i in range(total_video_frames)]

    frames_list = []
    for idx, offset in enumerate(video_offsets):
        time_in_ms = int((idx / fps) * 1000)  

        frames_list.append({
            "frame_no": idx + 1,
            "adres_dec": offset,
            "adres_hex": f"0x{offset:08x}",
            "time_ms": time_in_ms,
            "time_sec": time_in_ms / 1000.0
        })


    return pd.DataFrame(frames_list)

def extract_novatek_gps_direct(mp4_path):

    frames_df = build_frame_array(mp4_path)

    if frames_df.empty:
        print(f"  [ ERROR] The video frame table is empty for the file: {os.path.basename(mp4_path)}")
        return []

    file_size = os.path.getsize(mp4_path)

    with open(mp4_path, "rb") as f:
        seek_size = min(file_size, 10 * 1024 * 1024)
        tail_start_pos = file_size - seek_size
        f.seek(tail_start_pos)
        tail_data = f.read(seek_size)

        gps_idx = tail_data.find(b'gps ')
        if gps_idx == -1:
            print(f"  [ ERROR] GPS table of contents not found in {os.path.basename(mp4_path)}")
            return []

        gps_absolute_pos = tail_start_pos + gps_idx

        f.seek(gps_absolute_pos + 4)
        header_flags = struct.unpack(">I", f.read(4))[ 0]
        total_samples = struct.unpack(">I", f.read(4))[ 0]

        print( f"Declared points = {total_samples}" )

        raw_entries = []
        for _ in range(total_samples):
            chunk_offset = struct.unpack(">I", f.read(4))[ 0]
            chunk_size = struct.unpack(">I", f.read(4))[ 0]
            raw_entries.append((chunk_offset, chunk_size))

    points_from_mp4 = []

    for idx, (offset, size) in enumerate(raw_entries):
        sample_num = idx + 1

        closest_idx = (frames_df[ 'adres_dec'] - offset).abs().idxmin()

        sample_frame = int(frames_df.loc[ closest_idx, 'frame_no'])
        sample_video_ms = int(frames_df.loc[ closest_idx, 'time_ms'])

        with open(mp4_path, "rb") as f:
            f.seek(offset)
            chunk_data = f.read(64)

        if chunk_data[ 16:32] == b'\x00' * 16:
            points_from_mp4.append({
                "sample_no": sample_num,
                "video_ms": sample_video_ms,
                "video_frame": sample_frame,
                "has_fix": None,
                "lat": None,
                "lon": None,
                "speed": None,
                "bearing": None,
                "gps_time_str": None
            })
            continue

        try:
            hr = struct.unpack("<I", chunk_data[ 16:20])[ 0]
            mn = struct.unpack("<I", chunk_data[ 20:24])[ 0]
            sc = struct.unpack("<I", chunk_data[ 24:28])[ 0]
            yr = struct.unpack("<I", chunk_data[ 28:32])[ 0]
            mo = struct.unpack("<I", chunk_data[ 32:36])[ 0]
            dy = struct.unpack("<I", chunk_data[ 36:40])[ 0]

            if yr < 100:
                yr += 2000

            gps_time_str = f"{yr:04d}-{mo:02d}-{dy:02d} {hr:02d}:{mn:02d}:{sc:02d}Z"

            lat_raw = struct.unpack("<f", chunk_data[ 44:48])[ 0]
            lon_raw = struct.unpack("<f", chunk_data[ 48:52])[ 0]
            speed_raw = struct.unpack("<f", chunk_data[ 52:56])[ 0] 
            track_raw = struct.unpack("<f", chunk_data[ 56:60])[ 0] 

            lat_deg = int(lat_raw / 100) + (lat_raw % 100) / 60.0
            lon_deg = int(lon_raw / 100) + (lon_raw % 100) / 60.0

            flags = chunk_data[ 40:44].decode('ascii', errors='ignore')
            if 'S' in flags: lat_deg = -lat_deg
            if 'W' in flags: lon_deg = -lon_deg

            points_from_mp4.append({
                "sample_no": sample_num,
                "video_ms": sample_video_ms,
                "video_frame": sample_frame,
                "has_fix": True if (len(flags) > 0 and flags[ 0] == 'A') else False,
                "lat": lat_deg,
                "lon": lon_deg,
                "speed": speed_raw,
                "bearing": track_raw,
                "gps_time_str": gps_time_str
            })
        except Exception:
            continue

    return points_from_mp4

def fill_null_gps_start(df):

    df_out = df.copy()

    complex_condition = df_out[ 'lat'].notna() & df_out[ 'lon'].notna() & df_out[ 'time'].notna()

    correct_indexes = df_out[ complex_condition].index
    first_correct_idx = correct_indexes[ 0] if not correct_indexes.empty else None

    if first_correct_idx is not None:
        first_correct_row = df_out.loc[ first_correct_idx]
    
        base_time_str = first_correct_row[ 'time'].replace('T', ' ').replace('Z', '')
        base_datetime = datetime.strptime(base_time_str, "%Y-%m-%d %H:%M:%S")
    
        for idx in range(first_correct_idx):
            delta_seconds = idx - first_correct_idx
            exact_utc = base_datetime + timedelta(seconds=int(delta_seconds))
    
            df_out.loc[ idx, 'time'] = exact_utc.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    
            df_out.loc[ idx, 'lat'] = first_correct_row[ 'lat']
            df_out.loc[ idx, 'lon'] = first_correct_row[ 'lon']
    
            df_out.loc[ idx, 'viofo_knots'] = first_correct_row[ 'viofo_knots']
            df_out.loc[ idx, 'viofo_mps'] = first_correct_row[ 'viofo_mps']
            df_out.loc[ idx, 'geo_mps'] = first_correct_row[ 'geo_mps']
            df_out.loc[ idx, 'kmh'] = first_correct_row[ 'kmh']
            df_out.loc[ idx, 'mph'] = first_correct_row[ 'mph']
            df_out.loc[ idx, 'bearing'] = first_correct_row[ 'bearing']

        print(f"\033[32mRecreated {first_correct_idx} records at start.\033[0m")
        
    return df_out

def fix_null_end_gps(df):
    df_out = df.copy()

    valid_record_condition = df_out[ 'lat'].notna() & df_out[ 'lon'].notna() & df_out[ 'time'].notna()
    valid_indexes = df_out[ valid_record_condition].index
    last_valid_idx = valid_indexes[ -1] if not valid_indexes.empty else None

    if last_valid_idx is not None:
        last_valid_row = df_out.loc[ last_valid_idx]
    
        base_time_str = last_valid_row[ 'time'].replace('T', ' ').replace('Z', '')
        if '.' in base_time_str:
            base_datetime = datetime.strptime(base_time_str, "%Y-%m-%d %H:%M:%S.%f")
        else:
            base_datetime = datetime.strptime(base_time_str, "%Y-%m-%d %H:%M:%S")
    
        empty_rows_at_end_count = (len(df_out) - 1) - last_valid_idx
        
        for idx in range(last_valid_idx + 1, len(df_out)):
            delta_seconds = idx - last_valid_idx
            exact_utc = base_datetime + timedelta(seconds=int(delta_seconds))
    
            milliseconds_str = f"{exact_utc.microsecond // 1000:03d}"
            if '.' in last_valid_row[ 'time']:
                milliseconds_str = f"{exact_utc.microsecond // 1000:03d}"
                df_out.loc[ idx, 'time'] = exact_utc.strftime("%Y-%m-%dT%H:%M:%S.") + milliseconds_str + "Z"
            else:
                df_out.loc[ idx, 'time'] = exact_utc.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    
            df_out.loc[ idx, 'lat'] = last_valid_row[ 'lat']
            df_out.loc[ idx, 'lon'] = last_valid_row[ 'lon']
    
            df_out.loc[ idx, 'viofo_knots'] = last_valid_row.get('viofo_knots')
            df_out.loc[ idx, 'viofo_mps'] = last_valid_row.get('viofo_mps')
            df_out.loc[ idx, 'geo_mps'] = last_valid_row.get('geo_mps')
            df_out.loc[ idx, 'kmh'] = last_valid_row.get('kmh')
            df_out.loc[ idx, 'mph'] = last_valid_row.get('mph')
            df_out.loc[ idx, 'bearing'] = last_valid_row.get('bearing')

        print(f"\033[32mRecreated {empty_rows_at_end_count} records at the end of the DataFrame.\033[0m")
        
    return df_out

def geo_speed_mps( start_lon, start_lat, end_lon, end_lat ):

    try:
        d_lat = math.radians( float( end_lat ) - float( start_lat ) )
        d_lon = math.radians( float( end_lon ) - float( start_lon ) )

        a = ( math.sin(d_lat / 2) ** 2 +
              math.cos(math.radians( float( start_lat ) )) *
              math.cos(math.radians( float( end_lat ) )) *
              math.sin(d_lon / 2) ** 2 )
    
    except (TypeError, ValueError):
        return -1.0
            
    return 6371000 * ( 2 * math.atan2( math.sqrt( a ), math.sqrt( 1 - a ) ) )

def straighten_the_time(df):

    timestamp = 1
    df_out = df.copy()
    start_time_str = df_out.loc[ 0, 'time']
    base_datetime = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%SZ")

    for idx in df_out.index:
        fixed_dt = base_datetime + timedelta(seconds=int(idx))
        df_out.loc[ idx, 'time'] = fixed_dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        df_out.loc[ idx, 'point_no'] = timestamp
        timestamp += 1

    return df_out

def gpx_testfix( df, mode, total = "no" ):
#mode can be
# auditrepair - tests and sets flags and than repair
# retest - tests, we check results after repair

    video_duration = df.iloc[ 0][ "mp4_duration" ] if total == "no" else total_time
    filename = df.loc[ 0, "file" ] if total == "no" else "total"
        
    expected_count = math.floor( video_duration )
        
    if mode == "auditrepair":
        df[ 'missing_end' ] = int( 0 )
        
    if len( df ) < expected_count:
        print(f"\033[31m[ { filename } ] Number of GPS points less than video length by { str( expected_count - len( df ) ) } rows.\033[0m")

        if mode == "auditrepair":
            extra_df = pd.DataFrame( index = range( expected_count - len( df ) ), columns = df.columns )
            extra_df[ "gpsno" ] = -1
            extra_df[ "video_ms" ] = -1
            extra_df[ "video_frame" ] = -1
            extra_df[ "bad_end" ] = 1
            extra_df[ "has_fix" ] = False
            extra_df[ "mp4_duration" ] = video_duration
            extra_df[ "file" ] = df.iloc[ 0 ][ "file" ]
            extra_df[ "missing_end" ] = 1

            extra_df = extra_df.astype(df.dtypes)
            df = pd.concat([ df, extra_df], ignore_index = True )

    
    if math.isclose( video_duration, expected_count):      
        if mode == "auditrepair":
            df[ "mp4_extra_time" ] = 0.0
    else:
        print(f"\033[31m[ { filename } ] The file is longer than equal seconds by { ( video_duration - expected_count):.3f} s.\033[0m")
        if mode == "auditrepair":
            df[ "mp4_extra_time" ] = video_duration - expected_count

    #NULL testing
    if mode == "auditrepair":
        df[ 'lat_null']     = df[ 'lat'].isna().astype(int)
        df[ 'lon_null']     = df[ 'lon'].isna().astype(int)
        df[ 'time_null']    = df[ 'time'].isna().astype(int)
        df[ 'knots_null']   = df[ 'viofo_knots'].isna().astype(int)
        df[ 'bearing_null'] = df[ 'bearing'].isna().astype(int)

    if df[ [ 'lat', 'lon', 'time', 'viofo_knots', 'bearing']].isna().sum().sum() > 0:
        message = ", ".join([ f"{v} NULL values in w {k}" for k, v in df[ [ 'lat', 'lon', 'time', 'viofo_knots', 'bearing']].isna().sum().items() if v > 0])
        print(f"\033[31mDetected {message}.\033[0m")

    if mode == "auditrepair":
        df[ 'null_start'] = int( 0 )
        
    for s in range(0, len(df) ):
        if df.loc[ s, [ 'lat', 'lon', 'time']].isna().any():
            if mode == "auditrepair":
                df.loc[ s, 'null_start'] = 1
        else:
            break
            
    if s > 0:
        print(f"\033[31m[ { filename } ] first {s+1} records incomplete\033[0m")
    start = s
    
    if mode == "auditrepair":
        df[ 'null_end'] = int( 0 )
    for e in range(len(df) - 1, 0, -1 ):
        if df.loc[ e, [ 'lat', 'lon', 'time']].isna().any():
            if mode == "auditrepair":
                df.loc[ e, 'null_end'] = 1
        else:
            break

    if e < len(df) - 1:
        print(f"\033[31m[ { filename } ] last { len(df) - 1 - e} records incomplete\033[0m")

    end = e

    try:
        distance2 = round(math.sqrt((((df.loc[ start + 1, 'lon'] - df.loc[ start, 'lon']) * 111.32 * math.cos(math.radians(df.loc[ start + 1, 'lat'])))**2) + (((df.loc[ start + 1, 'lat'] - df.loc[ start , 'lat']) * 111.12)**2)), 3)
    except:
        distance2 = -1.0

    if distance2 > 5.0:
        print(f"{chr(27) + '[31m'}Distance between first two GPS points = {distance2}\033[0m")

    try:
        distance2end = round(math.sqrt((((df.loc[ end, 'lon'] - df.loc[ end - 1, 'lon']) * 111.32 * math.cos(math.radians(df.loc[ end, 'lat'])))**2) + (((df.loc[ end, 'lat'] - df.loc[ end - 1, 'lat']) * 111.12)**2)), 3)
    except:
        distance2end = -1.0

    if distance2end > 5.0:
        print(f"{chr(27) + '[31m'}Distance between last two GPS points = {distance2end}\033[0m")

    if mode == "auditrepair":
        df[ 'teleportation_point'] = int( 0 ) # 5 km in 1 second is 18 000km/h. One such point in DV is lineary extrapollated, more than one is not fixed.
    for j in range( start + 1, len(df) ):
        distance = 0.0
        try:
            distance = round(math.sqrt((((df.loc[ j, 'lon'] - df.loc[ j-1, 'lon']) * 111.32 * math.cos(math.radians(df.loc[ j, 'lat'])))**2) + (((df.loc[ j, 'lat'] - df.loc[ j-1, 'lat']) * 111.12)**2)), 3)
        except:
            pass
        if distance > 5:
            print(f"\033[31m[ { df.loc[ j, 'file'] } ] Distance between two GPS points greater than 5 km = {distance} at { 'total' if total == 'yes' else '' } index = { j }\033[0m")
            if mode == "auditrepair":
                df.loc[ j, 'teleportation_point'] = 1

    if mode == "auditrepair":
        df[ 'frozen_time']  = int( 0 )
        df[ 'skipped_time'] = int( 0 )

    for i in range( start + 1, end + 1 ):
        if pd.notna(df.loc[ i-1, 'time']) and pd.notna(df.loc[ i, 'time']):

            delta = (datetime.strptime(df.loc[ i, 'time'], "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(df.loc[ i-1, 'time'], "%Y-%m-%dT%H:%M:%SZ") ).total_seconds()

            if delta == 0:
                print(f"\033[31m[ { df.loc[ i, 'file'] } ] Time frozen at { 'total' if total == 'yes' else '' } index = {i}: Previous and current time is {df.loc[ i, 'time']}\033[0m", flush=True )
                if mode == "auditrepair":
                    df.loc[ i, "frozen_time" ] = 1
            elif delta > 1 or delta < 0:
                print(f"\033[31m[ { df.loc[ i, 'file'] } ] Time skip {int(delta)} s at { 'total' if total == 'yes' else '' } index {i}: {df.loc[ i-1, 'time']} -> {df.loc[ i, 'time']}\033[0m", flush = True )
                if mode == "auditrepair":
                    df.loc[ i, "skipped_time" ] = 1
        elif pd.isnull( df.loc[ i, 'time'] ) and i > start and i < end:
            print(f"\033[31m[ { df.loc[ i, 'file'] } ] Undefined timestamp in record on { 'total' if total == 'yes' else '' } index {i}\033[0m")
            if mode == "auditrepair":
                df.loc[ i, "skipped_time" ] = 1

    clean_time = pd.to_datetime(df[ 'time'], errors='coerce', format='%Y-%m-%dT%H:%M:%SZ').dt.tz_localize(None).dropna()

    print(f"Timestamp: MIN: {chr(27) + '[32m' if pd.Timestamp('2010-01-01') <= clean_time.min() <= pd.Timestamp('2038-01-19') else chr(27) + '[31m'}{clean_time.min()}{chr(27) + '[0m'}, MAX: {chr(27) + '[32m' if pd.Timestamp('2010-01-01') <= clean_time.max() <= pd.Timestamp('2038-01-19') else chr(27) + '[31m'}{clean_time.max()}{chr(27) + '[0m'}, Duration: {1+(clean_time.max() - clean_time.min()).total_seconds() if not clean_time.empty else 0}s")

    if mode == "auditrepair":
        df[ 'lat_skip'] = int( 0 )
        df[ 'lon_skip'] = int( 0 )

    for i in range( start+1, end + 1 ):

        if pd.notna(df.loc[ i, 'lon']) and pd.notna(df.loc[ i-1, 'lon']) and df.loc[ i, 'lon'] - df.loc[ i-1, 'lon'] > 5:
            if mode == "auditrepair":
                df.loc[ i, "lon_skip" ] = 1

        if pd.notna(df.loc[ i, 'lat']) and pd.notna(df.loc[ i-1, 'lat']) and df.loc[ i, 'lat'] - df.loc[ i-1, 'lat'] > 5:
            if mode == "auditrepair":
                df.loc[ i, "lat_skip" ] = 1

        if df.loc[ i, "lon_skip" ] == 1 or df.loc[ i, "lat_skip" ] == 1:
            print(f"\033[31m[ {df.loc[ 0, 'file']} ] Index {i}: Geo jump {round(math.sqrt((((df.loc[ i, 'lon'] - df.loc[ i-1, 'lon']) * 111.32 * math.cos(math.radians(df.loc[ i, 'lat'])))**2) + (((df.loc[ i, 'lat'] - df.loc[ i-1, 'lat']) * 111.12)**2)), 3)} km (ΔLat: {df.loc[ i, 'lat'] - df.loc[ i-1, 'lat']}, ΔLon: {df.loc[ i, 'lon'] - df.loc[ i-1, 'lon']})\033[0m")        

    for i in range( start, end + 1 ): # test for speeds over 500 km/h
        if pd.notna( df.loc[ i, 'viofo_mps' ] ) and df.loc[ i, 'viofo_mps'] * 3.6 > 500: #viofo_mps is going to gpx, so we testing viofo_mps
            print(f"\033[33m[ {df.loc[ 0, 'file']} ] { 'Total i' if total == 'yes' else 'I' }ndex {i}: Too high speed: { round(df.loc[ i, 'viofo_mps' ]  * 3.6, 3 ) }  km/h\033[0m")

    for n in range( start, end + 1  ):
        try:
            mps_diff = df.loc[ n, 'viofo_mps' ] - df.loc[ n - 1, 'viofo_mps' ]
        except:
            mps_diff = 0.0
        if abs( mps_diff) > 4:
            #speed directly from gps chip from doppler efect is good, speed from point to point aritmetic can show rapid speed changes
            print(f"\033[31m[ { df.loc[ n, 'file'] } ] { 'Total i' if total == 'yes' else 'I' }ndex {n}: Point to Point acceleration = {mps_diff:.3f} m/s2\033[0m") 

    try:
        max_diff = df[ "viofo_mps"].diff().max()
        min_diff = df[ "viofo_mps" ].diff().min()
        max_diff_str = f'{max_diff:.5f}' if pd.notna(max_diff) else "NaN"
        min_diff_str = f'{min_diff:.5f}' if pd.notna(min_diff) else "NaN"
    except:
        max_diff_str = 'NaN'
        min_diff_str = 'NaN'
        
    print(f'MAX Speed: {df[ "viofo_mps" ].max() * ( 3600 / 1609.344 ):.3f} mph, {df[ "viofo_mps" ].max() * 3.6:.3f} km/h, MAX Acceleration = {max_diff_str}, MAX DEcceleration = {min_diff_str}.')
    
    #fixing on the end to not spoil testing
    if mode == "auditrepair":
        if ( df[ 'null_start'] == 1 ).any():
            df = fill_null_gps_start(df)

        if ( df[ 'null_end'] == 1 ).any():
            df = fix_null_end_gps(df)

        if ( df[ 'frozen_time'] == 1 ).any() or ( df[ 'skipped_time'] == 1 ).any() :
            df = straighten_the_time(df)

        if (   ( df[ 'lat_null' ] == 1 ).sum() > ( df[ 'null_start' ] == 1 ).sum() + ( df[ 'null_end' ] == 1 ).sum()
            or ( df[ 'lon_null' ] == 1 ).sum() > ( df[ 'null_start' ] == 1 ).sum() + ( df[ 'null_end' ] == 1 ).sum()
           ):
            #lon lat interpolation if NULLs inside data block
            df[["lat", "lon"]] = df[["lat", "lon"]].apply(pd.to_numeric, errors='coerce')
            df.iloc[ start : end + 1, df.columns.get_indexer( [ "lat", "lon" ] ) ] = ( 
                df.iloc[ start : end + 1][ [ "lat", "lon" ] ].interpolate( method = "linear" )  )
            #fill statistics    
            df.loc[ start:end, [ "viofo_knots", "viofo_mps", "geo_mps", "kmh", "mph", "bearing" ]] = df.loc[ start:end, [ "viofo_knots", "viofo_mps", "geo_mps", "kmh", "mph", "bearing" ] ].ffill()
    
    return df

def write_df2gpx(output_gpx_path, df, bearing = "no", timelapse = "no" ):  

    if df.iloc[ 0]['time' ] is not None:
        gpx_lines = [ '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                ,'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="Python" xmlns:nstd="http://custom">'
                ,'  <metadata><name>Produced by python script directly from VIOFO A139 mp4 file</name>'
            ]

        #logging GPS data problems
        tgpx_lines = list()
        if len( df ) < math.floor( df.iloc[ 0 ][ "mp4_duration" ] ):
            tgpx_lines.append(f"""          <nstd:mp4_duration>{df.iloc[0]['mp4_duration' ]:.3f}</nstd:mp4_duration>
              <nstd:read_points>{df.iloc[0][ 'org_gpss' ]}</nstd:read_points>""")
    
    
        mp4_extra_time = df[ 'mp4_extra_time' ].max()
        if mp4_extra_time > 0: tgpx_lines.append(f"""          <nstd:mp4_extra_time>{mp4_extra_time:.3f}</nstd:mp4_extra_time>""")
    
        bad_first      = df[ 'null_start'].sum()
        null_lat       = df[ 'lat_null'].sum()
        null_lon       = df[ 'lon_null'].sum()
        null_time      = df[ 'time_null'].sum()
        null_knots     = df[ 'knots_null'].sum()
        frozen_time    = df[ 'frozen_time'].sum()
        skipped_time   = df[ 'skipped_time'].sum()
    
        if bad_first > 0:    tgpx_lines.append(f"          <nstd:bad_first_points>{bad_first}</nstd:bad_first_points>")
        if null_lat > 0:     tgpx_lines.append(f"          <nstd:null_lat>{null_lat}</nstd:null_lat>")
        if null_lon > 0:     tgpx_lines.append(f"          <nstd:null_lon>{null_lon}</nstd:null_lon>")
        if null_time > 0:    tgpx_lines.append(f"          <nstd:null_time>{null_time}</nstd:null_time>")
        if null_knots > 0:   tgpx_lines.append(f"          <nstd:null_knots>{null_knots}</nstd:null_knots>")
        if frozen_time > 0:  tgpx_lines.append(f"          <nstd:frozen_time>{frozen_time}</nstd:frozen_time>")
        if skipped_time > 0: tgpx_lines.append(f"          <nstd:skipped_time>{skipped_time}</nstd:skipped_time>")
    
        if len( tgpx_lines ) and timelapse == "no":
            gpx_lines.append(f"    <extensions>")
            gpx_lines.extend( tgpx_lines )
            gpx_lines.append(f"    </extensions>")
    
        gpx_lines.append(
        f"""  </metadata>
      <trk><name>Track Start Time: { df.iloc[0]['time' ] }</name>
        <trkseg>""")
    
        for idx, row in df.iterrows():
    
            time = datetime.strptime(row["time" ], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    
            if idx > 0:
                time += timedelta( milliseconds = 1 )
            # orientation (bearing) is not standard, some programs use <course> apparently,
            # DV the program neither reads nor writes, and in fact, if there is any unknown element, it does not load <speed>,
            # accepts only <ele> beside track point coordinates, time and speed (?), 
            # so there is course for archiving because the GPS chip using the Doppler is apparently more accurate and in terms of speed and bearing
            # Viofo log speed in Knots.
            if timelapse == "no":
                gpx_lines.append(f'      <trkpt lat="{row["lat" ]:.7f}" lon="{row["lon" ]:.7f}"><time>{time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"}</time><speed>{row["viofo_mps" ]:.4f}</speed>{f"""<course>{row["bearing" ]:.2f}</course>""" if bearing == "yes" else ""}</trkpt>')
            else:
                gpx_lines.append(f'      <trkpt lat="{row["lat" ]:.7f}" lon="{row["lon" ]:.7f}"><time>{row["time_timelapse" ]}</time><speed>{row["viofo_mps" ]:.4f}</speed></trkpt>')
    
        gpx_lines.extend([
                '    </trkseg>',
                '  </trk>',
                '</gpx>'
            ])
    
        with open(output_gpx_path, "w", encoding="utf-8") as f:
            f.write("\n".join(gpx_lines))

    else:
        df.apply(lambda col: col.map(lambda x: str(x).replace('.', ','))).to_csv( "temp\\" + mp4name + " DEBUG ( " + str( len( df ) ) + " ).csv", index = False, sep = ';' )
        print(f"\033[31m[GPX] No data to write: {os.path.basename(output_gpx_path)}, DEBUG info saved\033[0m")

# MAIN LOOP
points_df = pd.DataFrame()
total_time = float( 0 )

for mp4name in mp4_files:
    points = []
    mp4_fullname    = os.path.abspath(  mp4name )
    mp4_basename, _ = os.path.splitext( mp4name )

    if not timelapse:
        gpx_extract_with_exiftool( mp4name )

    part_duration_raw = ""
    try:
        ff_res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", mp4_fullname], 
            capture_output=True, text=True, check=False
        )
        part_duration_raw = ff_res.stdout.strip()
    except Exception:
        print("Failed to read mp4 duration:", mp4name, "\n\n")
        sys.exit()

    total_time =+ float( part_duration_raw )
    part_target_lines_count = math.floor( float( part_duration_raw ) )

    print(f"\033[94mFile processing: { os.path.basename( mp4_fullname ) } ( {float( part_duration_raw ):.2f} s)\033[0m" )

    raw_mp4_points = extract_novatek_gps_direct( mp4name )

    if not raw_mp4_points:
        print(f"  [ERROR] Missing binary GPS structure in file: { mp4name }")
        sys.exit()

    gps = 0
    mp4_points_to_gpx = []

    for idx, pt in enumerate( raw_mp4_points ):

        geo_mps: float | None = None
        if gps > 0:
            geo_mps = geo_speed_mps( points[ -1 ][ "lon" ], points[ -1 ][ "lat" ], pt[ 'lon' ], pt[ 'lat' ] )
            if gps == 1:
                points[-1]["geo_mps" ] = geo_mps
        
        point_record = {
            "gpsno":         gps,
            "file":          mp4name,
            "mp4_duration":  float( part_duration_raw ),
            "points_needed": math.floor( float( part_duration_raw ) ),
            "lat":           pt[ 'lat' ],
            "lon":           pt[ 'lon' ],
            "time":          pt[ "gps_time_str" ].replace(" ", "T") if pt["gps_time_str" ] is not None else None,
            "video_frame":   pt[ "video_frame" ],         # Actual frame number taken from the table of contents
            "video_ms":      pt[ "video_ms" ],            # position in the film converted from frames
            "viofo_knots":   float( pt[ 'speed' ] ) if pt[ 'speed' ] is not None else None,
            "viofo_mps":     float( pt[ 'speed' ] ) * ( 1852 / 3600 ) if pt[ 'speed' ] is not None else None,      # knots to m/s
            "geo_mps":       geo_mps,
            "kmh":           float( pt[ 'speed' ] ) * 1.852 if pt[ 'speed' ] is not None else None,
            "mph":           float( pt[ 'speed' ] ) * ( 1852 / 1609.344 ) if pt[ 'speed' ] is not None else None,
            "bearing":       pt[ 'bearing' ],             # The original Viofo "GPSTrack" named as bearing
            "has_fix":       pt[ "has_fix" ]
        }

        points.append(point_record)
        gps += 1

    print(f"Read {gps} GPS records from {mp4name}")
    points_df1 = pd.DataFrame( points )
    points_df1['org_gpss'] = len(points_df1)
   

    print("\033[94m=======================  TESTING AND FIXING INPUT DATA   ==============================\033[0m")

    points_df1 = gpx_testfix( points_df1, "auditrepair" )

    print("\033[33m=======================         RETEST FIXED DATA        ==============================\033[0m")

    points_df1 = gpx_testfix( points_df1, "retest" )
    if not timelapse:
        write_df2gpx(str(Path(skrypt_gpx_sub_folder) / Path(mp4name).with_suffix("")).strip() + "_skrypt.gpx", points_df1, "yes")

    points_df = pd.concat( [ points_df, points_df1 ], ignore_index = True )

points_df.insert(0, "total_idx", points_df.index)
# points_df.apply(lambda col: col.map(lambda x: str(x).replace('.', ','))).to_csv( "points after fix ( " + str( len( points_df ) ) + " ).csv", index = False, sep = ';' )

print("\033[94m=======================  TESTING AND FIXING TOTAL DATA   ==============================\033[0m")

print( "Total data points = ", len( points_df) )
points_df = gpx_testfix( points_df, "auditrepair", total = "yes" )

print("\033[33m=======================         RETEST TOTAL DATA        ==============================\033[0m")

points_df = gpx_testfix( points_df, "retest", total = "yes"  )

# points_df.apply(lambda col: col.map(lambda x: str(x).replace('.', ','))).to_csv( "after total ( " + str( len( points_df ) ) + " ).csv", index = False, sep = ';' )

if not timelapse:
    write_df2gpx(str(Path(skrypt_gpx_sub_folder) / Path(working_name).with_suffix("")).strip() + "_with_bearing.gpx", points_df, bearing = "yes")
    write_df2gpx(str(Path(temp_folder) / Path(working_name).with_suffix(".gpx")), points_df)

# TIMELAPSE

timelapse_path = Path(temp_folder) / f"{working_name}_timelapse.mp4"
timelapsegpx_path = Path(temp_folder) / f"{working_name}_timelapse.gpx"

if not timelapse_path.is_file():

    parts = timelapse_path.parts
    if jupyter_runtime:
        print( f"Timelapse video: '{ Path(parts[-2]) / parts[-1] if len( parts ) > 1 else timelapse_path }' not found")
    else:
        sys.exit( f"Timelapse video: '{ Path(parts[-2]) / parts[-1] if len( parts ) > 1 else timelapse_path }' not found" )

    if timelapsegpx_path.is_file() and not timelapse:
        #there is gpx file and no timelapse flag - stop program
        #otherwise we can make timelapse gpx because we have everything prepared
    
        parts = timelapsegpx_path.parts
        if jupyter_runtime:
            print( f"Timelapse gpx: '{ Path(parts[-2]) / parts[-1] if len( parts ) > 1 else timelapse_path }' found, and no timelapse flag: STOP ")
            print("gpx2one FINISHED")
        else:
            print( f"Timelapse gpx: '{ Path(parts[-2]) / parts[-1] if len( parts ) > 1 else timelapse_path }' found, and no timelapse flag: STOP" )
            sys.exit("gpx2one FINISHED")

# we have merged gpx data, have timelapse video file, and there is timelapse mode or no timelapse gpx file

cmd = [
    'ffprobe', '-v', 'error', 
    '-show_entries', 'format=duration', 
    '-of', 'json', f'"{os.path.normpath(str(timelapse_path))}"'
]

try:
    result = subprocess.run(" ".join(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, shell=True)
    data = json.loads(result.stdout)
    timelapse_duration = float(data['format']['duration'])
    print(" Timelapse duration is:", timelapse_duration )
    
except (KeyError, ValueError, subprocess.CalledProcessError) as e:
    print(f"[ERROR] ffprobe failed to read timelapse duration: {e}")

total_duration_seconds = float( points_df.groupby('file')['mp4_duration'].max().sum() )
print( "total_duration_seconds =", total_duration_seconds )

timelapse_ratio = total_duration_seconds / timelapse_duration
print( "Timelapse ratio = ", timelapse_ratio )

correct_ratio = 1
if math.floor( total_duration_seconds ) > len( points_df ):
    correct_ratio = math.floor( total_duration_seconds ) / len( points_df )
    print( "there are missing GPS points", math.floor( total_duration_seconds ) - len( points_df ), ", will rescale by", correct_ratio )
elif math.floor( total_duration_seconds ) < len( points_df ):
    print( "there more GPS points", len( points_df ) - math.floor( total_duration_seconds )) 
elif math.floor( total_duration_seconds ) == len( points_df ):
    print( "GPS points are ideal for original file")

points_df['point_no'] = range(1, len(points_df) + 1)

slow_trace = 0.8

points_df1 = points_df.copy()
points_df1['timelapse_micro'] = slow_trace + ( correct_ratio * points_df1['point_no'] ) / timelapse_ratio

points_df1.loc[0, 'timelapse_micro'] = 0
t_start = datetime.strptime(points_df1['time'].iloc[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

seconds = (points_df1['timelapse_micro'] - points_df1['timelapse_micro'].iloc[0]).round(3)

points_df1['time_timelapse'] = (t_start + pd.to_timedelta(seconds, unit='s')).dt.strftime("%Y-%m-%dT%H:%M:%S.%f").str[:-3] + "Z"

write_df2gpx(str(Path(temp_folder) / Path(working_name).with_suffix("")).strip() + "_timelapse_compressed.gpx", points_df1, timelapse = "yes")

points_df1['ideal_sec'] = np.floor( points_df1['timelapse_micro'] )
points_df1['dist_to_sec'] = (points_df1['timelapse_micro'] - points_df1['ideal_sec']).abs()

indeksy_do_zostawienia = points_df1.groupby('ideal_sec')['dist_to_sec'].idxmin().tolist()

points_dfo = points_df1.loc[indeksy_do_zostawienia]

write_df2gpx(str(Path(temp_folder) / Path(working_name).with_suffix("")).strip() + "_timelapse.gpx", points_dfo, timelapse = "yes")