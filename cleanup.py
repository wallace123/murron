import os
import sys
import getpass
import pickle
import logging
from navlib import navlib
from pyutils import utils
from pyutils import loggerinitializer

LOG_PATH = '/var/log/murron'
CLEANUP_LOG = os.path.join(LOG_PATH, 'cleanup.log')
loggerinitializer.initialize_logger(CLEANUP_LOG)
NAV_LOG = os.path.join(LOG_PATH, 'nav_cleanup.log')

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


passwd = set_nav_passwd()
files = os.listdir('.')

pkl_list = []
for fil in files:
    if '.pkl' in fil:
        pkl_list.append(fil)

for pkl in pkl_list:
    pkl_file = open(pkl, 'rb')
    data = pickle.load(pkl_file)

    # Stop the container
    docker_cmd = data['docker'].split()
    cmdlist = [docker_cmd[0], docker_cmd[1], docker_cmd[2], 'stop', data['container']]
    utils.simple_popen(cmdlist)
    logging.info('container stopped')

    # Stop and disable the service
    utils.stop_disable_service(data['dservice'].split('.')[0])
    logging.info('service disabled')

    # Remove service
    cmdlist = ['rm', '-rf', '/usr/lib/systemd/system/%s' % data['dservice']]
    utils.simple_popen(cmdlist)
    logging.info('service removed')

    # Remove navencrypt items
    navlog = open(NAV_LOG, 'a')
    if navlib.nav_prepare_loop_del(passwd, data['device'], logfile=navlog):
        logging.info('navencrypt prepare -f succeeded')
    else:
        logging.error('navencrypt prepare -f failed')
        sys.exit(1)

    if navlib.nav_acl_del(passwd, data['category'], logfile=navlog):
        logging.info('acl removed')
    else:
        logging.error('acl remove failed')
        sys.exit(1)

    navlog.close()

    # Remove docker items
    cmdlist = ['rm', '-rf', data['docker_lib']]
    utils.simple_popen(cmdlist)
    logging.info('docker_lib removed')

    cmdlist = ['rm', '-rf', data['docker_run']]
    utils.simple_popen(cmdlist)
    logging.info('docker_run removed')

    cmdlist = ['rm', '-rf', data['mount_point']]
    utils.simple_popen(cmdlist)
    logging.info('mount_point removed')

    cmdlist = ['rm', '-rf', data['loop_file']]
    utils.simple_popen(cmdlist)
    logging.info('loop_file removed')

    cmdlist = ['rm', '-rf', data['dockerd']]
    utils.simple_popen(cmdlist)
    logging.info('dockerd removed')

    cmdlist = ['ip', 'link', 'set', data['docker_bridge'], 'down']
    utils.simple_popen(cmdlist)
    logging.info('bridge down')

    cmdlist = ['brctl', 'delbr', data['docker_bridge']]
    utils.simple_popen(cmdlist)
    logging.info('bridge deleted')

    utils.remove_firewall(data['port'])
    logging.info('Port removed')

    pkl_file.close()
    cmdlist = ['rm', '-rf', pkl]
    utils.simple_popen(cmdlist)
    logging.info('removed pkl file')
