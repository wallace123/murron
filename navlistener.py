""" Listens on specified port for creating and cleaning up docker containers """

import os
import sys
import SocketServer
import json
import logging
from time import sleep

# pylint: disable=W0403
import containers
# Import submodules
from navlib import navlib
from pyutils import utils, loggerinitializer

# Globals
LOG_PATH = '/var/log/murron'
try:
    os.mkdir(LOG_PATH)
except OSError:
    # Dir already exists
    pass

LISTENER_LOG = os.path.join(LOG_PATH, 'navlistener.log')
loggerinitializer.initialize_logger(LISTENER_LOG)
NAV_LOG = os.path.join(LOG_PATH, 'nav.log')
NUM_LOOPS = 20


# Global functions
def setup_vnc(rand_int, navpass, vncpass, navlog):
    """ Does the setup and starting of the VNC container """

    logging.info('Initializing DockerVNC instance')
    vnc = containers.DockerVNC(rand_int, navpass, navlog, vncpass)

    logging.info('Starting dockerd')
    utils.start_enable_service(vnc.docker_service_name)
    sleep(5) # Wait for dockerd to start

    logging.info('Starting VNC container')
    port = vnc.run()
    text = 'VNC container started on port: %s' % str(port)
    logging.info(text)

    logging.info('Opening firewall port')
    utils.set_firewall(port)

    data = {'container': 'docker-vnc', 'docker': vnc.docker,
            'dservice': vnc.docker_service_name, 'device': vnc.device,
            'docker_lib': vnc.docker_lib, 'docker_run': vnc.docker_run,
            'mount_point': vnc.mount, 'dockerd': vnc.dockerd,
            'docker_bridge': vnc.bridge, 'category': vnc.category,
            'port': port, 'loop_file': vnc.loop_file,
            'dservice_path': vnc.docker_service_full_path}

    return json.dumps(data)


def setup_jabber():
    pass


# Handler and Server classes
class TCPHandler(SocketServer.BaseRequestHandler):
    """ Handles the creation of the docker daemon and container """

    def handle(self):
        """ Override default handler """
        data = self.request.recv(1024)
        recv_dict = json.loads(data)

        if recv_dict['action'] == 'start':
            if recv_dict['image'] == 'wallace123/docker-vnc':
                data = setup_vnc(recv_dict['rand_int'], self.server.navpass,
                                 recv_dict['vncpass'], self.server.navlog)
            elif recv_dict['image'] == 'wallace123/docker-jabber':
                setup_jabber()
            else:
                logging.error('Did not receive supported image')
        elif recv_dict['action'] == 'stop':
            pass
        else:
            logging.error('Did not receive supported action')

        text = '%s wrote: %s' % (self.client_address[0], recv_dict)
        logging.info(text)

        response = data
        self.request.send(response)


class ForkingNavServer(SocketServer.ForkingMixIn, SocketServer.TCPServer):
    """ TCP server that forks work """
    def __init__(self, server_address, RequestHandlerClass, navpass, navlog):
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
        self.navpass = navpass
        self.navlog = navlog


def main():
    """ Main function """
    # Set and check nav password
    if len(sys.argv) != 3:
        logging.error('Usage: python navlistener.py IP PORT')
        sys.exit(1)
    else:
        host = sys.argv[1]
        port = int(sys.argv[2])

    navpass = navlib.set_nav_passwd()

    navlog = open(NAV_LOG, 'w')
    if navlib.check_nav_passwd(navpass, navlog):
        logging.info('Navpass check succeeded')
    else:
        logging.error('Navpass check failed...exiting')
        sys.exit(1)

    # Run prereqs
    logging.info('Running prereqs')
    utils.create_loop_devices(NUM_LOOPS)
    text = 'Created %d loop devices' % NUM_LOOPS
    logging.info(text)

    logging.info('Setting firewall to masquerade on public zone')
    utils.set_masquerade()
    logging.info('Prereqs complete')

    # Start listener
    text = 'Starting listener on: %s:%d' % (host, port)
    logging.info(text)

    server = ForkingNavServer((host, port), TCPHandler, navpass, navlog)
    server.serve_forever()

if __name__ == '__main__':
    main()
