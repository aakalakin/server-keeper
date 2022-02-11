import time
import utils
import config
import logging


class Move:
    def __init__(self, user, params):
        self.user = user
        self.params = params

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')
        if not self.params['server']:
            return utils.failure('You must specify destination server')

        # Disable site
        from actions.nginx import Nginx
        Nginx(self.user, {}).disable()

        # Create new backup
        from actions.backup import Backup
        Backup(self.user, {}).create()

        # Copy backups
        logging.info('Trying to move backups of site "{}"'.format(self.user))
        start_time = time.time()
        res = Backup.rclone('move', 'yandex-cloud:modhost/{0}/{1} yandex-cloud:modhost/{2}/{1} --delete-empty-src-dirs'
                            .format(config.server['domain'], self.user, self.params['server']))
        if not res['success']:
            Nginx(self.user, {}).enable()
            msg = res['message']
            logging.error(msg)

            return utils.failure(msg)
        else:
            logging.info('Moved backups in {} sec'.format(round(time.time() - start_time, 1)))

        from actions.remove import Remove
        Remove(self.user, self.params).process()

        return utils.success()
