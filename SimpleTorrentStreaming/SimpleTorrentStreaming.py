#!/usr/bin/env python

"""
    Simple torrent streaming module
"""

from concurrent.futures import ThreadPoolExecutor
from . utils import *
import libtorrent as lt
import subprocess
import threading
import tempfile
import argparse
import logging
import time


logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] (%(threadName)-10s) %(message)s'
)


class TorrentStreamer(object):
    """
        Torrent Streaming service
    """
    def __init__(self):
        """
            Start session listening on default ports 6881, 6891
            Holds common session magnets between threads with
            the following format and defaults:

            ::

                self.threaded_magnets[magnet_hash] = {
                    'thread': thread_,
                    'status': None,
                    'file': None,
                    'share_ratio': 0,
                    'play_ratio': 5
                }

        """
        self.default_params = {
            'save_path': tempfile.gettempdir(),
            'allocation': lt.storage_mode_t.storage_mode_sparse
        }

        self.session = getattr(lt, 'session')()
        self.session.listen_on(6881, 6891)
        self.session.start_dht()

        self.threaded_magnets = {}

    def get_blocking_magnet(self, magnet_, params=False, player="mplayer"):
        """
            Start downloading a magnet link

            :param dict magnet_: magnet
            :param dict params: Params to pass to libtorrent's add_magnet_uri
            :param string player: Player (defaults to mplayer)
        """

        if not params:
            params = self.default_params

        magnet = self.threaded_magnets[get_hash(magnet_)]
        magnet['handle'] = lt.add_magnet_uri(self.session, str(magnet_), params)

        has_played = False
        magnet['run'] = True

        while magnet['run']:
            if magnet['share_ratio'] != -1:
                logging.debug("Streaming enabled, reordering pieces")
                set_streaming_priorities(magnet['handle'])

            if magnet['handle'].has_metadata():
                logging.debug("Metadata adquired")

                if has_played and stream_conditions_met(magnet):
                    logging.debug("File has been played and streamed.")
                    magnet['run'] = False

                if not magnet['file']:
                    logging.debug("Not file yet adquired")
                    magnet['file'] = '/tmp/{}'.format(get_media_files(magnet))
                    continue

                magnet['status'] = make_status_readable(magnet)
                magnet['download_status'] = make_download_status(magnet)

                logging.debug(magnet)

                if play_conditions_met(magnet):
                    logging.debug("Launching mplayer")
                    subprocess.check_call([player, magnet['file']])
                    has_played = True
                    continue
                else:
                    logging.debug("Not yet ready to play")

            time.sleep(5)


    def get_parallel_magnets(self, magnets, share_ratio, play_ratio, player):
        """
            Parallelize magnet downloading.

            :param list magnets: list of magnets to download.
            :param int share_ratio: Seed ratio before finishing. If -1 no seed.
            :param int play_ratio: Download ratio before start playing.
                                   If -1 don't play. If 0 play once finished.
            :param str player: Player
        """
        for magnet_ in magnets:
            logging.info("Adding {} to download queue".format(magnet_))
            thread_ = threading.Thread(
                name="Downloading {}".format(get_hash(magnet_)),
                target=self.get_blocking_magnet,
                args=[str(magnet_)],
                kwargs={'player': player}
            )

            self.threaded_magnets[get_hash(magnet_)] = {
                'thread': thread_,
                'status': None,
                'file': None,
                'share_ratio': 0,
                'play_ratio': 5
            }

        with ThreadPoolExecutor(max_workers=4) as executor:
            for _, thread_ in self.threaded_magnets.items():
                executor.submit(thread_['thread'].run)

        return True


def main():
    """
        Play a torrent.
    """
    parser = argparse.ArgumentParser("stream_torrent")
    parser.add_argument('magnet', metavar='magnet', type=str, nargs='+',
                        help='Magnet link to stream')
    args = parser.parse_args()
    TorrentStreamer().get_parallel_magnets(args.magnet, -1, 5, "mplayer")

if __name__ == "__main__":
    main()
