"""Serve the local player and resize GIF/PNG downloads on demand.

Run from the repository root: python -m tools.melee_anim.player_server
Open http://127.0.0.1:8765/player.html. No new packages are required.
"""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import threading
from urllib.parse import parse_qs, urlsplit, quote

from .downloads import DownloadCatalog, SIZES
from .render_settings import MASTER_SIZE


def make_server(root, port=8765, catalog=None):
    root = Path(root).resolve()
    catalog = DownloadCatalog(root) if catalog is None else catalog
    # Serialize exports to bound Pillow's memory use for long, large GIFs.
    lock = threading.Lock()
    # Bound waiting render/download requests as well as active work.
    slots = threading.BoundedSemaphore(4)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def list_directory(self, path):
            self.send_error(404, 'Open player.html')

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/_health':
                data = json.dumps({'service': 'melee-animation-downloads', 'sizes': SIZES,
                                   'master_size':MASTER_SIZE,
                                   'clips': len(catalog.clips), 'root': str(root)}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if url.path not in ('/export', '/prepare-export', '/rotation'):
                target = Path(self.translate_path(self.path)).resolve()
                if not target.is_relative_to(root):
                    self.send_error(403)
                    return
                return super().do_GET()
            try:
                values = parse_qs(url.query, strict_parsing=True)
                allowed = {'character', 'action', 'costume', 'cycle', 'pitch', 'yaw', 'roll', 'effects', 'power', 'center'}
                if url.path in ('/export','/prepare-export'):
                    allowed |= {'size', 'kind', 'scope', 'frame', 'view'}
                if set(values)-allowed or any(len(v) != 1 for v in values.values()):
                    raise ValueError('Unknown or repeated download option')
                options = {k: v[0] for k, v in values.items()}
                view = options.pop('view', '0')
                if view not in ('0', '1') or view == '1' and (options.get('kind', 'gif') != 'gif' or options.get('scope', 'costume') != 'costume'):
                    raise ValueError('Inline viewing requires one GIF')
                for key in ('costume', 'size', 'frame'):
                    if key in options:
                        options[key] = int(options[key])
                for key in ('pitch', 'yaw', 'roll'):
                    if key in options:
                        options[key] = float(options[key])
                options.setdefault('character', '')
                options.setdefault('action', '')
                if not slots.acquire(blocking=False):
                    self.send_error(503, 'Renderer is busy; retry after the current render completes')
                    return
                try:
                    with lock:
                        if url.path == '/rotation':
                            data = json.dumps(catalog.preview(**options)).encode()
                        else:
                            target, filename, mime = catalog.export(**options)
                            if url.path=='/prepare-export':
                                data=json.dumps({'url':'/'+quote(target.resolve().relative_to(root).as_posix()),'filename':filename}).encode()
                finally:
                    slots.release()
            except (ValueError, TypeError) as error:
                self.send_error(400, str(error))
                return
            except Exception as error:
                self.log_error('Export failed: %s', error)
                self.send_error(500, 'Export failed; see the player service log')
                return
            if url.path in ('/rotation','/prepare-export'):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Disposition', f'{"inline" if view == "1" else "attachment"}; filename="{filename}"')
            self.send_header('Content-Length', str(target.stat().st_size))
            self.end_headers()
            try:
                with target.open('rb') as source:
                    shutil.copyfileobj(source, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                pass

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('build/melee_anim/preview'))
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.root, args.port)
    print(f'Player: http://127.0.0.1:{server.server_port}/player.html', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
