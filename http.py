from flask import Flask, Response, request
from torrent import TorrentSession
from gevent import monkey, wsgi
monkey.patch_all()

torrents = TorrentSession()
app = Flask(__name__)


@app.route("/magnet/<partial_magnet>")
def handle_magnet(partial_magnet):
    if request.query_string:
        magnet = "{}?{}".format(partial_magnet, request.query_string)
    else:
        magnet = partial_magnet

    torrent = torrents.get_torrent_from_magnet(magnet)
    reader = torrent.get_reader()
    return Response(reader.yield_all(), torrent.mimetype)

if __name__ == "__main__":
    server = wsgi.WSGIServer(('127.0.0.1', 5000), app)
    server.serve_forever()
