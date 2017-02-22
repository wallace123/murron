""" CLI utility for setting up docker containers in navencrypt volumes """
import os
import sys
import getpass
import logging
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
IMAGES = ['wallace123/docker-vnc', 'wallace123/docker-whale', 'tutum/hello-world']

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

    if image == 'wallace123/docker-vnc':
        vncpass = set_vnc_passwd()

    text = 'Ready to set up navencrypt volumes for %s' % image
    print text
    logging.debug(text)

    navpass = set_nav_passwd()

    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H.%M.%S.%f')
    docker_name = 'docker-%s' % timestamp
    mount_point = '/%s-mount' % docker_name
    loop_file = '/dmcrypt/%s-loop' % docker_name
    docker_lib = '/dmcrypt/lib/%s' % docker_name
    docker_run = '/dmcrypt/run/%s' % docker_name
    docker_sock = 'unix://%s/%s.sock' % (docker_lib, docker_name)
    docker_pid = '%s/%s.pid' % (docker_run, docker_name)
    #docker_bridge = '%s-bridge' % docker_name
    docker_bridge = 'docker0'
    dockerd = '/usr/bin/dockerd-%s' % timestamp
    docker = '/usr/bin/docker -H %s ' % docker_sock
    device = utils.simple_popen(['losetup', '-f'])[0].rstrip()
    category = '@%s-mount' % docker_name
    acl_rule = 'ALLOW %s * %s' % (category, dockerd)
    dockerd_cmd = '%s --bridge=%s --exec-root=%s -g %s -H %s '\
                  '-p %s --storage-driver=devicemapper' % (dockerd, docker_bridge, docker_run,
                                                           docker_lib, docker_sock, docker_pid)

    text = 'Variables for setup:\n\t%s\n\t%s\n\t%s\n\t%s\n\t%s\n\t%s\n\t%s\n\t%s\n\t%s\n\t'\
           '%s\n\t%s\n\t%s\n\t%s\n\t%s' % (docker_name, mount_point, loop_file, docker_lib, docker_run, 
                                           docker_sock, docker_pid, docker_bridge, dockerd, docker, device,
                                           category, acl_rule, dockerd_cmd)
    logging.debug(text)

    num_loops = 20
    utils.create_loop_devices(num_loops)
    text = 'Created %d loop devices' % num_loops
    logging.info(text)

    cmdlist = ['mkdir', '-p', docker_lib, docker_run]
    utils.simple_popen(cmdlist)
    text = 'Created directories:\n\t%s\n\t%s' % (docker_lib, docker_run)
    logging.info(text)

    cmdlist = ['dd', 'if=/dev/zero', 'of=%s' % loop_file, 'bs=1M', 'count=2048']
    utils.simple_popen(cmdlist)
    text = 'Created file for loop device:\n\t%s' % (loop_file)
    logging.info(text)

    cmdlist = ['mkdir', '-p', mount_point]
    utils.simple_popen(cmdlist)
    text = 'Created directory:\n\t%s' % mount_point
    logging.info(text)

    cmdlist = ['cp', '/usr/bin/dockerd', dockerd]
    utils.simple_popen(cmdlist)
    text = 'Copied new dockerd:\n\t%s' % dockerd
    logging.info(text)

    navlog = open('./logs/navlog.log', 'a')
        
    if navlib.nav_prepare_loop(navpass, loop_file, device, mount_point, logfile=navlog):
        logging.info('Nav prepare completed')
    else:
        logging.error('Something went wrong on nav prepare command')
        sys.exit(1)

    if navlib.nav_encrypt(navpass, category, docker_lib, mount_point, logfile=navlog):
        text = 'Nav encrypt of %s complete' % docker_lib
        logging.info(text)
    else:
        logging.error('Something went wrong with the nav move command')
        sys.exit(1)

    sleep(5) # Sleep 5 seconds so move command can complete

    if navlib.nav_encrypt(navpass, category, docker_run, mount_point, logfile=navlog):
        text = 'Nav encrypt of %s complete' % docker_run
        logging.info(text)
    else:
        logging.error('Something went wrong with the nav move command')
        sys.exit(1)

    sleep(5) # Sleep 5 seconds so move command can complete

    if navlib.nav_acl_add(navpass, acl_rule, logfile=navlog):
        text = 'Nav acl rule added %s' % acl_rule
        logging.info(text)
    else:
        logging.error('Something went wrong with adding the acl rule')
        sys.exit(1)

    navlog.close()

    logging.info('Starting docker daemon')
    cmdlist = [dockerd, '&']
    output, errors = utils.simple_popen(cmdlist)
    text = '\nOutput: %s\nErrors: %s' % (output, errors) 
    logging.debug(text)

    print 'Check dockerd'


if __name__ == '__main__':
    main()
