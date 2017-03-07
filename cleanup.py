import os
import sys
import getpass
import json
import logging
from navlib import navlib
from pyutils import utils
from pyutils import loggerinitializer

LOG_PATH = '/var/log/murron'
CLEANUP_LOG = os.path.join(LOG_PATH, 'cleanup.log')
loggerinitializer.initialize_logger(CLEANUP_LOG)
NAV_LOG = os.path.join(LOG_PATH, 'nav_cleanup.log')

navlog = open(NAV_LOG, 'a')

passwd = navlib.set_nav_passwd()
if navlib.check_nav_passwd(passwd, navlog):
    logging.info('Nav password correct')
else:
    logging.error('Nav password incorrect, exiting')
    sys.exit(1)

files = os.listdir('.')

json_list = []
for fil in files:
    if '.json' in fil:
        json_list.append(fil)

for jsn in json_list:
    json_file = open(jsn, 'r')
    data = json.load(json_file)

    # Stop the container
    docker_cmd = data['docker'].split()
    cmdlist = [docker_cmd[0], docker_cmd[1], docker_cmd[2], 'stop', data['container']]
    utils.simple_popen(cmdlist)
    logging.info('container stopped')

    # Stop and disable the service
    utils.stop_disable_service(data['dservice'].split('.')[0])
    logging.info('service disabled')

    # Remove service
    cmdlist = ['rm', '-rf', data['dservice_path']]
    utils.simple_popen(cmdlist)
    logging.info('service removed')

    # Remove navencrypt items
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

    json_file.close()
    cmdlist = ['rm', '-rf', jsn]
    utils.simple_popen(cmdlist)
    logging.info('removed json file')


navlog.close()
