import glob
import subprocess


def get_duration(file_path):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    try:
        return float(subprocess.check_output(cmd, text=True).strip())
    except Exception as e:
        print(f"[ERROR] Failed to read {file_path}: {e}")
        return 0.0


def main():
    files = glob.glob("*.mp4")
    if not files:
        print("No MP4 files found.")
        return

    tot_sec = sum(get_duration(f) for f in files)

    h = f"{int(tot_sec // 3600):02d}"
    m = f"{int((tot_sec % 3600) // 60):02d}"
    s = f"{int(tot_sec % 60):02d}"
    ms = f"{int((tot_sec - int(tot_sec)) * 1000):03d}"
    sec_int = int(tot_sec)
    count = len(files)

    out_file = f"mp4_{count}files_total_time_{sec_int}s_{h}h{m}m{s}s{ms}ms.txt"
    content = (
        f"Analyzed files: {count}\n"
        "Total time of all MP4 files is:\n"
        f"{sec_int}.{ms} s\n"
        f"Exactly: {h}h {m}m {s}s {ms}ms"
    )

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nAnalyzed files: {count}")
    print(f"Total time: {h}h {m}m {s}s {ms}ms")


if __name__ == "__main__":
    main()