import os
import logging
import config
import utils
import re
import time


class Backup:
    def __init__(self, user, params):
        self.user = user

        default = {
            'command': 'status',
            'date': round(time.time()),
            'to': config.path['user']['backups'],
            'mode': '',
            'max_full': config.backup['max_full'],
        }
        if isinstance(params, dict):
            self.params = params
            for key in default:
                if key not in self.params:
                    self.params[key] = default[key]
        else:
            self.params = {
                'command': params[0] if len(params) > 0 else default['command'],
                'date': params[1] if len(params) > 1 else default['date'],
                'to': params[2] if len(params) > 2 else default['to'],
                'mode': params[3] if len(params) > 3 else default['mode'],
                'max_full': params[4] if len(params) > 4 else default['max_full'],
            }

        self.export()

    def duplicity(self, action, params=''):
        point = 's3://{0}/{1}/{2}'.format(config.backup['cloud_endpoint'], config.server['domain'], self.user)

        command = '. {0} && duplicity {1} {2} {3} --backend-retry-delay=10 --num-retries=10 ' \
            '--ssl-no-check-certificate'.format(config.path['pass'], action, point, params)
        logging.debug(command)

        return utils.run(command)

    @staticmethod
    def rclone(action, params='yandex-cloud:modhost'):
        command = 'rclone {0} {1} -q --retries 10 --config {2}'.format(action, params, config.path['templates'] +
                                                                       'rclone.conf')
        logging.debug(command)

        response = utils.run(command)
        logging.debug(response)

        return response

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')

        if self.params['command'] == 'status':
            return self.status()
        if self.params['command'] == 'verify':
            return self.verify(self.params['date'])
        if self.params['command'] == 'create':
            return self.create(self.params['mode'])
        if self.params['command'] == 'remove':
            return self.remove(self.params['max_full'])
        if self.params['command'] == 'cleanup':
            return self.cleanup()
        if self.params['command'] == 'restore':
            return self.restore(self.params['date'])
        if self.params['command'] == 'unpack':
            self.cleanup()
            return self.unpack(self.params['date'], self.params['to'])
        else:
            msg = 'Unknown command "{}", exit.'.format(self.params['command'])
            logging.error(msg)
            return utils.failure(msg)

    def status(self):
        response = self.duplicity('collection-status')
        if response['success']:
            status = []
            strings = response['message'].split('\n')
            i = 0
            for string in strings:
                if 'Chain start time' in string:
                    status.append({})
                    i += 1
                else:
                    matches = re.search(r'\s*?(Full|Incremental)\s{3,}(.*?)\s{3,}(\d+)', string)
                    if matches:
                        mode = matches.groups()[0]
                        date = self.parse_date(matches.groups()[1])
                        # volumes = matches.groups()[2]
                        status[i - 1][date] = mode
            return utils.success(data=status)
        else:
            return utils.failure(response['message'])

    def cleanup(self):
        logging.info('Trying to cleanup backups of the site "{}"'.format(self.user))
        response = self.duplicity('cleanup', config.backup['remove_options'])

        if not response['success']:
            if re.search('No backup chains found', response['message']):
                logging.info('No backup chains found, deleting empty directory')
                Backup.rclone('purge', 'yandex-cloud:modhost/{0}/{1}'.format(config.server['domain'], self.user))
                return utils.success('Empty directory deleted')
            else:
                return utils.failure(response['message'])

        return utils.success(response['message'])

    def verify(self, date=''):
        logging.info('Trying to verify backup of the site "{}"'.format(self.user))

        if date == '':
            date = round(time.time())
        if not isinstance(date, int) and not re.match(r'^\d+$', date):
            try:
                tmp = time.strptime(date, '%Y-%m-%dT%H:%M:%S%z')
                date = round(time.mktime(tmp))
            except Exception as e:
                msg = 'Wrong date: {}'.format(e)
                logging.error(msg)
                return utils.failure(msg)

        options = config.path['tmp'] + ' --time=' + str(date) + ' ' + config.backup['verify_options']
        response = self.duplicity('verify', options)
        if not response['success']:
            if re.search('No backup chains found', response['message']):
                logging.info('No backup chains found, deleting empty directory')
                Backup.rclone('purge', 'yandex-cloud:modhost/{0}/{1}'.format(config.server['domain'], self.user))
                return utils.success('Empty directory deleted')
            else:
                return utils.failure(response['message'])

        return utils.success(response['message'])

    def create(self, mode=''):
        if mode not in ['full', 'incr']:
            response = self.status()
            if not response['success']:
                msg = 'Could not get status for user "{0}": {1}'.format(self.user, response['message'])
                logging.error(msg)
                return utils.failure(msg)

            tmp = len(response['data'])
            if tmp == 0 or len(response['data'][tmp - 1]) >= config.backup['max_increments'] + 1:
                mode = 'full'
            else:
                mode = 'incr'

        logging.info('Trying to create {0} backup for the site "{1}"'.format(mode, self.user))
        # Create dump of user database
        sql = config.path['home'] + self.user + '/backup.sql.bz2'
        response = utils.run('. {0} && nice -n 0 mysqldump -uroot {1} {2} | bzip2 --stdout > {3}'
                             .format(config.path['pass'], self.user, config.backup['mysql_options'], sql))
        if not response['success']:
            msg = response['message']
            logging.error(msg)
            return utils.failure(msg)

        # Trying to backup cron jobs
        cron_jail = config.path['jail'] + 'var/spool/cron/crontabs/' + self.user
        cron_user = config.path['home'] + self.user + '/cron'
        if os.path.isfile(cron_jail):
            utils.run('cp {0} {1}'.format(cron_jail, cron_user))

        p = config.path['home'] + self.user
        exclude = [p + '/tmp', p + '/.npm', p + '/.cache', '**/node_modules']
        tmp = utils.get_site_config(config.path['home'] + self.user)
        if tmp and 'core_path' in tmp:
            exclude.append(re.sub(r'.*?' + self.user, p, tmp['core_path']) + 'cache')
        else:
            exclude.append(p + '/www/core/cache')

        mode = mode + ' ' + config.path['home'] + self.user
        options = config.backup['backup_options']
        for i in exclude:
            options += ' --exclude "{}"'.format(i)

        response = self.duplicity(mode, options)
        # Remove files
        if os.path.isfile(sql):
            os.remove(sql)
        if os.path.isfile(cron_user):
            os.remove(cron_user)
        # Check response
        if not response['success']:
            msg = response['message']
            logging.error(msg)
            return utils.failure(msg)

        data = {}
        matches = re.findall(r'^([A-z]+)\s(\d+)', response['message'], flags=re.MULTILINE)
        for i in list(matches):
            (key, value) = i
            if key in ['StartTime', 'EndTime']:
                value = self.parse_date(int(value))
            data[key] = value

        logging.info("Backup created, removing old backups")
        self.remove()
        self.cleanup()

        return utils.success(data=data)

    def restore(self, date=''):
        # TODO Implement a sync of passwords, paths and system version with hosting panel

        logging.info('Trying to restore backup of the site "{}"'.format(self.user))
        if not isinstance(date, int) and not re.match(r'^\d+$', date):
            try:
                tmp = time.strptime(date, '%Y-%m-%dT%H:%M:%S%z')
                date = round(time.mktime(tmp))
            except Exception as e:
                msg = 'Wrong date: {}'.format(e)
                logging.error(msg)
                return utils.failure(msg)

        self.cleanup()
        # Check for the existing backups
        response = self.status()
        if not response['success']:
            return response['message']
        elif len(response['data']) == 0:
            msg = 'There is no backups of the user "{}" for restore.'.format(self.user)
            logging.error(msg)
            return utils.failure(msg)

        user = config.path['home'] + self.user
        # Remove user dir
        utils.run('rm -rf {}/*'.format(user))

        # Try to restore files
        response = self.duplicity('restore', user + ' ' + config.backup['restore_options'] + ' --time=' + str(date))
        if not response['success']:
            msg = response['message']
            logging.error(msg)
            return utils.failure(msg)

        # Trying to restore database
        sql = user + '/backup.sql.bz2'
        if os.path.isfile(sql):
            response = utils.run('. {0} && export MYSQL_PWD && nice -n 0 bunzip2 {1} --stdout | mysql -uroot {2}'
                                 .format(config.path['pass'], sql, self.user))
            if not response['success']:
                msg = response['message']
                logging.error(msg)
                return utils.failure(msg)
            else:
                os.remove(sql)

        logging.info("Backup restored")

        # Trying to restore cron jobs
        cron_jail = config.path['jail'] + 'var/spool/cron/crontabs/' + self.user
        cron_user = config.path['home'] + self.user + '/cron'
        if os.path.isfile(cron_user):
            utils.run('mv {0} {1}'.format(cron_user, cron_jail))
            utils.run('chown {0}:{1} {2} && chmod 600 {2}'.format(self.user, 'crontab', cron_jail))
            utils.run('crontab -u {0} {1}'.format(self.user, cron_jail))

        # Create necessary directories
        if not os.path.isdir(user + '/tmp'):
            os.mkdir(user + '/tmp')

        # Fix permissions
        logging.info('Set permissions')
        utils.permissions(config.path['home'] + self.user, self.user)

        # Set passwords
        passwords = utils.get_site_info(config.path['home'] + self.user)
        if passwords:
            from actions.password import Password
            Password(self.user, {'passwords': passwords}).process()
        utils.service('nginx', 'restart')

        if passwords is False:
            return utils.success()
        else:
            return utils.success(data=passwords)

    def remove(self, max_full=config.backup['max_full']):
        logging.info('Leaving {0} full backups for user "{1}"'.format(max_full, self.user))
        response = self.duplicity('remove-all-but-n-full ' + str(max_full), config.backup['remove_options'])
        if not response['success']:
            return utils.failure(response['message'])

        return utils.success(response['message'])

    def unpack(self, date='', to=''):
        logging.info('Trying to unpack backup of the site "{}"'.format(self.user))

        if not isinstance(date, int) and not re.match(r'^\d+$', date):
            try:
                tmp = time.strptime(date, '%Y-%m-%dT%H:%M:%S%z')
                date = round(time.mktime(tmp))
            except Exception as e:
                msg = 'Wrong date: {}'.format(e)
                logging.error(msg)
                return utils.failure(msg)

        # Check for the existing backups
        response = self.status()
        if not response['success']:
            return response['message']
        elif len(response['data']) == 0:
            msg = 'There is no backups of the user "{}" for restore.'.format(self.user)
            logging.error(msg)
            return utils.failure(msg)

        if not os.access(to, os.W_OK):
            msg = 'Could not unpack backup of user "{}" to "{}".'.format(self.user, to)
            logging.error(msg)
            return utils.failure(msg)

        path = to + self.user + str(date)
        response = self.duplicity('restore', path + ' ' + config.backup['restore_options'] + ' --time=' + str(date))

        utils.run('chown -R root:root {0}'.format(path))
        if not response['success']:
            msg = response['message']
            logging.error(msg)
            return utils.failure(msg)
        else:
            logging.info('Ok! Now trying to zip files...')

        info = utils.get_site_info(config.path['home'] + self.user)
        if info is False:
            info = utils.get_site_info(path)
        # utils.run('rm -rf {}/etc'.format(path))
        # utils.run('rm -rf {}/config.xml'.format(path))
        # utils.run('rm -rf {}/pass.txt'.format(path))

        filename = '{0}-{1}-{2}.zip'.format(self.user, str(date), utils.password(length=6))
        file = to + filename

        response = utils.run('cd {0} && nice -n 0 zip -r {1} ./* --password="{2}" -q && cd / && rm -rf {0}'
                             .format(path, file, info['ssh']))
        if not response['success']:
            msg = 'Could not zip files in "{}": {}'.format(path, response['message'])
            logging.error(msg)
            return utils.failure(msg)
        else:
            utils.run('chown www-data:www-data {0} && chmod 0400 {0}'.format(file))
            logging.info('Done!')
            return utils.success(data={
                'filename': filename,
                'file': file,
                'user': self.user,
                'password': info['ssh']
            })

    @staticmethod
    def export():
        utils.run(
            'echo "export PASSPHRASE=\\"{0}\\"\nexport MYSQL_PWD=\\"{1}\\"\nexport AWS_ACCESS_KEY_ID=\\"{2}\\"\nexport AWS_SECRET_ACCESS_KEY=\\"{3}\\"" > {4}'
                .format(config.password['gpg'], config.password['mysql'], config.backup['cloud_id'], config.backup['cloud_key'], config.path['pass']))
        utils.run('chmod 600 ' + config.path['pass'])

    @staticmethod
    def parse_date(date):
        try:
            if isinstance(date, int):
                tmp = time.gmtime(date)
            else:
                tmp = time.strptime(date, '%a %b  %d %H:%M:%S %Y')
        except:
            return date

        return time.strftime("%Y-%m-%dT%H:%M:%S", tmp) + time.strftime('%z')
