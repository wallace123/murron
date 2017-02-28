""" CLI utility for setting up docker containers in navencrypt volumes """
import os
import sys
import getpass
import logging
import subprocess
from datetime import datetime
from time import sleep

try:
    # pylint: disable=W0403
    from navlib import navlib
    from pyutils import utils
    from pyutils import loggerinitializer
except ImportError:
    print 'navlib, utils, or loggerinitializer could not be imported.\n'\
          'Do git clone https://github.com/wallace123/navlib.git.\n'\
          'Do git clone https://github.com/wallace123/pyutils.git.\n'
    sys.exit(1)

# Globals
loggerinitializer.initialize_logger('./logs/cli.log')
IMAGES = ['wallace123/docker-vnc', 'wallace123/docker-whale', 'wallace123/docker-jabber']


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

    return passwd


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
    pass1 = raw_input("Enter the password for user1: ")
    user2 = raw_input("Enter the username for user2: ")
    pass2 = raw_input("Enter the password for user2: ")

    return jabber_ip, user1, pass1, user2, pass2


def create_lib_run_dirs(timestamp):
    """ Creates the lib and run dirs for docker daemon """
    lib = '/dmcrypt/lib/docker-%s' % timestamp
    run = '/dmcrypt/run/docker-%s' % timestamp
    cmdlist = ['mkdir', '-p', lib, run]
    utils.simple_popen(cmdlist)
    text = 'Created directories:\n\t%s\n\t%s' % (lib, run)
    logging.info(text)

    return lib, run


def create_loop_file(timestamp):
    """ Creates a 2G loop file for nav mounting """
    loop_file = '/dmcrypt/docker-%s-loop' % timestamp
    cmdlist = ['dd', 'if=/dev/zero', 'of=%s' % loop_file, 'bs=1M', 'count=2048']
    utils.simple_popen(cmdlist)
    text = 'Created file for loop device:\n\t%s' % (loop_file)
    logging.info(text)

    return loop_file


def create_mount_point(timestamp):
    """ Creates the mountpoint for nav mounting """
    mount_point = '/docker-%s-mount' % timestamp
    cmdlist = ['mkdir', '-p', mount_point]
    utils.simple_popen(cmdlist)
    text = 'Created directory:\n\t%s' % mount_point
    logging.info(text)

    return mount_point


def copy_dockerd(timestamp):
    """ Copies /usr/bin/dockerd to /usr/bin/dockerd-<timestamp> """
    dockerd = '/usr/bin/dockerd-%s' % timestamp
    cmdlist = ['cp', '/usr/bin/dockerd', dockerd]
    utils.simple_popen(cmdlist)
    text = 'Copied new dockerd:\n\t%s' % dockerd
    logging.info(text)

    return dockerd


def run_nav(navpass, loop_file, mount_point, lib, run, dockerd):
    """ Runs navencrypt commands to set up for dockerd start """
    navlog = open('./logs/navlog.log', 'a')

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

    return device, acl_rule


def start_vnc(docker, vncpass):
    """ Starts up the docker-vnc image """
    image = 'wallace123/docker-vnc'
    docker_cmd = '%s run -d -p 5900 --name docker-vnc -e VNCPASS=%s -v /etc/hosts:/etc/hosts:ro '\
                 '-v /etc/resolv.conf:/etc/resolv.conf:ro %s' % (docker, vncpass, image)
    cmdlist = docker_cmd.split()
    logging.info('Starting docker-vnc image')
    output, errors = utils.simple_popen(cmdlist)
    text = 'Docker command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)

    docker_cmd = '%s port docker-vnc' % docker
    cmdlist = docker_cmd.split()
    output, errors = utils.simple_popen(cmdlist)
    text = 'Docker command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)
    port_output = output.split(':')
    port = port_output[1]
    text = 'VNC port: %s' % port
    logging.info(text)

    return port


def start_whale(docker):
    """ Starts up the docker-whale image """
    image = 'wallace123/docker-whale'
    docker_cmd = '%s run -d --name docker-whale %s' % (docker, image)
    cmdlist = docker_cmd.split()
    logging.info('Starting docker-whale image')
    output, errors = utils.simple_popen(cmdlist)
    text = 'Docker command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)

    return output


def start_jabber(docker, jabber_ip, user1, pass1, user2, pass2):
    """ Starts up the jabber server """
    image = 'wallace123/docker-jabber'
    docker_cmd = '%s run -d -p 5222 --name docker-jabber -e JHOST=%s -e USER1=%s '\
                 '-e PASS1=%s -e USER2=%s -e PASS2=%s -v /etc/hosts:/etc/hosts:ro '\
                 '-v /etc/resolv.conf:/etc/resolv.conf:ro %s' % (docker, jabber_ip,
                                                                 user1, pass1,
                                                                 user2, pass2,
                                                                 image)
    cmdlist = docker_cmd.split()
    logging.info('Starting docker-jabber image')
    output, errors = utils.simple_popen(cmdlist)
    text = 'Docker command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)

    docker_cmd = '%s port docker-vnc' % docker
    cmdlist = docker_cmd.split()
    output, errors = utils.simple_popen(cmdlist)
    text = 'Docker command:\n\tOutput: %s\n\tErrors: %s' % (output, errors)
    logging.debug(text)
    port_output = output.split(':')
    port = port_output[1]
    text = 'VNC port: %s' % port
    logging.info(text)

    return port


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

    text = 'Ready to set up navencrypt volumes for %s' % image
    logging.info(text)

    navpass = set_nav_passwd()

    num_loops = 20
    utils.create_loop_devices(num_loops)
    text = 'Created %d loop devices' % num_loops
    logging.info(text)

    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H.%M.%S.%f')
    mount_point = create_mount_point(timestamp)
    docker_lib, docker_run = create_lib_run_dirs(timestamp)
    loop_file = create_loop_file(timestamp)
    docker_sock = 'unix://%s/docker-%s.sock' % (docker_lib, timestamp)
    docker_pid = '%s/docker-%s.pid' % (docker_run, timestamp)
    docker_bridge = 'docker0'
    dockerd = copy_dockerd(timestamp)
    docker = '/usr/bin/docker -H %s ' % docker_sock
    device, acl_rule = run_nav(navpass, loop_file, mount_point, docker_lib, docker_run, dockerd)
    dockerd_cmd = 'nohup %s --bridge=%s --exec-root=%s -g %s -H %s '\
                  '-p %s --storage-driver=devicemapper' % (dockerd, docker_bridge, docker_run,
                                                           docker_lib, docker_sock, docker_pid)

    text = 'Variables for setup:\n\t%s\n\t%s\n\t%s\n\t%s\n\t%s\n\t%s\n\t%s\n\t%s\n\t%s\n\t'\
           '%s\n\t%s\n\t%s\n\t%s' % (timestamp, mount_point, loop_file, docker_lib,
                                     docker_run, docker_sock, docker_pid, docker_bridge,
                                     dockerd, docker, device, acl_rule, dockerd_cmd)
    logging.debug(text)

    logging.info('Starting docker daemon')
    cmdlist = dockerd_cmd.split()
    proc = subprocess.Popen(cmdlist,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            preexec_fn=os.setpgrp,
                           ).pid
    text = 'proc: %s' % proc
    logging.info(text)

    sleep(10) # Sleep so dockerd can finish starting
    logging.info('Check dockerd')

    if image == 'wallace123/docker-vnc':
        vncpass = set_vnc_passwd()
        start_vnc(docker, vncpass)
    elif image == 'wallace123/docker-whale':
        output = start_whale(docker)
        logging.info(output)
    elif image == 'wallace123/docker-jabber':
        jabber_ip, user1, pass1, user2, pass2 = set_jabber_vars()
        start_jabber(docker, jabber_ip, user1, pass1, user2, pass2)
    else:
        logging.error('Unsupported image')


if __name__ == '__main__':
    main()
