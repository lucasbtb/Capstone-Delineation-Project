"""
delineation_explorer.py — Opens the Delineation Explorer: a local web page for looking at delineations.

The page (index.html, next to this script):
  - imports one or more .nii / .nii.gz delineations (button or drag and drop);
  - shows them in the 3 views (axial, coronal, sagittal), reoriented to RAS, with nucleus names;
  - ITK-SNAP-style navigation: click = shared cursor, wheel = slice, right-drag = zoom;
  - one colour per file (outline) or per nucleus (fill), nuclei 1 to 9 can be toggled one by one.
Everything happens in the browser: nothing is sent online, no file is modified.

Usage:
  python ANALYSIS/delineation_explorer/delineation_explorer.py
      -> opens the page, then "Import delineations…"
  python ANALYSIS/delineation_explorer/delineation_explorer.py PATH [PATH ...]
      -> opens the page with these files already loaded (folder = every .nii / .nii.gz inside it).
         The page is then served on 127.0.0.1 while the script runs (Ctrl+C to stop).
  e.g.: python ANALYSIS/delineation_explorer/delineation_explorer.py \\
            DATA/STAPLE/C_001_2_staple.nii.gz DATA/DELINEATION_CLEAN/C_001_2
"""

import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGE = Path(__file__).resolve().parent / "index.html"


def nifti_files(args):
    """NIfTI files named by the arguments (files or folders, searched recursively)."""
    files = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.is_file() and ".nii" in f.name)
        elif p.is_file():
            files.append(p)
        else:
            print(f"Not found, skipped: {a}")
    return files


def display_name(path):
    """Displayed name: parent folder + file (the rater folder in DELINEATION_DATA, the scan folder in DELINEATION_CLEAN)."""
    return f"{path.parent.name.strip()}/{path.name}" if path.parent.name else path.name


def serve(files):
    preload = json.dumps([{"name": display_name(f), "url": f"file/{i}"} for i, f in enumerate(files)]).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                body, ctype = PAGE.read_bytes(), "text/html; charset=utf-8"
            elif path == "/preload.json":
                body, ctype = preload, "application/json"
            elif path.startswith("/file/") and path[6:].isdigit() and int(path[6:]) < len(files):
                body, ctype = files[int(path[6:])].read_bytes(), "application/octet-stream"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)  # free port chosen by the OS
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"{len(files)} file(s) loaded at {url}  (Ctrl+C to stop)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


def main():
    if len(sys.argv) == 1:
        webbrowser.open(PAGE.as_uri())
        print(f"Page opened: {PAGE}")
        return
    files = nifti_files(sys.argv[1:])
    if not files:
        sys.exit("No .nii / .nii.gz file found.")
    serve(files)


if __name__ == "__main__":
    main()
