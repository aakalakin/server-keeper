import os
import utils
import config
import logging
import re


class Password:
    def __init__(self, user, params):
        self.user = user

        default = {
            'passwords': {},
            'options': {},
            'system': '',
        }
        if isinstance(params, dict):
            self.params = params
            for key in default:
                if key not in self.params:
                    self.params[key] = default[key]
        else:
            self.params = {
                'passwords': params[0] if len(params) > 0 else default['passwords'],
                'options': params[1] if len(params) > 1 else default['options'],
                'system': params[2] if len(params) > 2 else default['system'],
            }

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')
        elif not isinstance(self.params['passwords'], dict):
            return utils.failure('Wrong type of array with passwords')

        # Check user
        res = utils.run('id ' + self.user)
        if res['success'] is not True:
            return utils.failure('User not found: ' + self.user)

        # Check config
        placeholders = {
            '{domain}': '{0}.{1}'.format(self.user, config.server['domain']),
            '{user}': self.user,
            '{password}': self.params['passwords']['manager'] if 'manager' in self.params['passwords'] else '',
            '{mysql}': self.params['passwords']['mysql'] if 'mysql' in self.params['passwords'] else '',
            '{charset}': 'utf8mb4',
            '{prefix}': self.params['options']['prefix'] if 'prefix' in self.params['options'] else 'modx_',
            '{language}': 'ru',
            '{user_home}': config.path['user_home'],
            '{core}': self.params['passwords']['core'] if 'core' in self.params['passwords'] else 'core',
            '{manager}': self.params['passwords']['manager'] if 'manager' in self.params['passwords'] else 'manager',
            '{connectors}': self.params['passwords']['connectors'] if 'connectors' in self.params[
                'passwords'] else 'connectors',
            '{ssh}': self.params['passwords']['ssh'] if 'ssh' in self.params['passwords'] else '',
        }

        cfg = config.path['home'] + self.user + '/config.xml'
        if not os.path.exists(cfg):
            file = open(cfg, 'w')
            file.write(utils.template(config.path['templates'] + 'modx.xml', placeholders))
            file.close()
            utils.run(['chmod', '0400', cfg])
        pwd = config.path['home'] + self.user + '/pass.txt'
        if not os.path.exists(pwd):
            file = open(pwd, 'w')
            file.write(utils.template(config.path['templates'] + 'pass.txt', placeholders))
            file.close()
            utils.run(['chmod', '0400', pwd])

        # Change passwords
        if 'passwords' in self.params:
            for key in self.params['passwords']:
                res = self.password(key, self.params['passwords'][key])
                if not res['success']:
                    logging.error('Error on change "{0}" password for user {1}: "{2}"'.format(
                        key, self.user, res['message']
                    ))
                else:
                    logging.info('Changed "{0}" password for user {1}'.format(key, self.user))

        # Change paths
        if 'options' in self.params:
            for key in self.params['options']:
                res = self.option(key, self.params['options'][key])
                if not res['success']:
                    logging.error('Error on change "{0}" option for user {1}: "{2}"'.format(
                        key, self.user, res['message']
                    ))
                else:
                    logging.info('Changed "{0}" option for user {1}'.format(key, self.user))

        return utils.success()

    def password(self, key, value):
        if value == '':
            return utils.failure('Password can`t be empty')

        system = str(self.params['system']).lower()
        if key == 'ssh':
            # Set user password
            file = open(config.path['tmp'] + self.user + '.pass', 'w')
            file.write(value + '\n' + value)
            file.close()
            utils.run('cat ' + config.path['tmp'] + self.user + '.pass | passwd ' + self.user)
            os.remove(config.path['tmp'] + self.user + '.pass')

            utils.file_replace(
                config.path['home'] + self.user + '/pass.txt',
                'SSH/SFTP password',
                'SSH/SFTP password: {}'.format(value)
            )

            shadow = '{}etc/shadow'.format(config.path['jail'])
            res = utils.run('cat /etc/shadow | grep {}:'.format(self.user))
            if res['success']:
                utils.file_replace(shadow, self.user + ':', res['message'].strip())
        elif key == 'mysql':
            res = utils.mysql("SET PASSWORD FOR {0}@localhost = PASSWORD('{1}');".format(self.user, value))
            if not res['success']:
                return utils.failure(res['message'])

            if system == 'modx' or system == 'modx_revo':
                site_config = utils.get_site_config(config.path['home'] + self.user)
                utils.file_replace(
                    site_config['core_path'] + 'config/config.inc.php',
                    '\$database_password',
                    '$database_password = \'{}\';'.format(value)
                )
                utils.file_replace(
                    config.path['home'] + self.user + '/config.xml',
                    '.*?<database_password>',
                    '    <database_password>{}</database_password>'.format(value)
                )
                utils.file_replace(
                    config.path['home'] + self.user + '/pass.txt',
                    'MySQL password',
                    'MySQL password: {}'.format(value)
                )
                utils.run('rm -rf ' + site_config['core_path'] + 'cache/')
        elif key == 'manager' and (system == 'modx' or system == 'modx_revo'):
            site_config = utils.get_site_config(config.path['home'] + self.user)
            res = utils.run_php(config.path['packages'] + 'modx_revo.php', self.user, {
                'root': config.path['home'] + self.user + '/www/',
                'action': 'password_manager',
                'username': self.user,
                'password': value,
            })
            if res['message']:
                return utils.failure(res['message'])

            utils.file_replace(
                config.path['home'] + self.user + '/config.xml',
                '.*?<cmspassword>',
                '    <cmspassword>{}</cmspassword>'.format(value)
            )
            utils.run('rm -rf ' + site_config['core_path'] + 'cache/')

            utils.file_replace(
                config.path['home'] + self.user + '/pass.txt',
                'Manager password',
                'Manager password: {}'.format(value)
            )

        return utils.success()

    def option(self, key, value):
        if value == '':
            return utils.failure('Option can`t be empty')

        system = str(self.params['system']).lower()
        site_config = utils.get_site_config(config.path['home'] + self.user)
        if key == 'prefix':
            if system == 'modx' or system == 'modx_revo':
                res = utils.mysql(
                    "SELECT `TABLE_NAME` FROM information_schema.tables WHERE `table_schema` = '{}'".format(self.user)
                )
                if not res['success']:
                    return res
                tables = str(res['message']).split('\n')
                for table in tables:
                    if re.match(site_config['table_prefix'], table):
                        new_table = table.replace(site_config['table_prefix'], value, 1)
                        utils.mysql("RENAME TABLE `{0}`.`{1}` TO `{0}`.`{2}`;".format(self.user, table, new_table))
                # Change config
                utils.file_replace(
                    site_config['core_path'] + 'config/config.inc.php',
                    '\$table_prefix',
                    '$table_prefix = \'{}\';'.format(value)
                )
                utils.file_replace(
                    config.path['home'] + self.user + '/config.xml',
                    '.*?<table_prefix>',
                    '    <table_prefix>{}</table_prefix>'.format(value)
                )
                utils.run('rm -rf ' + site_config['core_path'] + 'cache/')
        elif key == 'core' and (system == 'modx' or system == 'modx_revo'):
            new = config.path['user_home'] + self.user + '/www/' + value + '/'
            if site_config['core_path'] != new:
                utils.file_replace(
                    site_config['core_path'] + 'config/config.inc.php',
                    '(\s+|\t+|)\$modx_core_path',
                    '    $modx_core_path = \'{}\';'.format(new)
                )
                utils.file_replace(
                    site_config['core_path'] + 'config/config.inc.php',
                    '(\s+|\t+|)\$modx_processors_path',
                    '    $modx_processors_path = \'{}\';'.format(new + 'model/modx/processors/')
                )
                utils.file_replace(
                    config.path['home'] + self.user + '/config.xml',
                    '(\s+|\t+|)\<core_path>',
                    '    <core_path>{}</core_path>'.format(new)
                )
                utils.file_replace(
                    site_config['context_web_path'] + 'config.core.php',
                    '(.*?|)define\(\'MODX_CORE_PATH',
                    'define(\'MODX_CORE_PATH\', \'{}\');'.format(new)
                )
                utils.run('cp -f {0}config.core.php {1}'.format(
                    site_config['context_web_path'], site_config['context_mgr_path'])
                )
                utils.run('cp -f {0}config.core.php {1}'.format(
                    site_config['context_web_path'], site_config['context_connectors_path'])
                )
                utils.run('rm -rf ' + site_config['core_path'] + 'cache/')
                utils.run('mv {0} {1}'.format(site_config['core_path'], new))
        elif key == 'connectors' and (system == 'modx' or system == 'modx_revo'):
            new = config.path['user_home'] + self.user + '/www/' + value + '/'
            utils.file_replace(
                site_config['core_path'] + 'config/config.inc.php',
                '(\s+|\t+|)\$modx_connectors_path',
                '    $modx_connectors_path = \'{}\';'.format(new)
            )
            utils.file_replace(
                site_config['core_path'] + 'config/config.inc.php',
                '(\s+|\t+|)\$modx_connectors_url',
                '    $modx_connectors_url = \'/{}/\';'.format(value)
            )
            utils.file_replace(
                config.path['home'] + self.user + '/config.xml',
                '(\s+|\t+|)\<context_connectors_path>',
                '    <context_connectors_path>{}</context_connectors_path>'.format(new)
            )
            utils.file_replace(
                config.path['home'] + self.user + '/config.xml',
                '(\s+|\t+|)\<context_connectors_url>',
                '    <context_connectors_url>/{}/</context_connectors_url>'.format(value)
            )
            utils.run('mv {0} {1}'.format(site_config['context_connectors_path'], new))
        elif key == 'manager' and (system == 'modx' or system == 'modx_revo'):
            new = config.path['user_home'] + self.user + '/www/' + value + '/'
            utils.file_replace(
                site_config['core_path'] + 'config/config.inc.php',
                '(\s+|\t+|)\$modx_manager_path',
                '    $modx_manager_path = \'{}\';'.format(new)
            )
            utils.file_replace(
                site_config['core_path'] + 'config/config.inc.php',
                '(\s+|\t+|)\$modx_manager_url',
                '    $modx_manager_url = \'/{}/\';'.format(value)
            )
            utils.file_replace(
                config.path['home'] + self.user + '/config.xml',
                '(\s+|\t+|)\<context_mgr_path>',
                '    <context_mgr_path>{}</context_mgr_path>'.format(new)
            )
            utils.file_replace(
                config.path['home'] + self.user + '/config.xml',
                '(\s+|\t+|)\<context_mgr_url>',
                '    <context_mgr_url>/{}/</context_mgr_url>'.format(value)
            )
            utils.run('mv {0} {1}'.format(site_config['context_mgr_path'], new))

        return utils.success()
