import libtorrent as lt
import tempfile
from os import path
from gevent import sleep
import mimetypes
import urlparse
import re
from storage import LimitedHandle
from log import get_logger
log = get_logger(__name__)


class TorrentSession(object):
    torrents_by_hash = {}

    def __init__(self):
        self.default_params = {
            # 'save_path': tempfile.gettempdir(),
            'save_path': 'tmp',
            'allocation': lt.storage_mode_t.storage_mode_sparse
        }

        self.session = getattr(lt, 'session')()
        self.session.set_download_rate_limit(50000)
        self.session.listen_on(6881, 6891)
        self.session.start_dht()
        log.info("Started DHT")

    def get_torrent_from_magnet(self, magnet):
        log.info("Starting magnet: {}".format(magnet))
        hash = get_hash(magnet)
        if hash in self.torrents_by_hash:
            log.info("Found cached")
            return self.torrents_by_hash[hash]
        torrent = _Torrent(self.session, magnet, self.default_params)
        self.torrents_by_hash[magnet] = torrent
        return torrent


class _Torrent(object):
    filename = None

    def __init__(self, session, magnet, params):
        self.handle = lt.add_magnet_uri(session, str(magnet), params)

    def set_streaming(self):
        self.handle.set_sequential_download(True)
        pieces = dict(enumerate(self.handle.status().pieces))
        next_pieces = [key for key, val in pieces.iteritems() if val][:3]
        for piece in next_pieces:
            self.handle.piece_priority(piece, 7)

    def downloaded(self):
        pieces = self.handle.status().pieces
        torrent_info = self.handle.get_torrent_info()

        sequential_bytes = 0
        for i, piece in enumerate(pieces):
            if not piece:
                break
            sequential_bytes += torrent_info.piece_size(i)

        return sequential_bytes

    def wait_for_metadata(self):
        while not self.handle.has_metadata():
            log.info("Waiting for metadata...")
            sleep(1)

    def get_reader(self):
        self.wait_for_metadata()

        if not self.filename:
            media_filename, self.mimetype = self.get_media_file()
            if not media_filename:
                return None

            self.filename = path.join(tempfile.gettempdir(), media_filename)

        self.set_streaming()

        return LimitedHandle(self.downloaded, self.filename)

    def get_media_file(self):
        torrent_info = self.handle.get_torrent_info()
        reserved_words = ['sample']

        for torrent_file_info in torrent_info.files():
            torrent_file = torrent_file_info.path
            for reserved in reserved_words:
                if reserved in torrent_file:
                    continue

            mime = mimetypes.guess_type(torrent_file)
            if not mime[0] or 'video' not in mime[0]:
                continue

            return torrent_file, mime[0]


def get_hash(magnet_):
    """
        return readable hash
    """
    magnet_p = urlparse.parse_qs(urlparse.urlparse(magnet_).query)
    return re.match('urn:btih:(.*)', magnet_p['xt'][0]).group(1)

if __name__ == '__main__':
    torrents = TorrentSession()

    magnet = "magnet:?xt=urn:btih:565DB305A27FFB321FCC7B064AFD7BD73AEDDA2B&dn=bbb_sunflower_1080p_60fps_normal.mp4&tr=udp%3a%2f%2ftracker.openbittorrent.com%3a80%2fannounce&tr=udp%3a%2f%2ftracker.publicbt.com%3a80%2fannounce&ws=http%3a%2f%2fdistribution.bbb3d.renderfarming.net%2fvideo%2fmp4%2fbbb_sunflower_1080p_60fps_normal.mp4"

    torrent = torrents.get_torrent_from_magnet(magnet)
    reader = torrent.get_reader()

    for chunk in reader.yield_all(chunk_size=10000):
        log.info("Downloaded: {} bytes".format(len(chunk)))