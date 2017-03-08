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
def setup_vnc(rand_int, navpass, navlog, data_dict):
    """ Does the setup and starting of the VNC container """
    vncpass = data_dict['vncpass']

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


def setup_jabber(rand_int, navpass, navlog, data_dict):
    """ Does the setup and starting of Jabber container """
    jabber_ip = data_dict['jabber_ip']
    user1 = data_dict['user1']
    pass1 = data_dict['pass1']
    user2 = data_dict['user2']
    pass2 = data_dict['pass2']

    logging.info('Initializing DockerJabber instance')
    jabber = containers.DockerJabber(rand_int, navpass, navlog, jabber_ip,
                                     user1, pass1, user2, pass2)

    logging.info('Starting dockerd')
    utils.start_enable_service(jabber.docker_service_name)
    sleep(5) # Wait for dockerd to start

    logging.info('Starting jabber container')
    port = jabber.run()
    text = 'Jabber Container started on port: %s' % str(port)
    logging.info(text)

    logging.info('Opening firewall port')
    utils.set_firewall(port)

    data = {'container': 'docker-jabber', 'docker': jabber.docker,
            'dservice': jabber.docker_service_name, 'device': jabber.device,
            'docker_lib': jabber.docker_lib, 'docker_run': jabber.docker_run,
            'mount_point': jabber.mount, 'dockerd': jabber.dockerd,
            'docker_bridge': jabber.bridge, 'category': jabber.category,
            'port': port, 'loop_file': jabber.loop_file,
            'dservice_path': jabber.docker_service_full_path}

    return json.dumps(data)


def cleanup(passwd, navlog, data_dict):
    """ Receives a json dictionary and cleans up items """
    docker_cmd = data_dict['docker'].split()
    cmdlist = [docker_cmd[0], docker_cmd[1], docker_cmd[2], 'stop', data_dict['container']]
    utils.simple_popen(cmdlist)
    logging.info('container stopped')

    # Stop and disable the service
    utils.stop_disable_service(data_dict['dservice'].split('.')[0])
    logging.info('service disabled')

    # Remove service
    cmdlist = ['rm', '-rf', data_dict['dservice_path']]
    utils.simple_popen(cmdlist)
    logging.info('service removed')

    # Remove navencrypt items
    if navlib.nav_prepare_loop_del(passwd, data_dict['device'], logfile=navlog):
        logging.info('navencrypt prepare -f succeeded')
    else:
        logging.error('navencrypt prepare -f failed. Need to inspect manually')

    if navlib.nav_acl_del(passwd, data_dict['category'], logfile=navlog):
        logging.info('acl removed')
    else:
        logging.error('acl remove failed. Need to remove manually')

    # Remove docker items
    cmdlist = ['rm', '-rf', data_dict['docker_lib']]
    utils.simple_popen(cmdlist)
    logging.info('docker_lib removed')

    cmdlist = ['rm', '-rf', data_dict['docker_run']]
    utils.simple_popen(cmdlist)
    logging.info('docker_run removed')

    cmdlist = ['rm', '-rf', data_dict['mount_point']]
    utils.simple_popen(cmdlist)
    logging.info('mount_point removed')

    cmdlist = ['rm', '-rf', data_dict['loop_file']]
    utils.simple_popen(cmdlist)
    logging.info('loop_file removed')

    cmdlist = ['rm', '-rf', data_dict['dockerd']]
    utils.simple_popen(cmdlist)
    logging.info('dockerd removed')

    cmdlist = ['ip', 'link', 'set', data_dict['docker_bridge'], 'down']
    utils.simple_popen(cmdlist)
    logging.info('bridge down')

    cmdlist = ['brctl', 'delbr', data_dict['docker_bridge']]
    utils.simple_popen(cmdlist)
    logging.info('bridge deleted')

    utils.remove_firewall(data_dict['port'])
    logging.info('Port removed')

    return 'Cleanup complete'


# Handler and Server classes
class TCPHandler(SocketServer.BaseRequestHandler):
    """ Handles the creation of the docker daemon and container """

    def handle(self):
        """ Override default handler """
        data = self.request.recv(1024)
        recv_dict = json.loads(data)

        text = '%s wrote: %s' % (self.client_address[0], recv_dict)
        logging.info(text)

        if recv_dict['action'] == 'start':
            if recv_dict['image'] == 'wallace123/docker-vnc':
                logging.info('Starting VNC image')
                response = setup_vnc(recv_dict['rand_int'], self.server.navpass,
                                     self.server.navlog, recv_dict)
            elif recv_dict['image'] == 'wallace123/docker-jabber':
                logging.info('Starting Jabber image')
                response = setup_jabber(recv_dict['rand_int'], self.server.navpass,
                                        self.server.navlog, recv_dict)
            else:
                logging.error('Did not receive supported image')
        elif recv_dict['action'] == 'stop':
            logging.info('Starting cleanup actions')
            response = cleanup(self.server.navpass, self.server.navlog, recv_dict)
        else:
            logging.error('Did not receive supported action')
            response = 'Did not receive support action'

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
