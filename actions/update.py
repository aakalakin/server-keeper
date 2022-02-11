import logging
import config
import utils


class Update:
    def __init__(self, user, params):
        self.user = user

        default = {
            'system': '',
            'version': ''
        }
        if isinstance(params, dict):
            self.params = params
            for key in default:
                if key not in self.params:
                    self.params[key] = default[key]
        else:
            self.params = {
                'system': params[0] if len(params) > 0 else default['system'],
                'version': params[1] if len(params) > 1 else default['version']
            }

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')

        # Check user
        res = utils.run('id ' + self.user)
        if res['success'] is not True:
            return utils.failure('User not found: ' + self.user)

        logging.info('Updating site "{}"'.format(self.user))

        # Download and install CMS
        if self.params['system']:
            if not self.download():
                return utils.failure('Could not retrieve CMS distribution package')
            if not self.install():
                return utils.failure('Could not install CMS')

        # Fixing permissions
        logging.info('Set permissions')
        utils.permissions(config.path['home'] + self.user, self.user)

        logging.info('Done!')
        return utils.success()

    def download(self):
        download_link = self.params['download_link'] if 'download_link' in self.params else ''
        file = utils.download(self.params['system'], self.params['version'], download_link)
        if file:
            logging.info('{} package retrieved'.format(self.params['system']))
            src = utils.extract(file, config.path['tmp'] + self.params['system'] + '/')
            dst = config.path['home'] + self.user + '/'
            if src:
                logging.info('{} package unzipped'.format(self.params['system']))
                try:
                    utils.move_dir(src, dst + 'www/')
                except Exception as e:
                    logging.error('Failed to move {0} files: {1}'.format(self.params['system'], str(e)))
                    return False

                utils.run('rm -rf ' + src)
                logging.info('{0} files moved to {1}www/'.format(self.params['system'], dst))
                return True
        else:
            logging.error('Could not retrieve {} distribution package'.format(self.params['system']))
        return False

    def install(self):
        system = str(self.params['system']).lower()
        if system == 'modx' or system == 'modx_revo':
            site_config = utils.get_site_config(config.path['home'] + self.user)
            # Clear cache
            utils.run('rm -rf ' + site_config['core_path'] + 'cache/*')
            if site_config['core_path'] != '{0}/www/core/'.format(config.path['user_home'] + self.user):
                utils.run('cp -fr {0}/www/core/* {1}'.format(
                    config.path['user_home'] + self.user, site_config['core_path']
                ))
                utils.run('rm -rf {0}/www/core'.format(config.path['home'] + self.user))
            res = utils.run('php {0}/www/setup/index.php --installmode=upgrade --config={0}/config.xml \
                --core_path={1}'.format(
                config.path['home'] + self.user, site_config['core_path'])
            )
            logging.info(res['message'].replace('\n', ''))

            # Set permissions
            utils.permissions(config.path['home'] + self.user, self.user)

            utils.run('rm -rf {0}{1}/www/setup'.format(config.path['home'], self.user))
            return res['success']
        elif system == 'pma':
            cfg = config.path['home'] + self.user + '/www/config.inc.php'
            utils.run('mv {0}/www/config.sample.inc.php {1}'.format(config.path['home'] + self.user, cfg))

            tmp = utils.password(50)
            utils.file_replace(cfg, "\$cfg\['blowfish_secret'\] = '';", "$cfg['blowfish_secret'] = '{0}';".format(tmp))
            utils.file_replace(cfg, "\$cfg\['Servers'\]\[\$i\]\['host'\]", "$cfg['Servers'][$i]['host'] = '127.0.0.1';")
            utils.file_add(cfg, "$cfg['PmaNoRelation_DisableWarning'] = true;")

            utils.run('rm -rf {0}/www/setup {0}/www/examples {0}/www/doc'.format(config.path['home'] + self.user))
            pass
        elif system == '':
            logging.info('No CMS specified - skip installation')
        else:
            logging.info('Skip installation of unknown CMS: "{}".'.format(self.params['system']))

        return True
