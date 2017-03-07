""" Module which contains container classes """

import netifaces  # Need to pip install netifaces

# Import submodules
# pylint: disable=W0403
from pyutils import utils

# Globals
BRIDGE_IPS = ['172.18.1.1', '172.18.2.1', '172.18.3.1', '172.18.4.1',
              '172.18.5.1', '172.18.6.1', '172.18.7.1', '172.18.8.1']

# pylint: disable=R0902
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
        self.docker_service_full_path = self.create_dservice()
        self.docker_service_name = self.get_dservice_name()
        self.docker = '/usr/bin/docker -H unix://%s/docker.sock' % self.docker_lib

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

    def create_dservice(self):
        """ Copies /usr/lib/systemd/system/docker.service
            and modifies for new dockerd """
        # Copy docker service file to new docker service file
        docker_service = '/usr/lib/systemd/system/docker.service'
        new_docker_service = '/usr/lib/systemd/system/docker%s.service' % self.rand_int
        cmdlist = ['cp', docker_service, new_docker_service]
        utils.simple_popen(cmdlist)

        # Modify new docker service file
        dockerd_cmd = 'ExecStart=%s '\
                      '-D --bridge=%s '\
                      '--exec-root=%s '\
                      '-g %s '\
                      '-H unix://%s/docker.sock '\
                      '-p %s/docker.pid '\
                      '--storage-driver=devicemapper '\
                      '--iptables=false --ip-masq=false' % (self.dockerd, self.bridge,
                                                            self.docker_run, self.docker_lib,
                                                            self.docker_lib, self.docker_run)

        old = 'ExecStart=/usr/bin/dockerd'
        new = dockerd_cmd
        utils.change_file(new_docker_service, old, new)

        return new_docker_service

    def get_dservice_name(self):
        """ Get the service name for starting and stopping service """
        return self.docker_service_full_path.split('/')[5].split('.')[0]


class DockerVNC(ContainerBase):
    """ Class for wallace123/docker-vnc containers """
    def __init__(self, rand_int, vncpass):
        ContainerBase.__init__(self, self.rand_int)
        self.vncpass = vncpass

    def run(self):
        """ Starts the container, returns the port it started on """
        # Start the container
        docker_cmd = '%s run -d -p 5900 --name docker-vnc '\
                     '-e VNCPASS=%s '\
                     '-v /etc/hosts:/etc/hosts:ro '\
                     '-v /etc/resolv.conf:/etc/resolv.conf:ro '\
                     'wallace123/docker-vnc' % (self.docker, self.vncpass)

        cmdlist = docker_cmd.split()
        utils.simple_popen(cmdlist)

        # Get the port
        docker_cmd = '%s port docker-vnc' % self.docker
        cmdlist = docker_cmd.split()
        # pylint: disable=W0612
        output, errors = utils.simple_popen(cmdlist)

        port_output = output.split(':')
        port = port_output[1].rstrip()

        return port