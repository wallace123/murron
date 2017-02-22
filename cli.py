""" CLI utility for setting up docker containers in navencrypt volumes """
import os
import sys
import getpass
import logging
from datetime import datetime

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
    mount_point = '/docker-%s-mount' % timestamp
    lfile = '/dmcrypt/docker-%s-loop' % timestamp
    dockerd = '/usr/bin/dockerd-%s' % timestamp
    device = utils.simple_popen(['losetup', '-f'])[0].rstrip()
    docker_lib = '/dmcrypt/lib/docker-%s' % timestamp
    docker_run = '/dmcrypt/run/docker-%s' % timestamp
    category = '@docker-%s-mount' % timestamp
    acl_rule = 'ALLOW %s * %s' % (category, dockerd)

    text = 'Variables for setup:\n\t%s\n\t%s\n\t%s\n\t%s\n\t'\
           '%s\n\t%s\n\t%s\n\t%s' % (mount_point, lfile, dockerd, device,
                                     docker_lib, docker_run, category, acl_rule)
    logging.debug(text)

    num_loops = 20
    utils.create_loop_devices(num_loops)
    text = 'Created %d loop devices' % num_loops
    logging.info(text)

    cmdlist = ['mkdir', '-p', docker_lib, docker_run]
    utils.simple_popen(cmdlist)
    text = 'Created directories:\n\t%s\n\t%s' % (docker_lib, docker_run)
    logging.info(text)

    cmdlist = ['dd', 'if=/dev/zero', 'of=%s' % lfile, 'bs=1M', 'count=2048']
    utils.simple_popen(cmdlist)
    text = 'Created file for loop device:\n\t%s' % (lfile)
    logging.info(text)

    cmdlist = ['mkdir', '-p', mount_point]
    utils.simple_popen(cmdlist)
    text = 'Created directory:\n\t%s' % mount_point
    logging.info(text)

    navlog = open('./logs/navlog.log', 'a')
        
    if navlib.nav_prepare_loop(navpass, lfile, device, mount_point, logfile=navlog):
        logging.info('Nav prepare completed')
    else:
        logging.error('Something went wrong on nav prepare command')
        sys.exit(1)

    navlog.close()


if __name__ == '__main__':
    main()
