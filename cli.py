""" CLI utility for setting up docker containers in navencrypt volumes """
import os
import sys
import getpass
import logging

try:
    from navlib import navlib
    from pyutils import utils
    from pyutils import loggerinitializer
except ImportError:
    print 'navlib, utils, or loggerinitializer could not be imported.\n'\
          'Do git clone https://github.com/wallace123/navlib.git.\n'\
          'Do git clone https://github.com/wallace123/pyutils.git.\n'
    sys.exit(1)


loggerinitializer.initialize_logger('./logs/cli.log')


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


def main():
    """ Main function """
    pass


if __name__ == '__main__':
    main()
