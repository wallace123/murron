""" CLI utility for setting up docker containers in navencrypt volumes """
import os
import sys
import getpass
import logging
import pickle
from time import sleep
import netifaces  # Need to pip install netifaces


# Import submodules
# pylint: disable=W0403
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
BRIDGE_IPS = ['172.18.1.1', '172.18.2.1', '172.18.3.1', '172.18.4.1',
              '172.18.5.1', '172.18.6.1', '172.18.7.1', '172.18.8.1']


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


def create_lib_run_dirs(rand_int):
    """ Creates the lib and run dirs for docker daemon """
    lib = '/dmcrypt/lib/docker-%s' % rand_int
    run = '/dmcrypt/run/docker-%s' % rand_int
    cmdlist = ['mkdir', '-p', lib, run]
    utils.simple_popen(cmdlist)
    text = 'Created directories:\n\t%s\n\t%s' % (lib, run)
    logging.info(text)

    return lib, run


def create_loop_file(rand_int):
    """ Creates a 2G loop file for nav mounting """
    loop_file = '/dmcrypt/docker-%s-loop' % rand_int
    cmdlist = ['dd', 'if=/dev/zero', 'of=%s' % loop_file, 'bs=1M', 'count=2048']
    utils.simple_popen(cmdlist)
    text = 'Created file for loop device:\n\t%s' % (loop_file)
    logging.info(text)

    return loop_file


def create_mount_point(rand_int):
    """ Creates the mountpoint for nav mounting """
    mount_point = '/docker-%s-mount' % rand_int
    cmdlist = ['mkdir', '-p', mount_point]
    utils.simple_popen(cmdlist)
    text = 'Created directory:\n\t%s' % mount_point
    logging.info(text)

    return mount_point


def copy_dockerd(rand_int):
    """ Copies /usr/bin/dockerd to /usr/bin/dockerd-<timestamp> """
    dockerd = '/usr/bin/dockerd-%s' % rand_int
    cmdlist = ['cp', '/usr/bin/dockerd', dockerd]
    utils.simple_popen(cmdlist)
    text = 'Copied new dockerd:\n\t%s' % dockerd
    logging.info(text)

    return dockerd


def create_dockerd_service(rand_int, dockerd_cmd):
    """ Copies /usr/lib/systemd/system/docker.service and modifies for new dockerd """
    docker_service = '/usr/lib/systemd/system/docker.service'
    new_docker_service = '/usr/lib/systemd/system/docker%s.service' % rand_int
    cmdlist = ['cp', docker_service, new_docker_service]
    utils.simple_popen(cmdlist)
    text = 'Copied new docker service:\n\t%s' % new_docker_service
    logging.info(text)

    old = 'ExecStart=/usr/bin/dockerd'
    new = dockerd_cmd
    utils.change_file(new_docker_service, old, new)

    dservice_name = new_docker_service.split('/')[5]
    return dservice_name


# pylint: disable=R0913
def run_nav(navpass, loop_file, mount_point, lib, run, dockerd):
    """ Runs navencrypt commands to set up for dockerd start """
    navlog = open(NAV_LOG, 'a')

    device = utils.simple_popen(['losetup', '-f'])[0].rstrip()

    if navlib.nav_prepare_loop(navpass, loop_file, device, mount_point, logfile=navlog):
        logging.info('Nav prepare completed')
    else:
        logging.error('Something went wrong on nav prepare command')
        sys.exit(1)

    category = '@%s' % mount_point.split('/')[1]

    if navlib.nav_encrypt(navpass, category, lib, mount_point, logfile=navlog):
        text = 'Nav encrypt of %s complete' % lib
        logging.info(text)
    else:
        logging.error('Something went wrong with the nav move command')
        sys.exit(1)

    if navlib.nav_encrypt(navpass, category, run, mount_point, logfile=navlog):
        text = 'Nav encrypt of %s complete' % run
        logging.info(text)
    else:
        logging.error('Something went wrong with the nav move command')
        sys.exit(1)

    acl_rule = 'ALLOW %s * %s' % (category, dockerd)

    if navlib.nav_acl_add(navpass, acl_rule, logfile=navlog):
        text = 'Nav acl rule added %s' % acl_rule
        logging.info(text)
    else:
        logging.error('Something went wrong with adding the acl rule')
        sys.exit(1)

    navlog.close()

    return device, category


def get_avail_ip():
    """ Gets available ip for bridge set up """
    cmdlist = ['cat', '/proc/net/dev']
    output, errors = utils.simple_popen(cmdlist)
    text = 'Devices:\n\tOutput: %s\nErrors: %s' % (output, errors)
    logging.debug(text)

    tmp = output.split()
    docker_dev = []
    for item in tmp:
        if 'docker' in item:
            docker_dev.append(item.rstrip(':'))

    used_ips = []
    for dev in docker_dev:
        used_ips.append(netifaces.ifaddresses(dev)[2][0]['addr'])

    for avail_ip in BRIDGE_IPS:
        if avail_ip not in used_ips:
            return avail_ip


def set_bridge(rand_int):
    """ Sets the bridge interface for dockerd """
    avail_ip = get_avail_ip()
    docker_bridge = 'docker%d' % rand_int

    cmdlist = ['brctl', 'addbr', docker_bridge]
    output, errors = utils.simple_popen(cmdlist)
    text = 'brctl command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)

    cmdlist = ['ip', 'addr', 'add', '%s/24' % avail_ip, 'dev', docker_bridge]
    output, errors = utils.simple_popen(cmdlist)
    text = 'ip command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)

    cmdlist = ['ip', 'link', 'set', 'dev', docker_bridge, 'up']
    output, errors = utils.simple_popen(cmdlist)
    text = 'ip command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)

    text = 'Created bridge: %s' % docker_bridge
    logging.info(text)

    return docker_bridge


def start_vnc(docker, vncpass, rand_int):
    """ Starts up the docker-vnc image """
    image = 'wallace123/docker-vnc'
    container = 'docker-vnc-%s' % rand_int
    docker_cmd = '%s run -d -p 5900 --name %s -e VNCPASS=%s '\
                 '-v /etc/hosts:/etc/hosts:ro '\
                 '-v /etc/resolv.conf:/etc/resolv.conf:ro %s' % (docker, container, vncpass, image)
    cmdlist = docker_cmd.split()
    logging.info('Starting docker-vnc image')
    output, errors = utils.simple_popen(cmdlist)
    text = 'Docker command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)

    docker_cmd = '%s port docker-vnc-%s' % (docker, rand_int)
    cmdlist = docker_cmd.split()
    output, errors = utils.simple_popen(cmdlist)
    text = 'Docker command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)
    port_output = output.split(':')
    port = port_output[1].rstrip()
    text = 'VNC port: %s' % port
    logging.info(text)

    return container, port


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

    text = 'Ready to set up navencrypt volumes for %s' % image
    logging.info(text)

    rand_int = utils.rand_n_digits(9)
    mount_point = create_mount_point(rand_int)
    docker_lib, docker_run = create_lib_run_dirs(rand_int)
    loop_file = create_loop_file(rand_int)
    docker_sock = 'unix://%s/docker-%s.sock' % (docker_lib, rand_int)
    docker_pid = '%s/docker-%s.pid' % (docker_run, rand_int)
    docker_bridge = set_bridge(rand_int)
    dockerd = copy_dockerd(rand_int)
    docker = '/usr/bin/docker -H %s ' % docker_sock
    device, category = run_nav(navpass, loop_file, mount_point, docker_lib, docker_run, dockerd)
    dockerd_cmd = 'ExecStart=%s -D --bridge=%s --exec-root=%s -g %s -H %s '\
                  '-p %s --storage-driver=devicemapper --iptables=false '\
                  '--ip-masq=false' % (dockerd, docker_bridge, docker_run, docker_lib, docker_sock,
                                       docker_pid)

    logging.info('Starting docker daemon')
    dservice = create_dockerd_service(rand_int, dockerd_cmd)
    utils.start_enable_service(dservice)

    sleep(5) # Sleep so dockerd can finish starting
    logging.info('Check dockerd')

    if image == 'wallace123/docker-vnc':
        vncpass = set_vnc_passwd()
        container, port = start_vnc(docker, vncpass, rand_int)
        utils.set_firewall(port)
    elif image == 'wallace123/docker-jabber':
        jabber_ip, user1, pass1, user2, pass2 = set_jabber_vars()
        container, port = start_jabber(docker, jabber_ip, user1, pass1, user2, pass2, rand_int)
        utils.set_firewall(port)
    else:
        logging.error('Unsupported image')

    # Set up dictionary for pickling so we can delete it with cleanup.py
    pkl_file = dservice.split('.')[0] + '_cleanup.pkl'
    data = {'container': container, 'docker': docker, 'dservice': dservice,
            'device': device, 'docker_lib': docker_lib, 'docker_run': docker_run,
            'mount_point': mount_point, 'dockerd': dockerd, 'docker_bridge': docker_bridge,
            'category': category, 'port': port, 'loop_file': loop_file}

    output = open(pkl_file, 'wb')
    pickle.dump(data, output)
    output.close()

if __name__ == '__main__':
    main()
