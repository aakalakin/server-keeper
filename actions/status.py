import utils
import re
import config
import os
import time


class Status:
    def __init__(self, user, params=''):
        self.user = user

    def process(self):
        cpu = self.get_cpu()
        if cpu is False:
            return utils.failure("Could not get number of processors")

        data = {}
        quotas = self.get_quotas()
        processes = self.get_processes()
        for i in quotas:
            if i in processes:
                data[i] = quotas[i].copy()
                data[i].update(processes[i])
                data[i]['res'] = self.get_response(i)
                data[i]['cpu'] = round(data[i]['cpu'] / cpu, 2)

        return utils.success(data=data)

    def get_quotas(self):
        from actions.quotas import Quotas

        response = Quotas(self.user, {}).process()
        if response['success'] is True:
            return response['data']
        else:
            return {}

    def get_processes(self):
        response = utils.run('ps -e -o user,pcpu,rss')
        if not response['success']:
            return utils.failure(response['message'])

        data = {}
        strings = response['message'].split('\n')
        for string in strings:
            if re.match(self.user + '\s', string):
                tmp = re.findall(r'\S+', string)
                if tmp[0] not in data:
                    data[tmp[0]] = {
                        'cpu': float(tmp[1]),
                        'mem': int(tmp[2]),
                    }
                else:
                    data[tmp[0]]['cpu'] = round(float(tmp[1]) + data[tmp[0]]['cpu'], 1)
                    data[tmp[0]]['mem'] += int(tmp[2])

        return data

    @staticmethod
    def get_response(user):
        nginx = config.path['nginx'] + 'sites-enabled/' + user + '.conf'
        host = ''
        if os.path.isfile(nginx):
            try:
                file = open(nginx, 'r')
                strings = file.read().split('\n')
                file.close()

                for string in strings:
                    search = re.search(r'.*?server_name(.*?)$', string)
                    if search:
                        host = search.group(1).strip("; ").split(' ').pop().strip()
            except Exception:
                # return utils.failure('Could not open file "{0}" for reading: {1}'.format(nginx, e))
                return -2

        if host is '':
            # return utils.failure('Could not get host')
            return -2

        url = 'http://' + host

        start = time.time()
        utils.run('wget {0} -O /dev/null --tries 1 --timeout {1} --quiet'.format(url, 5))

        return round(time.time() - start, 4)

    @staticmethod
    def get_cpu():
        response = utils.run("nproc")
        if response["success"] is True:
            return int(response["message"])
        else:
            return False

