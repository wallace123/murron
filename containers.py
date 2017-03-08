""" Module which contains container classes """

import sys
import logging
import netifaces  # Need to pip install netifaces

# Import submodules
# pylint: disable=W0403
from pyutils import utils
from navlib import navlib

# Globals
BRIDGE_IPS = ['172.18.1.1', '172.18.2.1', '172.18.3.1', '172.18.4.1',
              '172.18.5.1', '172.18.6.1', '172.18.7.1', '172.18.8.1']

# pylint: disable=R0902
class ContainerBase(object):
    """ Base class for docker nav containers """
    def __init__(self, rand_int, navpass, navlogfile=sys.stdout):
        self.rand_int = rand_int
        self.navpass = navpass
        self.docker_lib = self.create_lib()
        self.docker_run = self.create_run()
        self.loop_file = self.create_loop()
        self.mount = self.create_mount()
        self.dockerd = self.create_dockerd()
        self.bridge = self.create_bridge()
        self.docker_service_full_path = self.create_dservice()
        self.docker_service_name = self.get_dservice_name()
        self.docker = '/usr/bin/docker -H unix://%s/docker.sock' % self.docker_lib
        self.navlogfile = navlogfile

        # Navencrypt setup
        self.device, self.category = self.run_nav()

    def create_lib(self):
        """ Creates the docker lib directory """
        lib = '/dmcrypt/lib/docker-%s' % self.rand_int
        cmdlist = ['mkdir', '-p', lib]
        utils.simple_popen(cmdlist)

        text = 'Created directory: %s' % lib
        logging.info(text)

        return lib

    def create_run(self):
        """ Creates the docker run directory """
        run = '/dmcrypt/run/docker-%s' % self.rand_int
        cmdlist = ['mkdir', '-p', run]
        utils.simple_popen(cmdlist)

        text = 'Created directory: %s' % run
        logging.info(text)

        return run

    def create_loop(self):
        """ Creates the 2G loop file for navencrypt prepare """
        loop_file = '/dmcrypt/docker-%s-loop' % self.rand_int
        cmdlist = ['dd', 'if=/dev/zero', 'of=%s' % loop_file, 'bs=1M', 'count=2048']
        utils.simple_popen(cmdlist)

        text = 'Created loop file: %s' % loop_file
        logging.info(text)

        return loop_file

    def create_mount(self):
        """ Creates the mount point for navencrypt prepare """
        mount_point = '/docker-%s-mount' % self.rand_int
        cmdlist = ['mkdir', '-p', mount_point]
        utils.simple_popen(cmdlist)

        text = 'Created directory: %s' % mount_point
        logging.info(text)

        return mount_point

    def create_dockerd(self):
        """ Creates a copy of the dockerd binary """
        dockerd = '/usr/bin/dockerd-%s' % self.rand_int
        cmdlist = ['cp', '/usr/bin/dockerd', dockerd]
        utils.simple_popen(cmdlist)

        text = 'Created binary: %s' % dockerd
        logging.info(text)

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
                break

        # Create the bridge with the available IP
        docker_bridge = 'docker%d' % self.rand_int

        cmdlist = ['brctl', 'addbr', docker_bridge]
        utils.simple_popen(cmdlist)

        cmdlist = ['ip', 'addr', 'add', '%s/24' % bridge_ip, 'dev', docker_bridge]
        utils.simple_popen(cmdlist)

        cmdlist = ['ip', 'link', 'set', 'dev', docker_bridge, 'up']
        utils.simple_popen(cmdlist)

        text = 'Created bridge %s with ip %s' % (docker_bridge, bridge_ip)
        logging.info(text)

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

        text = 'Created docker service file: %s' % new_docker_service
        logging.info(text)

        return new_docker_service

    def get_dservice_name(self):
        """ Get the service name for starting and stopping service """
        return self.docker_service_full_path.split('/')[5].split('.')[0]

    def run_nav(self):
        """ Sets up navencrypt items """
        device = utils.simple_popen(['losetup', '-f'])[0].rstrip()

        if navlib.nav_prepare_loop(self.navpass, self.loop_file, device, self.mount,
                                   self.navlogfile):
            logging.info('Nav prepare completed')
        else:
            logging.error('Something went wrong on nav prepare command')
            sys.exit(1)

        category = '@%s' % self.mount.split('/')[1]

        if navlib.nav_encrypt(self.navpass, category, self.docker_lib, self.mount,
                              self.navlogfile):
            text = 'Nav encrypt of %s complete' % self.docker_lib
            logging.info(text)
        else:
            logging.error('Something went wrong with the nav move command')
            sys.exit(1)

        if navlib.nav_encrypt(self.navpass, category, self.docker_run, self.mount,
                              self.navlogfile):
            text = 'Nav encrypt of %s complete' % self.docker_run
            logging.info(text)
        else:
            logging.error('Something went wrong with the nav move command')
            sys.exit(1)

        acl_rule = 'ALLOW %s * %s' % (category, self.dockerd)

        if navlib.nav_acl_add(self.navpass, acl_rule, self.navlogfile):
            text = 'Nav acl rule added %s' % acl_rule
            logging.info(text)
        else:
            logging.error('Something went wrong with adding the acl rule')
            sys.exit(1)

        return device, category


class DockerVNC(ContainerBase):
    """ Class for wallace123/docker-vnc containers """
    def __init__(self, rand_int, navpass, navlogfile, vncpass):
        ContainerBase.__init__(self, rand_int, navpass, navlogfile)
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


class DockerJabber(ContainerBase):
    """ Class for wallace123/docker-jabber containers """
    # pylint: disable=R0913
    def __init__(self, rand_int, navpass, navlogfile,
                 jabber_ip, user1, pass1, user2, pass2):
        ContainerBase.__init__(self, rand_int, navpass, navlogfile)
        self.jabber_ip = jabber_ip
        self.user1 = user1
        self.pass1 = pass1
        self.user2 = user2
        self.pass2 = pass2

    def run(self):
        """ Starts the container, returns the port it started on """
        # Start the container
        docker_cmd = '%s run -d -p 5222 --name docker-jabber -e JHOST=%s -e USER1=%s '\
                     '-e PASS1=%s -e USER2=%s -e PASS2=%s '\
                     'wallace123/docker-jabber' % (self.docker, self.jabber_ip,
                                                   self.user1, self.pass1,
                                                   self.user2, self.pass2)

        cmdlist = docker_cmd.split()
        utils.simple_popen(cmdlist)

        # Get the port
        docker_cmd = '%s port docker-jabber' % self.docker
        cmdlist = docker_cmd.split()
        # pylint: disable=W0612
        output, errors = utils.simple_popen(cmdlist)

        port_output = output.split(':')
        port = port_output[1].rstrip()

        return port
