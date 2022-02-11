#!/usr/bin/python3

import config, utils, os, subprocess, time

path = os.path.dirname(os.path.realpath(__file__))


def deploy(server, restart = True):
    print('Updating server {0}'.format(server))
    files = os.listdir(path)
    for file in files:
        if file[0] not in ['.', '_']:
            command = 'scp -r {0}/{1} {2}@{3}:/home/{2}/server-keeper/'.format(
                path, file, config.admin, server
            )
            subprocess.call(command, shell=True)

    if restart:
        print('Trying to restart Server-Keeper on {0}'.format(server))

        reload = 'ssh {0}@{1} "sudo systemctl daemon-reload"'.format(config.admin, server)
        stop = 'ssh {0}@{1} "sudo systemctl stop server-keeper"'.format(config.admin, server)
        start = 'ssh {0}@{1} "sudo systemctl start server-keeper"'.format(config.admin, server)
        status = 'ssh {0}@{1} "sudo systemctl status server-keeper"'.format(config.admin, server)

        subprocess.call(reload, shell=True)
        subprocess.call(stop, shell=True)
        time.sleep(1)
        subprocess.call(start, shell=True)
        res = subprocess.call(status, shell=True)
        if res:
            while res:
                subprocess.call(start, shell=True)
                print('...')
                time.sleep(2)
                res = subprocess.call(status, shell=True)

        print('Done!\n')


if __name__ == "__main__":
    deploy('modhost.pro', False)
    deploy('heibel1.modhost.pro')
    deploy('bez.modhost.pro')
    for i in range(2, config.servers + 1):
        server = 'h{0}.{1}'.format(i, config.host)
        deploy(server)

