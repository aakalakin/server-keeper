import os
import utils
import config


class Logs:
    def __init__(self, user, params):
        self.user = user

        default = {
            'type': 'error',
            'lines': 100,
        }
        if isinstance(params, dict):
            self.params = params
            for key in default:
                if key not in self.params:
                    self.params[key] = default[key]
        else:
            self.params = {
                'type': params[0] if len(params) > 0 else default['type'],
                'lines': params[1] if len(params) > 1 else default['lines'],
            }

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')

        file = '{0}{1}/log/{2}.log'.format(config.path['home'], self.user, self.params['type'])
        file1 = file + '.1'
        if os.path.exists(file1):
            res = utils.run('tail -q -n {0} {2} {1}'.format(self.params['lines'], file, file1))
        else:
            res = utils.run('tail -q -n {0} {1}'.format(self.params['lines'], file))

        if res['success'] is False:
            return utils.success(data='')
        else:
            return utils.success(data=res['message'])
