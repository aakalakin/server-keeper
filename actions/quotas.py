import utils
import re
import config


class Quotas:
    def __init__(self, user, params=''):
        self.user = user

    def process(self):
        response = utils.run('repquota /')
        if not response['success']:
            return utils.failure(response['message'])

        quotas = {}
        db = self.get_db()
        strings = response['message'].split('\n')
        for string in strings:
            if re.match(self.user + '\s', string):
                tmp = re.findall(r'\S+', string)
                count = len(tmp)
                quotas[tmp[0]] = {
                    'hdd': {
                        'used': int(tmp[2]),
                        'max': int(tmp[4]),
                        # 'soft': tmp[3],
                        # 'hard': tmp[4],
                    },
                    'files': {
                        'used': int(tmp[5]) if count == 8 else int(tmp[6]),
                        'max': int(tmp[7]) if count == 8 else int(tmp[8]),
                        # 'soft': tmp[6],
                        # 'hard': tmp[7],
                    },
                    }
                if tmp[0] in db:
                    quotas[tmp[0]]['db'] = int(round(float(db[tmp[0]]), 0))
                else:
                    quotas[tmp[0]]['db'] = 0
        quotas['hdd_use'] = self.get_hdd_use()

        return utils.success(data=quotas)

    def get_db(self):
        response = utils.run('mysql -uroot -sN -e "SELECT table_schema, SUM(data_length + index_length) / 1024 '
                             'FROM information_schema.TABLES GROUP BY table_schema"')

        if not response['success']:
            return utils.failure(response['message'])

        data = {}
        strings = response['message'].split('\n')
        for string in strings:
            if re.match(self.user + '\s', string):
                tmp = re.findall(r'\S+', string)
                data[tmp[0]] = tmp[1]

        return data

    @staticmethod
    def get_hdd_use():
        hdd_use = '0%'
        response = utils.run('df | grep /dev')
        strings = response['message'].split('\n')
        for string in strings:
            dict = re.split('\s+', string)
            if len(dict) == 6 and dict[5] == '/':
                hdd_use = dict[4]

        return hdd_use.replace('%', '')
