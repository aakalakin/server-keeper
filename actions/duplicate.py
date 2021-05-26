import time
import utils
import config
import logging


class Duplicate:
    def __init__(self, user, params):
        self.user = user
        self.params = params

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')
        if not self.params['new_user']:
            return utils.failure('You must specify destination user')

        # Create new backup
        from actions.backup import Backup
        Backup(self.user, {'command': 'create'}).process()

        # Copy backups
        logging.info('Trying to copy backups of site "{0}" to "{1}"'.format(self.user, self.params['new_user']))
        start_time = time.time()

        if not self.params['server']:
            res = Backup.rclone('sync', 'yandex-cloud:modhost/{0}/{1} yandex-cloud:modhost/{0}/{2}'
                                .format(config.server['domain'], self.user, self.params['new_user']))
        else:
            res = Backup.rclone('sync', 'yandex-cloud:modhost/{0}/{1} yandex-cloud:modhost/{2}/{3}'
                                .format(config.server['domain'], self.user, self.params['server'],
                                        self.params['new_user']))

        if not res['success']:
            msg = res['message']
            logging.error(msg)

            return utils.failure(msg)
        else:
            logging.info('Copied backups in {} sec'.format(round(time.time() - start_time, 1)))

        return utils.success()
