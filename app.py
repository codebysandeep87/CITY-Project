# app.py
import streamlit as st
import os
import glob
import time
import shutil
import threading
from queue import Queue, Empty
import subprocess
import sys

# Ensure yt-dlp is available; if not, offer an in-app installer and stop.
try:
    from yt_dlp import YoutubeDL
except Exception:
    st.error("The 'yt-dlp' package is not installed in this Python environment.")
    if st.button("Install yt-dlp into this environment"):
        with st.spinner("Installing yt-dlp..."):
            proc = subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp"], capture_output=True, text=True)
            if proc.returncode == 0:
                st.success("yt-dlp installed. Please reload the app.")
            else:
                st.error(f"Installation failed:\n{proc.stderr}")
    st.stop()

# Ensure download folder exists (use absolute path based on this file)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

st.set_page_config(page_title="YouTube Downloader", layout="centered")
st.title("YouTube Video/Audio Downloader (Streamlit)")

st.write("Paste a YouTube URL, choose format, then click **Download**. "
         "Only download videos you have rights to.")

url = st.text_input("YouTube video URL")
choice = st.selectbox("Format", options=["best (video+audio)", "mp4 (video)", "mp3 (audio only)"])
filename_placeholder = st.empty()
progress_placeholder = st.empty()

def find_latest_file_with_title(title):
    # search downloads folder for files that contain title in name
    pattern = os.path.join(DOWNLOAD_DIR, f"*{sanitize_filename(title)}*")
    files = glob.glob(pattern)
    if not files:
        return None
    # return most recently modified
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def sanitize_filename(name):
    # very small sanitizer to avoid problematic chars for glob matching
    return "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).rstrip()


def adjust_opts_for_ffmpeg(opts, choice):
    """If ffmpeg is not available, adjust yt-dlp options to avoid merge/convert steps.

    - For combined video+audio formats, fall back to a single-file `best` format.
    - For mp3 conversion, skip the postprocessor so raw audio is downloaded.
    """
    has_ffmpeg = shutil.which("ffmpeg") is not None
    if has_ffmpeg:
        return opts

    # No ffmpeg: adjust based on user's choice
    if choice in ("best (video+audio)", "mp4 (video)"):
        st.warning("ffmpeg not found — will download a single-file 'best' format instead of merging.")
        new_opts = opts.copy()
        new_opts["format"] = "best"
        new_opts.pop("postprocessors", None)
        return new_opts

    if choice == "mp3 (audio only)":
        st.warning("ffmpeg not found — mp3 conversion skipped; raw audio file will be downloaded.")
        new_opts = opts.copy()
        new_opts.pop("postprocessors", None)
        return new_opts

    return opts

def download_with_hook(url, opts, events_q: Queue = None, result_q: Queue = None):
    # progress hook closure that pushes events to a queue (thread-safe)
    def progress_hook(d):
        if events_q is not None:
            events_q.put(d)
        else:
            # fallback to previous direct UI updates (rare)
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                if total:
                    pct = downloaded / total * 100
                    progress_placeholder.progress(min(int(pct), 100))
                    filename_placeholder.text(f"Downloading... {d.get('filename','')}\n{int(pct)}%")
                else:
                    filename_placeholder.text(f"Downloading... {d.get('filename','')}")
            elif status == "finished":
                progress_placeholder.progress(100)
                filename_placeholder.text("Download finished. Finalizing...")
            elif status == "error":
                filename_placeholder.text("Error during download.")

    opts["progress_hooks"] = [progress_hook]

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        if result_q is not None:
            result_q.put({"status": "finished", "info": info})
        return info
    except Exception as e:
        if result_q is not None:
            result_q.put({"status": "error", "error": str(e)})
        return None

if st.button("Download"):
    if not url.strip():
        st.error("Please paste a YouTube URL.")
    else:
        progress_placeholder.empty()
        filename_placeholder.empty()
        # set options depending on choice
        if choice == "best (video+audio)":
            ydl_opts = {
                "format": "bestvideo+bestaudio/best",
                "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
            }
        elif choice == "mp4 (video)":
            ydl_opts = {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
                "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
            }
        else:  # mp3
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }

        # ensure filenames are safe and adapt options if ffmpeg missing
        ydl_opts["restrictfilenames"] = True
        ydl_opts = adjust_opts_for_ffmpeg(ydl_opts, choice)

        # start background download using queues for progress and result
        events_q = Queue()
        result_q = Queue()
        download_thread = threading.Thread(target=download_with_hook, args=(url, ydl_opts, events_q, result_q), daemon=True)
        download_thread.start()

        st.info("Download started in background...")

        # poll for progress events while the background thread runs
        while download_thread.is_alive() or not result_q.empty():
            try:
                # drain events queue
                while True:
                    ev = events_q.get_nowait()
                    status = ev.get("status")
                    if status == "downloading":
                        total = ev.get("total_bytes") or ev.get("total_bytes_estimate")
                        downloaded = ev.get("downloaded_bytes", 0)
                        if total:
                            pct = int(min(downloaded / total * 100, 100))
                            progress_placeholder.progress(pct)
                            filename_placeholder.text(f"Downloading... {ev.get('filename','')}\n{pct}%")
                        else:
                            filename_placeholder.text(f"Downloading... {ev.get('filename','')}")
                    elif status == "finished":
                        progress_placeholder.progress(100)
                        filename_placeholder.text("Download finished. Finalizing...")
                    elif status == "error":
                        filename_placeholder.text("Error during download.")
            except Empty:
                pass
            time.sleep(0.1)

        # get final result
        result = None
        try:
            result = result_q.get_nowait()
        except Empty:
            result = None

        if result is None:
            st.error("Download failed or was interrupted.")
            st.stop()

        if result.get("status") == "error":
            st.error(f"Download failed: {result.get('error')}")
            st.stop()

        info = result.get("info")
        st.success("Download completed — searching for downloaded file...")
        # try to find the most recent file in downloads (with some retry for postprocessing)
        time.sleep(0.5)
        # extract basic info to find filename (safer to glob by title)
        try:
            # re-run a small info extraction without downloading to get title
            with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            title = info.get("title", "")
        except Exception:
            title = ""

        # try to compute expected filename from returned info
        downloaded_file = None
        try:
            with YoutubeDL({"outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"), "quiet": True}) as ydl:
                expected = ydl.prepare_filename(info)
            if expected and os.path.exists(expected):
                downloaded_file = expected
        except Exception:
            downloaded_file = None

        # fallback: find by title (fallback to most recent file if title empty)
        if not downloaded_file and title:
            downloaded_file = find_latest_file_with_title(title)
        if not downloaded_file:
            files = glob.glob(os.path.join(DOWNLOAD_DIR, "*"))
            if files:
                files.sort(key=os.path.getmtime, reverse=True)
                downloaded_file = files[0]

        if downloaded_file and os.path.exists(downloaded_file):
            st.write(f"**Saved file:** `{os.path.basename(downloaded_file)}`")
            # show file size
            st.write(f"Size: {round(os.path.getsize(downloaded_file) / (1024*1024), 2)} MB")
            # present download button to user
            with open(downloaded_file, "rb") as f:
                st.download_button("Download file to your computer", data=f, file_name=os.path.basename(downloaded_file))
        else:
            st.error("Could not find the downloaded file. Check the downloads folder.")
