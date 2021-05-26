import os
import logging
import re
import config
import utils
import math


class Resize:
    def __init__(self, user, params):
        self.user = user

        default = {
            'hdd': 1024,
            'memory_limit': 128,
            'time_limit': 30,
            'workers': 10,
            'mail': True,
            'post_max': 500,
            'upload_max': 500,
            'gc': 1
        }
        if isinstance(params, dict):
            self.params = params
            for key in default:
                if key not in self.params:
                    self.params[key] = default[key]
        else:
            self.params = {
                'hdd': params[0] if len(params) > 0 else default['hdd'],
                'memory_limit': params[1] if len(params) > 1 else default['memory_limit'],
                'time_limit': params[2] if len(params) > 2 else default['time_limit'],
                'workers': params[3] if len(params) > 3 else default['workers'],
                'mail': params[4] if len(params) > 4 else default['mail'],
                'post_max': default['post_max'],
                'upload_max': default['upload_max'],
                'gc': default['gc'],
            }

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')

        logging.info('Resizing the site of user "{}"'.format(self.user))

        # Set user quota
        quota = str(int(self.params['hdd']) * config.server['hdd_multiplier'])
        res = utils.run(['setquota', '-u', self.user, quota, quota, '0', '0', '/'])
        if not res['success']:
            logging.error(res['message'])
            # return utils.failure(res['message'])

        # Update configs
        self.configs()

        # Set permissions
        utils.permissions(config.path['home'] + self.user, self.user)

        # Remove paid packages
        if self.params['system'] and 'packages' in self.params:
            if len(self.params['packages']) > 0:
                if not self.packages():
                    logging.error('Could not remove paid packages')
                else:
                    logging.info('All paid packages was removed')

        logging.info('Done!')
        return utils.success()

    def configs(self):
        placeholders = {
            '{user}': self.user,
            '{port}': utils.get_port(self.user),
            # '{domain}': self.params['domain'],
            # '{password}': self.params['passwords']['manager'],
            # '{mysql}': self.params['passwords']['mysql'],
            # '{ssh}': self.params['passwords']['ssh'],
            '{jail}': config.path['jail'],
            '{home}': config.path['home'],
            '{user_home}': config.path['user_home'],
            '{run}': config.path['run'],
            '{log}': config.path['log'],
            '{timezone}': config.timezone,
            '{memory_limit}': self.params['memory_limit'],
            '{time_limit}': self.params['time_limit'],
            '{workers}': self.params['workers'],
            '{start_workers}': math.ceil((self.params['workers'] / 10) * 4),
            '{min_workers}': math.ceil((self.params['workers'] / 10) * 4),
            '{max_workers}': math.ceil((self.params['workers'] / 10) * 6),
            '{mail}': '/usr/sbin/sendmail -t -i' if self.params['mail'] else '/bin/false',
            '{post_max}': self.params['post_max'],
            '{upload_max}': self.params['upload_max'],
            '{gc}': self.params['gc'],
        }

        # try to enable site if need
        src = config.path['nginx'] + 'sites-available/' + self.user + '.conf'
        dst = config.path['nginx'] + 'sites-enabled/' + self.user + '.conf'
        if not os.path.isfile(src):
            msg = 'Could not find site config. Maybe it not exists?'
            logging.error(msg)

            return utils.failure(msg)
        elif not os.path.islink(dst):
            os.symlink(src, dst)
            utils.service('nginx', 'restart')
            logging.info('Site enabled')

        # Php-fpm pool
        php = utils.get_php_ver(self.user)
        file = open(config.path['php' + php] + self.user + '.conf', 'w')
        file.write(utils.template(config.path['templates'] + 'php-fpm.conf', placeholders))
        file.close()
        utils.service('php' + php, 'restart')

    def packages(self):
        system = str(self.params['system']).lower()
        if system == 'modx' or system == 'modx_revo':
            # Remove packages
            if 'packages' in self.params:
                for data in self.params['packages']:
                    params = {
                        'root': config.path['home'] + self.user + '/www/',
                        'action': 'package_remove',
                        'data': data
                    }
                    res = utils.run_php(config.path['packages'] + 'modx_revo.php', self.user, params)
                    logging.info(res['message'].replace('\n', ''))
        return True
