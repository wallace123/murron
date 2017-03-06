""" Module which contains container classes """

import netifaces  # Need to pip install netifaces

# Import submodules
# pylint: disable=W0403
from pyutils import utils

# Globals
BRIDGE_IPS = ['172.18.1.1', '172.18.2.1', '172.18.3.1', '172.18.4.1',
              '172.18.5.1', '172.18.6.1', '172.18.7.1', '172.18.8.1']

class ContainerBase(object):
    """ Base class for docker nav containers """
    def __init__(self, rand_int):
        self.rand_int = rand_int
        self.docker_lib = self.create_lib()
        self.docker_run = self.create_run()
        self.loop_file = self.create_loop()
        self.mount = self.create_mount()
        self.dockerd = self.create_dockerd()
        self.bridge = self.create_bridge()

    def create_lib(self):
        """ Creates the docker lib directory """
        lib = '/dmcrypt/lib/docker-%s' % self.rand_int
        cmdlist = ['mkdir', '-p', lib]
        utils.simple_popen(cmdlist)

        return lib

    def create_run(self):
        """ Creates the docker run directory """
        run = '/dmcrypt/run/docker-%s' % self.rand_int
        cmdlist = ['mkdir', '-p', run]
        utils.simple_popen(cmdlist)

        return run

    def create_loop(self):
        """ Creates the 2G loop file for navencrypt prepare """
        loop_file = '/dmcrypt/docker-%s-loop' % self.rand_int
        cmdlist = ['dd', 'if=/dev/zero', 'of=%s' % loop_file, 'bs=1M', 'count=2048']
        utils.simple_popen(cmdlist)

        return loop_file

    def create_mount(self):
        """ Creates the mount point for navencrypt prepare """
        mount_point = '/docker-%s-mount' % self.rand_int
        cmdlist = ['mkdir', '-p', mount_point]
        utils.simple_popen(cmdlist)

        return mount_point

    def create_dockerd(self):
        """ Creates a copy of the dockerd binary """
        dockerd = '/usr/bin/dockerd-%s' % self.rand_int
        cmdlist = ['cp', '/usr/bin/dockerd', dockerd]
        utils.simple_popen(cmdlist)

        return dockerd

    def create_bridge(self):
        """ Creates a bridge for the docker daemon """
        # First get an available IP
        cmdlist = ['cat', '/proc/net/dev']
        # pylint: disable=W0612
        output, errors = utils.simple_popen(cmdlist)

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
                bridge_ip = avail_ip

        # Create the bridge with the available IP
        docker_bridge = 'docker%d' % self.rand_int

        cmdlist = ['brctl', 'addbr', docker_bridge]
        utils.simple_popen(cmdlist)

        cmdlist = ['ip', 'addr', 'add', '%s/24' % bridge_ip, 'dev', docker_bridge]
        utils.simple_popen(cmdlist)

        cmdlist = ['ip', 'link', 'set', 'dev', docker_bridge, 'up']
        utils.simple_popen(cmdlist)

        return docker_bridge
