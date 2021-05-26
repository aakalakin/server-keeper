import utils
import config


class Php:
    def __init__(self, user, params):
        self.user = user

        default = {
            'version': 0,
        }
        if isinstance(params, dict):
            self.params = params
            for key in default:
                if key not in self.params:
                    self.params[key] = default[key]
        else:
            self.params = {
                'version': params[0] if len(params) > 0 else default['version'],
            }

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')

        new = str(self.params['version'])
        if 'php' + new not in config.commands:
            return utils.failure('You must specify correct PHP version')
        old = utils.get_php_ver(self.user)
        if config.commands['php' + old] == config.commands['php' + new]:
            return utils.success('No version changed')

        conf = self.user + '.conf'
        res = utils.run('mv {0}{2} {1}{2}'.format(config.path['php' + old], config.path['php' + new], conf))
        if res['success']:
            utils.service(config.commands['php' + old], 'restart')
            utils.service(config.commands['php' + new], 'restart')
            return utils.success()
        return utils.failure(res['message'])
