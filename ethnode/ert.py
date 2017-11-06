import cherrypy
import os
import sys
import traceback
import config
import argparse
from kadem.kad import DHT, DHTFacade

from toolkit.tools import mkdir, on_hook
from toolkit import kadmini_codec
from toolkit import store_handler

from eth_profile import EthearnalProfileView, EthearnalProfileController
from eth_profile import EthearnalJobView, EthearnalJobPostController
from eth_profile import EthearnalUploadFileView


parser = argparse.ArgumentParser(description='Ethearnal p2p ert node')


parser.add_argument('-l', '--http_host_port',
                    default=config.http_host_port,
                    help='E,g 127.0.0.1:8080',
                    required=False,
                    type=str)

parser.add_argument('-d', '--data_dir',
                    default=config.data_dir,
                    help='Point local profile data directory',
                    required=False,
                    type=str)

parser.add_argument('-w', '--http_webdir',
                    default=config.http_webdir,
                    help='Point ui html static dir',
                    required=False,
                    type=str)

parser.add_argument('-u', '--udp_host_port',
                    default=config.udp_host_port,
                    help='E,g 127.0.0.1:3000',
                    required=False,
                    type=str)


parser.add_argument('-s', '--udp_seed_host_port',
                    default=None,
                    help='E,g 127.0.0.1:3000',
                    required=False,
                    type=str)


parser.add_argument('-i', '--interactive_shell',
                    help='embed ipython shell',
                    required=False,
                    action='store_true'
                    )

parser.add_argument('-b', '--dht_only',
                    help='only udb dht',
                    required=False,
                    action='store_true'
                    )


class EthearnalSite(object):
    @cherrypy.expose
    def index(self):
        return "ethearnal 0.0.1"
    # todo make entry point redirect to ui


def main_dht(host: str, port: int, store: store_handler.DHTStoreHandlerOne,
             guid: int =None, seed_host=None, seed_port=None):
    if seed_host and seed_port and (host, port) != (seed_host, seed_port):
        print('BOOTSTRAP TO SEED', seed_host, seed_port)
        dht = DHT(host=host, port=port, guid=guid,  seeds=[(seed_host, seed_port)],
                  storage=store)
    else:
        dht = DHT(host=host, port=port, guid=guid, storage=store)
    return dht


def tear_down_udp(dht):
    print('UDP stopping...')
    if dht:
        dht.server.shutdown()


def main_profile(http_webdir,
                 files_dir_name):

    http_webdir = os.path.abspath(http_webdir)
    files_dir = os.path.abspath('%s/%s' % (profile_dir, files_dir_name))
    if not os.path.isdir(files_dir):
        print('Creating dir for static files')
        mkdir(files_dir)
    profile_dir_abs = os.path.abspath(profile_dir)
    ert_profile_ctl = EthearnalProfileController(data_dir=profile_dir_abs, files_dir=files_dir)
    ert_profile_view = view = EthearnalProfileView(ert_profile_ctl)
    return ert_profile_ctl, ert_profile_view


def main_http(http_webdir: str = config.http_webdir,
              socket_host: str = config.http_socket_host,
              socket_port: int = config.http_socket_port,
              ert_profile_ctl: EthearnalProfileController = None,
              ert_profile_view: EthearnalProfileView = None,
              files_dir_name: str = config.static_files,
              # profile_dir: str = config.data_dir,
              interactive: bool = config.interactive,
              dht=None,
              ):

    site_conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd())
        },
        '/ui': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': http_webdir,
            'tools.staticdir.index': 'index.html',
        },
        '/ui/files': {
            'tools.staticdir.on': True,
            'tools.staticdir.root': ert_profile_ctl.files_dir,
            'tools.staticdir.dir': files_dir_name,
        }
    }
    cherrypy.server.socket_host = socket_host
    cherrypy.server.socket_port = socket_port
    # Cache-Control:public, max-age=5 # in seconds
    cherrypy.response.headers['Cache-Control'] = 'public, max-age=5'

    cherrypy.tree.mount(EthearnalSite(), '/', site_conf)
    #
    cherrypy.tree.mount(ert_profile_view,
                        '/api/v1/profile',
                        {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}}
                        )
    #
    cherrypy.tree.mount(EthearnalJobView(EthearnalJobPostController(ert_profile_ctl)),
                        '/api/v1/job', {'/': {
                            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
                            'tools.sessions.on': True,
                            'tools.response_headers.on': True,
                            'tools.response_headers.headers': [('Content-Type', 'text/plain')],
                            }
                         }
                        )

    cherrypy.tree.mount(EthearnalUploadFileView(ert_profile_ctl),
                        '/api/v1/upload', {'/': {
                            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
                            'tools.sessions.on': True,
                            'tools.response_headers.on': True,
                            'tools.response_headers.headers': [('Content-Type', 'text/plain')],
                            }
                         }
                        )

    cherrypy.engine.start()

    print('STATIC FILES DIR:', ert_profile_ctl.files_dir)
    print('WEBUI DIR:', http_webdir)
    print('PROFILE DIR:', ert_profile_ctl.data_dir)

    cherrypy.engine.exit = on_hook(target=tear_down_udp,
                                   target_args=(dht,),
                                   target_kwargs={})(cherrypy.engine.exit)

    if not interactive:
        cherrypy.engine.block()
    else:
        try:
            from IPython import embed
            embed()
        except:
            pass


if __name__ == '__main__':
    args = parser.parse_args()
    socket_host, socket_port = args.http_host_port.split(':')
    profile_dir = args.data_dir
    http_webdir = args.http_webdir
    socket_port = int(socket_port)
    udp_host, udp_port = args.udp_host_port.split(':')
    udp_port = int(udp_port)
    seed_host = None
    seed_port = None

    if args.udp_seed_host_port:
        seed_host, seed_port = args.udp_seed_host_port.split(':')
        seed_port = int(seed_port)

    if os.path.isdir(args.data_dir):
        print('Using existing profile directory: %s' % profile_dir)
    else:
        mkdir(profile_dir)

    dht = None
    d = None

    try:
        ert_profile_ctl, ert_profile_view = main_profile(
            http_webdir=http_webdir,
            files_dir_name=config.static_files
        )
        ert = ert_profile_ctl
        hex_guid, bin_guid = ert_profile_ctl.rsa_guid_hex_bin
        int_guid = kadmini_codec.guid_bts_to_int(bin_guid)
        bts_2 = kadmini_codec.guid_int_to_bts(int_guid)
        hex2_guid = kadmini_codec.guid_int_to_hex(int_guid)

        assert hex2_guid == hex_guid
        #
        storage_handle = store_handler.DHTStoreHandlerOne()
        # storage_handle = dict()

        dht = main_dht(udp_host, udp_port,
                       store=storage_handle,
                       guid=int_guid,
                       seed_host=seed_host,
                       seed_port=seed_port)
        d = DHTFacade(dht, ert_profile_ctl)
        if dht.server_thread.is_alive():
            print('UDP server thread is alive')
        else:
            print('UDP server thread id dead')

        if not args.dht_only:
            main_http(http_webdir=http_webdir,
                      socket_host=socket_host,
                      socket_port=socket_port,
                      ert_profile_ctl=ert_profile_ctl,
                      ert_profile_view=ert_profile_view,
                      dht=dht,
                      interactive=args.interactive_shell
                      )
        else:
            from IPython import embed
            embed()

    except Exception as e:
        print('MAIN ERROR')
        cherrypy.engine.stop()
        traceback.print_exc(file=sys.stdout)

