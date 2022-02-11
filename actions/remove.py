import os
import utils
import config
import logging
import re


class Remove:
    def __init__(self, user, params):
        self.user = user

        default = {
            'php': 5.6,
        }
        if isinstance(params, dict):
            self.params = params
            for key in default:
                if key not in self.params:
                    self.params[key] = default[key]
        else:
            self.params = {
                'php': params[0] if len(params) > 0 else default['php'],
            }

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')

        logging.info('Removing user "{}"'.format(self.user))

        # Kill all user processes
        res = utils.run('ps aux | grep ' + self.user)
        if res['success']:
            ps = res['message'].split('\n')
            for row in ps:
                match = re.match('^' + self.user + '\s+(\d+)', row)
                if match:
                    utils.run('kill -9 ' + match.groups()[0])

        # Removing configs
        utils.run('rm ' + config.path['nginx'] + 'sites-enabled/' + self.user + '.conf')
        utils.run('rm ' + config.path['nginx'] + 'sites-available/' + self.user + '.conf')
        utils.run('rm ' + config.path['logrotate'] + '_' + self.user)

        # Removing crontab
        utils.run('rm /var/spool/cron/crontabs/' + self.user)

        # Removing PHP
        php = str(self.params['php'])
        utils.run('rm ' + config.path['php' + php] + self.user + '.conf')
        utils.service('php' + php, 'restart')

        # Drop database and user
        q = 'DROP DATABASE `{0}`;DROP USER {0}@localhost;'.format(self.user)
        res = utils.mysql(q)
        if not res['success']:
            logging.error(res['message'].replace('\n',''))
        else:
            logging.info('Database was successfully removed')

        # Trying to remove SSL certificate
        from actions.nginx import Nginx
        Nginx(self.user, {}).remove_cert(reload=False)

        # Restarting Nginx
        utils.service('nginx', 'reload')

        # Trying to remove user
        res = utils.run(['userdel', '-rf', self.user])
        if not res['success'] and res['code'] != 12:
            logging.error(res['message'].replace('\n', '. '))

        # User dir
        if os.path.isdir(config.path['home'] + self.user):
            utils.run('rm -rf ' + config.path['home'] + self.user)

        # Symlink from user dir
        utils.run('rm /home/' + self.user)

        # Removing jail entries
        utils.file_remove(config.path['jail'] + 'etc/passwd', '{}\:'.format(self.user))
        utils.file_remove(config.path['jail'] + 'etc/shadow', '{}\:'.format(self.user))

        utils.file_remove(config.path['jail'] + 'etc/group', '{}\:'.format(self.user))
        res = utils.run('cat /etc/group | grep jail:')
        if res['success']:
            utils.file_replace(config.path['jail'] + 'etc/group', 'jail\:', res['message'].strip())

        logging.info('Done!')
        return utils.success()
