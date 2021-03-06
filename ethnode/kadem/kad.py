# import json
import bson
import random
import hashlib
# import socket
import socketserver
import threading
import time
from .bucketset import BucketSet
# from .hashing import hash_function, random_id
# from .hashing import random_id
# from toolkit.kadmini_codec import hash_function
from .peer import Peer, PeerC
# from .storage import Shelve
from .shortlist import Shortlist
# from . import hashing
from toolkit import kadmini_codec
from ert_profile import EthearnalProfileController

cdx = kadmini_codec

# k = 20
k = 20

alpha = 3

# id_bits = 128

id_bits = kadmini_codec.id_bits

iteration_sleep = 0.1

# all the things have to be bson encoded


class DHTFacade(object):
    def __init__(self, dht, ert: EthearnalProfileController):
        self.dht = dht
        self.ert = ert
        self.cdx = cdx
        self.push_pubkey(local_only=True)
        self.dht.storage.dhf = self
        self._last_pushed_hk_hex = None
        self._last_pulled_hk_hex = None
        self.cdn = None
        # self.events = None
        self.indexer = None

        # self.dht.storage

    def boot_to(self, host, port):
        self.dht.bootstrap([(host, port), ])

    def direct_push(self, key, value, host, port):
        guid = self.bin_guid
        hk = cdx.encode_key_hash(key, guid=guid, revision=cdx.DEFAULT_REVISION)
        ev = cdx.encode_val_bson(value, cdx.DEFAULT_REVISION)
        sg = self.ert.rsa_sign(ev)
        self.dht.peer.direct_store(hk, ev, host, port,
                                   socket=self.dht.server.socket,
                                   peer_id=self.dht.peer.id,
                                   signature=sg)

        self._last_pushed_hk_hex = cdx.guid_int_to_hex(hk)

    def push_peer(self, host_port, to_host, to_port):
        key = 'ert:peer'
        value = {'ert:peer': host_port}
        self.direct_push(key, value, to_host, to_port)

    @property
    def peers(self):
        return self.dht.peers()

    @property
    def ip4_peers(self):
        return self.ip4_peers_format()

    @property
    def ip4_peers_hex(self):
        return self.ip4_peers_format(hex_format=True)

    def ip4_peers_format(self, hex_format=False):
        if hex_format:
            return self.dht.buckets.host_port__host_port_hexguid
        return self.dht.buckets.host_port__host_port_binguid

    @property
    def data(self):
        return self.dht.data

    @property
    def bin_guid(self):
        return cdx.guid_int_to_bts(self.dht.peer.id)

    @staticmethod
    def calc_hk_hex(key, guid_hex, revision=1):
        guid_bin = cdx.guid_hex_to_bin(guid_hex)
        hk = cdx.encode_key_hash(key, guid=guid_bin, revision=revision)
        hk_hex = cdx.guid_int_to_hex(hk)
        return hk_hex, hk

    def push(self, key, value,
             revision=cdx.DEFAULT_REVISION,
             nearest_nodes=None, local_only=False, remote_only=False, hk_hex=None):
        guid = self.bin_guid
        # hk = cdx.encode_key_hash(key, guid=guid, revision=revision)
        ev = cdx.encode_val_bson(value, revision)
        sg = self.ert.rsa_sign(ev)

        if hk_hex:
            hk = cdx.guid_bts_to_int(cdx.guid_hex_to_bin(hk_hex))
            self._last_pulled_hk_hex = hk_hex
        else:
            hk = cdx.encode_key_hash(key, guid=guid, revision=revision)
            self._last_pulled_hk_hex = cdx.guid_int_to_hex(hk)
            # return cdx.guid_int_to_hex(hk)

        print('PUSH HK', hk)

        if not remote_only:
            self.dht.storage.push(hk, ev, sg, guid)

        if local_only:
            return

        if not nearest_nodes:
            nearest_nodes = self.dht.iterative_find_nodes(hk)
        for node in nearest_nodes:
            node.store(hk, ev,
                       socket=self.dht.server.socket,
                       peer_id=self.dht.peer.id,
                       signature=sg)
        self._last_pushed_hk_hex = cdx.guid_int_to_hex(hk)
        return hk

    def direct_push_pubkey(self, host, port):
        key = {'ert': 'pubkey'}
        value = {'ert:pubkey': self.ert.rsa_pub_der}
        self.direct_push(key, value, host, port)

    def push_pubkey(self, local_only=False):
        key = {'ert': 'pubkey'}
        value = {'ert:pubkey': self.ert.rsa_pub_der}
        self.push(key, value, local_only=local_only)

    def known_guids(self):
        c = self.dht.storage.pubkeys.cursor.execute('SELECT bkey from ertref;')
        guid_list = [cdx.guid_bin_to_hex(k[0]).decode() for k in c.fetchall()]
        return guid_list

    def push_host_port(self, host_port, local_only=False):
        key = {'ert': 'udp_ip4_port'}
        value = {'ert:udp_ip4_port': {'h:p': host_port}}
        self.push(key,  value, local_only=local_only)

    def push_peer_request(self):
        ip_host = self.dht.peer.host
        if ip_host == '0.0.0.0':
            if self.ert.my_wan_ip:
                ip_host = self.ert.my_wan_ip
            elif self.ert.my_lan_ip:
                ip_host = self.ert.my_lan_ip
            else:
                ip_host = '127.0.0.1'
        key = {'ert': 'peer'}
        val = {'ert:peer': {'h': ip_host, 'p': self.dht.peer.port}}
        print('IP', ip_host, self.dht.peer.port)
        for item in self.dht.peers():
            peer_host = item['host']
            peer_port = item['port']
            self.direct_push(key, val, peer_host, peer_port)

    def push_peer_ping(self):
        ip_host = self.dht.peer.host
        if ip_host == '0.0.0.0':
            if not self.ert.my_lan_ip:
                ip_host = '127.0.0.1'
            else:
                ip_host = self.ert.my_lan_ip
        key = {'ert': 'pong_to'}
        val = {'ert:pong_to': {'h': ip_host, 'p': self.dht.peer.port}}
        print('IP', ip_host, self.dht.peer.port)
        for item in self.dht.peers():
            peer_host = item['host']
            peer_port = item['port']
            self.direct_push(key, val, peer_host, peer_port)

    def converge_peers(self):
        from time import sleep
        self.push_pubkey()
        sleep(3)
        self.push_peer_request()
        sleep(3)
        self.pull_peer_request()
        sleep(3)

    def pull_peer_request(self):
        key = {'ert': 'peer'}
        return self.pull_remote(key)

    def pull_pubkey(self, guid=None, remote_only=False):
        key = {'ert': 'pubkey'}
        if not guid:
            guid = self.bin_guid
        val = None
        if not remote_only:
            val = self.pull_local(key, guid=guid)

        if val:
            print('LOCAL VAL PUBKEY')
        else:
            remote_val = self.pull_remote(key, guid=guid)
            if remote_val:
                print('REMOTE VAL PUBKEY')
                own, sig, val = remote_val
                rev, data = cdx.decode_bson_val(val)
                der = data['ert:pubkey']
                is_ok = cdx.verify_guid(guid, der)
                is_hash_ok = False
                if hashlib.sha256(der).digest() == guid:
                    is_hash_ok = True

                if is_ok and own == guid and is_hash_ok:
                    print('REMOTE PUBKEY OK')
                    print('STORE PUB KEY')
                    # store only reference
                    hk = cdx.encode_key_hash(key, guid=guid, revision=rev)
                    self.data.pubkeys[own] = hk
                    print('STORE IN DHT')
                    return self.data.store.__setitem__(hk, remote_val)
                else:
                    print('REMOTE PUBKEY NOT OK')

    def pull_pubkey_in_peers(self):
        for peer in self.peers:
            guid = cdx.guid_int_to_bts(peer['id'])
            self.pull_pubkey(guid)

    def pull_local(self, key,
                   guid=None,
                   revision=cdx.DEFAULT_REVISION,
                   hk_hex=None
                   ):
        if not guid:
            guid = self.bin_guid
        if hk_hex:
            hk = cdx.guid_bts_to_int(cdx.guid_hex_to_bin(hk_hex))
            self._last_pulled_hk_hex = hk_hex
        else:
            hk = cdx.encode_key_hash(key, guid=guid, revision=revision)
            self._last_pulled_hk_hex = cdx.guid_int_to_hex(hk)

        v = self.dht.data.pull(hk)

        return v

    @property
    def last_pushed_hk_hex(self):
        return self._last_pushed_hk_hex

    @property
    def last_pulled_hk_hex(self):
        return self._last_pulled_hk_hex

    def pull_remote(self, key, guid=None, revision=cdx.DEFAULT_REVISION,
                    hk_hex=None):
        if not guid:
            guid = self.bin_guid

        if hk_hex:
            hk = cdx.guid_bts_to_int(cdx.guid_hex_to_bin(hk_hex))
            self._last_pulled_hk_hex = hk_hex
        else:
            hk = cdx.encode_key_hash(key, guid, revision)
            self._last_pulled_hk_hex = cdx.guid_int_to_hex(hk)
            # return cdx.guid_int_to_hex(hk)

        val = self.dht.iterative_find_value(hk)
        if val:
            print('HAVE VAL')
            return val
        else:
            print('NO VAL')

    def get_guid_bin(self, idx):
        return cdx.guid_int_to_bts(self.peers[idx]['id'])

    def pubkey_to_peers(self, peers=None):
        if not peers:
            peers = self.peers
        for kwargs in peers:
            kwargs['socket'] = self.dht.server.socket
            kwargs['from_id'] = self.dht.identity
            node = PeerC(**kwargs)
            node.push_pubkey(pubkey_der=self.ert.rsa_pub_der)


class DHTRequestHandler(socketserver.BaseRequestHandler):
    def handle_dht(self, message, message_type):
        # todo make it in dict or something, some general protocol handler
        # that way is lame, .... whole thing have to refactored in brand new kademlia
        try:

            # handle message receive

            if message_type == "ping":
                self.handle_ping(message)
            elif message_type == "pong":
                self.handle_pong(message)
            elif message_type == "find_node":
                self.handle_find(message)
            elif message_type == "find_value":
                self.handle_find(message, find_value=True)
            elif message_type == "found_nodes":
                self.handle_found_nodes(message)
            elif message_type == "found_value":
                self.handle_found_value(message)
            elif message_type == "store":
                self.handle_store(message)

        except KeyError:
            pass
        except ValueError:
            pass
        client_host, client_port = self.client_address
        peer_id = kadmini_codec.guid_bts_to_int(message["peer_id"])
        # peer_info = message["peer_info"] # disabled in protocol
        peer_info = None
        new_peer = Peer(client_host, client_port, peer_id, peer_info)
        self.server.dht.buckets.insert(new_peer)

    def handle_ping(self, message):
        print('RCV PING', )
        client_host, client_port = self.client_address
        id = kadmini_codec.guid_bts_to_int(message["peer_id"])
        #  info = message["peer_info"] # diabled in protocol
        info = None
        peer = Peer(client_host, client_port, id, info)
        peer.pong(socket=self.server.socket, peer_id=self.server.dht.peer.id, lock=self.server.send_lock)

    def handle_pong(self, message):
        pass

    def handle_find(self, message, find_value=False):
        print('RCV FIND: ', find_value)
        key = kadmini_codec.guid_bts_to_int(message["id"])
        id = kadmini_codec.guid_bts_to_int(message["peer_id"])

        if id == key:
            print('KEY IS PEER')
            guid_owner = cdx.guid_int_to_bts(key)
            print('\n\n\n + + + ++ ++ GUID' , guid_owner)
            if guid_owner in self.server.dht.storage.pubkeys:
                print(' \n\n\n + + ++ ++ + IN PUBKEYS \n \n \n\ ')
            else:
                # todo async
                self.server.dht.storage.dhf.pull_pubkey(guid=guid_owner, remote_only=True)
                pass
                # self.server.dht
            # if guid_owner in self.pubkeys:
            #     print('HAVE PUBKEY', guid_owner)

        msg_rpc_id_int = cdx.guid_bts_to_int(message["rpc_id"])
        info = None
        client_host, client_port = self.client_address
        peer = Peer(client_host, client_port, id, info)
        response_socket = self.request[1]
        print('RCV FIND KEY', key)

        if find_value and (key in self.server.dht.data):
            bv = self.server.dht.storage.pull(key)
            print('RCV FIND VALUE')
            peer.found_value(id, bv, msg_rpc_id_int, socket=response_socket,
                             peer_id=self.server.dht.peer.id,
                             peer_info=self.server.dht.peer.info,
                             lock=self.server.send_lock)
        else:
            nearest_nodes = self.server.dht.buckets.nearest_nodes(id)
            if not nearest_nodes:
                nearest_nodes.append(self.server.dht.peer)
            nearest_nodes = [nearest_peer.astriple() for nearest_peer in nearest_nodes]

            peer.found_nodes(id, nearest_nodes, msg_rpc_id_int, socket=response_socket,
                             peer_id=self.server.dht.peer.id, peer_info=self.server.dht.peer.info,
                             lock=self.server.send_lock)

    def handle_found_nodes(self, message):
        print('RCV FOUND NODES')
        msg_rpc_id_int = cdx.guid_bts_to_int(message["rpc_id"])
        rpc_id = msg_rpc_id_int
        peer_info = None  # just for compatibility with original kad
        shortlist = self.server.dht.rpc_ids[rpc_id]
        del self.server.dht.rpc_ids[rpc_id]
        # nearest_nodes = [Peer(*peer) for peer in message["nearest_nodes"]]
        decoded_nearest_nodes = list()
        for item in message['nearest_nodes']:
            ip4, port, id_bts = item
            # print('NEAR NODE', item)
            decoded_nearest_nodes.append(Peer(ip4,
                                              port,
                                              cdx.guid_bts_to_int(id_bts),
                                              peer_info))
        shortlist.update(decoded_nearest_nodes)

    def handle_found_value(self, message):
        print('RCV FOUND VALUE')
        rpc_id = cdx.guid_bts_to_int(message["rpc_id"])
        shortlist = self.server.dht.rpc_ids[rpc_id]
        del self.server.dht.rpc_ids[rpc_id]
        shortlist.set_complete(message["value"])
        print('RCV FOUND COMPLETED')

    def handle_store(self, message):
        bts_key = message["id"]
        int_key = cdx.guid_bts_to_int(message["id"])
        bts_value = message['value']
        sig = message['signature']
        from_guid = message['peer_id']

        print('RCV STORE FROM', from_guid)
        if from_guid == self.server.dht.identity:
            print('RCV SAME GUID SKIP')
            return
        self.server.dht.storage.push(int_key, bts_value, sig, from_guid)


# handle receive of all udp msg here


class EthDHTRequestHandle(DHTRequestHandler):
    def handle(self):
        message = kadmini_codec.decode(self.request[0])
        message_type = message["message_type"]
        # todo impl logging
        print('RECV', message_type, 'LEN', len(self.request[0]))
        self.handle_dht(message, message_type)


class DHTServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    def __init__(self, host_address, handler_cls):
        socketserver.UDPServer.__init__(self, host_address, handler_cls)
        self.send_lock = threading.Lock()
        self.socketserver = socketserver


class DHT(object):
    def __init__(self, host, port,
                 guid=None, seeds=[],
                 storage=None,
                 info={},  # rm this
                 request_handler=EthDHTRequestHandle):
        if not guid:
            raise ValueError('GUID must SET from PUBLIC KEY!')

        self.storage = storage
        self.info = info
        self.hash_function = cdx.hash_function
        self.peer = Peer(host, port, guid, info)
        # self.wan_peer = Peer(host, port, guid)
        self.data = self.storage
        self.buckets = BucketSet(k, id_bits, self.peer.id)
        self.rpc_ids = {}  # should probably have a lock for this
        self.rpc_ids = {}  # omg
        self.server = DHTServer(self.peer.address(), request_handler)
        self.server.dht = self
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        self.bootstrap(seeds)
        # self.dhf = None


        # ext

    @property
    def identity(self):
        return self.peer.id

    def iterative_find_nodes(self, key, boot_peer=None):
        shortlist = Shortlist(k, key)
        shortlist.update(self.buckets.nearest_nodes(key, limit=alpha))
        if boot_peer:
            rpc_id = random.getrandbits(id_bits)
            self.rpc_ids[rpc_id] = shortlist
            boot_peer.find_node(key, rpc_id, socket=self.server.socket, peer_id=self.peer.id, peer_info=self.peer.info)
        while (not shortlist.complete()) or boot_peer:
            nearest_nodes = shortlist.get_next_iteration(alpha)
            for peer in nearest_nodes:
                shortlist.mark(peer)
                rpc_id = random.getrandbits(id_bits)
                self.rpc_ids[rpc_id] = shortlist
                peer.find_node(key, rpc_id, socket=self.server.socket, peer_id=self.peer.id,
                               peer_info=self.info)  # #####
            time.sleep(iteration_sleep)
            boot_peer = None
        return shortlist.results()

    def iterative_find_value(self, key):
        shortlist = Shortlist(k, key)
        shortlist.update(self.buckets.nearest_nodes(key, limit=alpha))
        while not shortlist.complete():
            nearest_nodes = shortlist.get_next_iteration(alpha)
            for peer in nearest_nodes:
                shortlist.mark(peer)
                rpc_id = random.getrandbits(id_bits)
                self.rpc_ids[rpc_id] = shortlist
                peer.find_value(key, rpc_id, socket=self.server.socket, peer_id=self.peer.id,
                                peer_info=self.info)  # ####
            time.sleep(iteration_sleep)
        print('COMPLETE')
        return shortlist.completion_result()

    # Return the list of connected peers
    def peers(self):
        return self.buckets.to_dict()

    # Boostrap the network with a list of bootstrap nodes
    def bootstrap(self, bootstrap_nodes=[]):
        for bnode in bootstrap_nodes:
            boot_peer = Peer(bnode[0], bnode[1], "", "")
            self.iterative_find_nodes(self.peer.id, boot_peer=boot_peer)

        if len(bootstrap_nodes) == 0:
            for bnode in self.buckets.to_list():
                self.iterative_find_nodes(self.peer.id, boot_peer=Peer(bnode[0], bnode[1], bnode[2], bnode[3]))






