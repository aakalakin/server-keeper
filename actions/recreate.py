import os
import logging
import config
import utils
import re
import shutil
import math


class Recreate:
    def __init__(self, user, params):
        self.user = user

        default = {
            'system': '',
            'version': '',
            'options': [],
            'language': 'ru',
            'charset': 'utf8mb4',
            'php': 5.6,
        }
        if isinstance(params, dict):
            self.params = params
            for key in default:
                if key not in self.params:
                    self.params[key] = default[key]
        else:
            self.params = {
                'system': params[1] if len(params) > 1 else default['system'],
                'version': params[2] if len(params) > 2 else default['version'],
                'options': params[3] if len(params) > 3 else default['options'],
                'language': params[4] if len(params) > 4 else default['language'],
                'php': params[5] if len(params) > 5 else default['php'],
                'charset': default['charset'],
            }

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')

        # Check user
        res = utils.run('id ' + self.user)
        if res['success'] is not True:
            return utils.failure('User not found: ' + self.user)

        logging.info('ReCreating site "{}"'.format(self.user))

        # ReCreate database
        q = 'DROP DATABASE `{0}`;' \
            'CREATE DATABASE `{0}` DEFAULT CHARACTER SET {1} COLLATE {1}_unicode_ci;' \
            .format(self.user, self.params['charset'])
        res = utils.mysql(q)
        if not res['success']:
            logging.error(res['message'])
            return res['message']

        # Clean site directory
        res = utils.run('rm -rf {0}/www/'.format(config.path['home'] + self.user))
        if not res['success']:
            logging.error(res['message'])
            return res['message']

        # Download and install CMS
        if self.params['system']:
            if not self.download():
                return utils.failure('Could not retrieve CMS distribution package')
            if not self.install():
                return utils.failure('Could not install CMS')

        # Fixing permissions
        if not os.path.isdir(config.path['home'] + self.user + '/www/'):
            os.mkdir(config.path['home'] + self.user + '/www/')
        logging.info('Set permissions')
        utils.permissions(config.path['home'] + self.user, self.user)

        # Change PHP version
        from actions.php import Php
        Php(self.user, {'version': self.params['php']}).process()

        logging.info('Done!')
        return utils.success()

    def download(self):
        download_link = self.params['download_link'] if 'download_link' in self.params else ''
        file = utils.download(self.params['system'], self.params['version'], download_link)
        if file:
            logging.info('CMS package retrieved')
            src = utils.extract(file, config.path['tmp'] + self.params['system'] + '/')
            dst = config.path['home'] + self.user + '/'
            if src:
                logging.info('CMS package unzipped')
                if not os.path.isdir(config.path['home']):
                    os.mkdir(config.path['home'])
                try:
                    os.renames(src, dst + 'www/')
                except Exception as e:
                    logging.error('Failed to move CMS files: ' + str(e))
                    return False

                logging.info('CMS files moved to ' + dst + 'www/')
                return True
        else:
            logging.error('Could not retrieve CMS distribution package')
        return False

    def install(self):
        system = str(self.params['system']).lower()
        if system == 'modx' or system == 'modx_revo':
            if self.params['options']:
                file = config.path['home'] + self.user + '/config.xml'
                # Language
                utils.file_replace(
                    file, '.*?<inplace>.*?</inplace>',
                    '    <inplace>0</inplace>'.format(self.params['language'])
                )
                # Language
                utils.file_replace(
                    file, '.*?<language>.*?</language>',
                    '    <language>{0}</language>'.format(self.params['language'])
                )
                # Table prefix
                if self.params['options']['prefix']:
                    utils.file_replace(
                        file, '.*?<table_prefix>.*?</table_prefix>',
                        '<table_prefix>{0}</table_prefix>'.format(self.params['options']['prefix'])
                    )
                # System core
                if self.params['options']['core']:
                    utils.file_replace(
                        file, '.*?<core_path>.*?</core_path>',
                        '    <core_path>{0}{1}/www/{2}/</core_path>'.format(
                            config.path['user_home'], self.user, self.params['options']['core']
                        )
                    )
                # Manager
                if self.params['options']['manager']:
                    utils.file_replace(
                        file, '.*?<context_mgr_path>.*?</context_mgr_path>',
                        '    <context_mgr_path>{0}{1}/www/{2}/</context_mgr_path>'.format(
                            config.path['user_home'], self.user, self.params['options']['manager']
                        )
                    )
                    utils.file_replace(
                        file, '.*?<context_mgr_url>.*?</context_mgr_url>',
                        '    <context_mgr_url>/{0}/</context_mgr_url>'.format(self.params['options']['manager'])
                    )
                # System connectors
                if self.params['options']['connectors']:
                    utils.file_replace(
                        file, '.*?<context_connectors_path>.*?</context_connectors_path>',
                        '    <context_connectors_path>{0}{1}/www/{2}/</context_connectors_path>'.format(
                            config.path['user_home'], self.user, self.params['options']['connectors']
                        )
                    )
                    utils.file_replace(
                        file, '.*?<context_connectors_url>.*?</context_connectors_url>',
                        '    <context_connectors_url>/{0}/</context_connectors_url>'.format(
                            self.params['options']['connectors']
                        )
                    )

            site_config = utils.get_site_config(config.path['home'] + self.user)
            if site_config['core_path'] != '{0}/www/core/'.format(config.path['user_home'] + self.user):
                utils.run('mv {0}/www/core {1}'.format(
                    config.path['home'] + self.user, site_config['core_path']
                ))
            res = utils.run('php {0}/www/setup/index.php --installmode=new --config={0}/config.xml \
                --core_path={1}'.format(
                config.path['user_home'] + self.user, site_config['core_path'])
            )
            logging.info(res['message'].replace('\n', ''))

            # Set permissions
            utils.permissions(config.path['home'] + self.user, self.user)

            # Install packages
            if 'packages' in self.params:
                for data in self.params['packages']:
                    params = {
                        'root': config.path['home'] + self.user + '/www/',
                        'action': 'package_download',
                        'data': data
                    }
                    res = utils.run_php(config.path['packages'] + 'modx_revo.php', self.user, params)
                    logging.info(res['message'].replace('\n', ''))

                    params['action'] = 'package_install'
                    res = utils.run_php(config.path['packages'] + 'modx_revo.php', self.user, params)
                    logging.info(res['message'].replace('\n', ''))

            utils.run('rm -rf {}packages/core'.format(site_config['core_path']))
            utils.run('rm -rf {}packages/core.transport.zip'.format(site_config['core_path']))
            return res['success']
        elif system == '':
            logging.info('No CMS specified - skip installation')
        else:
            logging.info('Skip installation of unknown CMS: "{}".'.format(self.params['system']))

        return True
