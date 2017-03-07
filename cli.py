""" CLI utility for setting up docker containers in navencrypt volumes """
import os
import sys
import getpass
import logging
import json
from time import sleep

# Import submodules
# pylint: disable=W0403
import containers
from navlib import navlib
from pyutils import utils, loggerinitializer


# Globals
LOG_PATH = '/var/log/murron'
try:
    os.mkdir(LOG_PATH)
except OSError:
    # Dir already exists
    pass
CLI_LOG = os.path.join(LOG_PATH, 'cli.log')
loggerinitializer.initialize_logger(CLI_LOG)
NAV_LOG = os.path.join(LOG_PATH, 'nav.log')
IMAGES = ['wallace123/docker-vnc', 'wallace123/docker-jabber']


def set_nav_passwd():
    """ Prompts user for Nav Admin password to be used
        during nav commands. Optionally, can read from
        environment variable to speed up deployments for
        automated testing.
    """
    try:
        passwd = os.environ['NAVPASS']
        logging.info('Using environ password')
    except KeyError:
        passwd = getpass.getpass('Enter Navencrypt Admin password: ')
        ver_passwd = getpass.getpass('Verify password: ')

        if passwd != ver_passwd:
            logging.error('Passwords do not match. Exiting...')
            sys.exit(1)
        else:
            logging.info('Passwords match')

    navlog = open(NAV_LOG, 'a')
    if navlib.check_nav_password(passwd, logfile=navlog):
        logging.info('Password check succeeded')
        navlog.close()
        return passwd
    else:
        logging.error('Password typed is not the navencrypt password')
        sys.exit(1)


def set_vnc_passwd():
    """ Prompts user for VNC password to be used to VNC in """
    max_trys = 3
    trys = 0

    while trys < max_trys:
        passwd = getpass.getpass('Enter VNC password you want to set: ')
        ver_passwd = getpass.getpass('Verify VNC password: ')

        if passwd != ver_passwd:
            print 'Passwords do not match. Try again.'
            trys += 1
        else:
            text = 'VNC password: %s' % passwd
            logging.debug(text)
            return passwd

    logging.error('Max trys for setting VNC password reached')
    sys.exit(1)


def set_jabber_vars():
    """ Prompts user for jabber items """
    jabber_ip = raw_input("Enter the IP address of the jabber server: ")
    user1 = raw_input("Enter the username for user1: ")
    pass1 = getpass.getpass("Enter the password for user1: ")
    user2 = raw_input("Enter the username for user2: ")
    pass2 = getpass.getpass("Enter the password for user2: ")

    return jabber_ip, user1, pass1, user2, pass2


# pylint: disable=R0913
# pylint: disable=R0914
def start_jabber(docker, jabber_ip, user1, pass1, user2, pass2, rand_int):
    """ Starts up the jabber server """
    image = 'wallace123/docker-jabber'
    container = 'docker-jabber-%s' % rand_int
    docker_cmd = '%s run -d -p 5222 --name %s -e JHOST=%s -e USER1=%s '\
                 '-e PASS1=%s -e USER2=%s -e PASS2=%s %s' % (docker, container, jabber_ip,
                                                             user1, pass1, user2, pass2,
                                                             image)
    cmdlist = docker_cmd.split()
    logging.info('Starting docker-jabber image')
    output, errors = utils.simple_popen(cmdlist)
    text = 'Docker command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)

    docker_cmd = '%s port docker-jabber-%s' % (docker, rand_int)
    cmdlist = docker_cmd.split()
    output, errors = utils.simple_popen(cmdlist)
    text = 'Docker command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)
    port_output = output.split(':')
    port = port_output[1].rstrip()
    text = 'VNC port: %s' % port
    logging.info(text)

    return container, port


# pylint: disable=R0914
# pylint: disable=R0915
def main():
    """ Main function """
    logging.debug('='*25)
    print 'Enter the number of the docker image you want to spin up.\n'
    print 'Available docker images:'
    num_images = len(IMAGES)
    for pos in range(num_images):
        print '\t%d:\t%s' % (pos+1, IMAGES[pos])

    selection = raw_input('Enter image number: ')

    if selection.isdigit() and int(selection) != 0:
        if int(selection) <= num_images:
            image = IMAGES[int(selection) - 1]
            print 'Image selected: %s' % image
            text = 'User selected %s' % image
            logging.debug(text)

    logging.info('Running prereqs')
    navpass = set_nav_passwd()

    num_loops = 20
    utils.create_loop_devices(num_loops)
    text = 'Created %d loop devices' % num_loops
    logging.info(text)

    logging.info('Setting firewall to masquerade on public zone')
    utils.set_masquerade()

    logging.info('Prereqs complete')

    rand_int = utils.rand_n_digits(9)

    if image == 'wallace123/docker-vnc':
        vncpass = set_vnc_passwd()
        logging.info('Initializing DockerVNC instance')
        vnc = containers.DockerVNC(rand_int, navpass, vncpass)
        logging.info('Starting dockerd')
        utils.start_enable_service(vnc.docker_service_name)
        sleep(5) # Wait for dockerd to start
        logging.info('Starting VNC container')
        port = vnc.run()
        text = 'VNC container started on port: %s' % str(port)
        logging.info(text)
        utils.set_firewall(port)
        json_file = vnc.docker_service_name + '_cleanup.json'
        data = {'container': 'docker-vnc', 'docker': vnc.docker,
                'dservice': vnc.docker_service_name, 'device': vnc.device,
                'docker_lib': vnc.docker_lib, 'docker_run': vnc.docker_run,
                'mount_point': vnc.mount, 'dockerd': vnc.dockerd,
                'docker_bridge': vnc.bridge, 'category': vnc.category,
                'port': port, 'loop_file': vnc.loop_file,
                'dservice_path': vnc.docker_service_full_path}
    elif image == 'wallace123/docker-jabber':
        pass
        #jabber_ip, user1, pass1, user2, pass2 = set_jabber_vars()
        #container, port = start_jabber(docker, jabber_ip, user1, pass1, user2, pass2, rand_int)
        #utils.set_firewall(port)
    else:
        logging.error('Unsupported image')

    # Set up dictionary for pickling so we can delete it with cleanup.py
    output = open(json_file, 'wb')
    json.dump(data, output)
    output.close()

if __name__ == '__main__':
    main()
