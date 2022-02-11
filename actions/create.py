import os
import logging
import config
import utils
import re
import shutil
import math


class Create:
    def __init__(self, user, params):
        self.user = user

        default = {
            'domain': '{0}.{1}'.format(user, config.server['domain']),
            'system': '',
            'version': '',
            'hdd': 1024,
            'memory_limit': 128,
            'time_limit': 30,
            'workers': 10,
            'mail': True,
            'language': 'ru',
            'charset': 'utf8mb4',
            'passwords': {
                'mysql': utils.password(),
                'ssh': utils.password(),
                'manager': utils.password(),
            },
            'options': {
                'core': 'core',
                'connectors': 'connectors',
                'manager': 'manager',
                'prefix': 'modx_'
            },
            'backup_create': True,
            'backup_restore': False,
            'is_duplicate': False,
            'php': '7.0',
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
                'domain': params[0] if len(params) > 0 else default['domain'],
                'system': params[1] if len(params) > 1 else default['system'],
                'version': params[2] if len(params) > 2 else default['version'],
                'hdd': params[3] if len(params) > 3 else default['hdd'],
                'memory_limit': params[4] if len(params) > 4 else default['memory_limit'],
                'time_limit': params[5] if len(params) > 5 else default['time_limit'],
                'workers': params[6] if len(params) > 6 else default['workers'],
                'mail': params[7] if len(params) > 7 else default['mail'],
                'language': default['language'],
                'charset': default['charset'],
                'passwords': default['passwords'],
                'options': default['options'],
                'backup_create': default['backup_create'],
                'backup_restore': default['backup_restore'],
                'is_duplicate': default['is_duplicate'],
                'php': default['php'],
                'post_max': default['post_max'],
                'upload_max': default['upload_max'],
                'gc': default['gc'],
            }

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')
        elif self.params['domain'] == '':
            return utils.failure('You must specify site domain for creation')

        logging.info('Creating new site "{0}" for user "{1}"'.format(self.params['domain'], self.user))

        # Create user
        res = utils.run('useradd ' + self.user + ' -m -G jail -s /bin/bash')
        if not res['success']:
            logging.error(res['message'])
            return utils.failure(res['message'].replace('\n', ''))

        # Set user password
        file = open(config.path['tmp'] + self.user + '.pass', 'w')
        file.write(self.params['passwords']['ssh'] + '\n' + self.params['passwords']['ssh'])
        file.close()
        utils.run('cat ' + config.path['tmp'] + self.user + '.pass | passwd ' + self.user)
        os.remove(config.path['tmp'] + self.user + '.pass')

        # Jail user
        res = utils.run('jk_jailuser -m -s /bin/bash -j ' + config.path['jail'] + ' ' + self.user)
        if not res['success']:
            logging.error(res['message'])
            return utils.failure(res['message'])

        # Change user dir to chrooted env
        file = open(config.path['etc'] + 'passwd', 'r')
        tmp = file.read()
        strings = tmp.split('\n')
        i = 0
        for string in strings:
            if re.match('.*?' + config.path['jail'], string):
                string = string.replace(config.path['jail'] + '.', '')
                strings[i] = string.replace('/usr/sbin/jk_chrootsh', '/bin/bash')
            i += 1
        file.close()
        file = open(config.path['etc'] + 'passwd', 'w')
        file.write('\n'.join(strings))
        file.close()

        # Copy shadow record
        shadow = '{}etc/shadow'.format(config.path['jail'])
        utils.run('touch ' + shadow)
        res = utils.run('cat /etc/shadow | grep {}:'.format(self.user))
        if res['success']:
            utils.file_add(shadow, res['message'].strip())

        # Create symlink from user dir
        utils.run('ln -s ' + config.path['home'] + self.user + ' /home/' + self.user)

        # Set user quota
        quota = str(int(self.params['hdd']) * config.server['hdd_multiplier'])
        res = utils.run(['setquota', '-u', self.user, quota, quota, '0', '0', '/'])
        if not res['success']:
            logging.error(res['message'])
            # return utils.failure(res['message'])

        # Create directories
        try:
            dst = config.path['home'] + self.user + '/'
            os.mkdir(dst + 'www')
            os.mkdir(dst + 'tmp')
            os.mkdir(dst + 'etc')
            os.mkdir(dst + 'log')
            shutil.copyfile(config.path['templates'] + 'nginx/rules.conf', dst + config.path['user']['rules'])
            file = open(dst + config.path['user']['nginx'], 'w')
            file.close()
        except Exception as e:
            logging.error('Failed to create user directories: ' + str(e))

        # Create and save configs
        self.configs()

        # Create database
        q = 'CREATE DATABASE IF NOT EXISTS `{0}` DEFAULT CHARACTER SET {1} COLLATE {1}_unicode_ci;' \
            'GRANT ALL PRIVILEGES ON {0}.* TO {0}@localhost IDENTIFIED BY "{2}";' \
            'FLUSH PRIVILEGES;'.format(self.user, self.params['charset'], self.params['passwords']['mysql'])
        res = utils.mysql(q)
        if not res['success']:
            print(res)
            return utils.failure(['message'])

        # Download and install CMS
        if self.params['system']:
            if not self.download():
                return utils.failure('Could not retrieve CMS distribution package')
            if not self.install():
                return utils.failure('Could not install CMS')

        # Fixing permissions
        logging.info('Set permissions')
        utils.permissions(config.path['home'] + self.user, self.user)

        site_config = utils.get_site_config(config.path['home'] + self.user)
        # Create or restore backup
        if self.params['backup_create'] is True and not self.params['is_duplicate']:
            from actions.backup import Backup
            Backup(self.user, {'command': 'create'}).process()
        elif self.params['backup_restore'] is True:
            if self.params['is_duplicate'] is True:
                utils.run('mv {0}{1}/etc /tmp/{1}'.format(config.path['home'], self.user))
                utils.run('mv {0}config/config.inc.php /tmp/{1}.config.inc.php'.format(
                    site_config['core_path'], self.user)
                )
                utils.run('mv {0}{1}/config.xml /tmp/{1}.config.xml'.format(config.path['home'], self.user))
                utils.run('mv {0}{1}/pass.txt /tmp/{1}.pass.txt'.format(config.path['home'], self.user))
            from actions.backup import Backup
            Backup(self.user, {'command': 'restore'}).process()

        if self.params['is_duplicate'] is True:
            logging.info('Cleaning backups')
            utils.run('rm -rf {0}{1}/etc'.format(config.path['home'], self.user))
            utils.run('mv /tmp/{1} {0}{1}/etc'.format(config.path['home'], self.user))
            utils.run('mv /tmp/{1}.config.inc.php {0}config/config.inc.php'.format(
                site_config['core_path'], self.user)
            )
            utils.run('mv /tmp/{1}.config.xml {0}{1}/config.xml'.format(config.path['home'], self.user))
            utils.run('mv /tmp/{1}.pass.txt {0}{1}/pass.txt'.format(config.path['home'], self.user))

            if self.params['system']:
                from actions.update import Update
                from actions.password import Password
                Password(self.user, {'passwords': self.params['passwords'], 'system': self.params['system']}).process()
                Update(self.user, {'system': self.params['system'], 'version': self.params['version']}).process()
                Password(self.user, {'passwords': self.params['passwords'], 'system': self.params['system']}).process()

            if self.params['backup_create']:
                from actions.backup import Backup
                Backup(self.user, {'command': 'create'}).process()
        logging.info('Done!')

        passwords = utils.get_site_info(config.path['home'] + self.user)
        if passwords is False:
            passwords = self.params['passwords']
        return utils.success(data=passwords)

    def configs(self):
        placeholders = {
            '{user}': self.user,
            '{port}': utils.get_port(self.user),
            '{domain}': self.params['domain'],
            '{password}': self.params['passwords']['manager'],
            '{mysql}': self.params['passwords']['mysql'],
            '{charset}': self.params['charset'],
            '{ssh}': self.params['passwords']['ssh'],
            '{language}': self.params['language'],
            '{core}': self.params['options']['core'] if 'core' in self.params['options'] else 'core',
            '{manager}': self.params['options']['manager'] if 'manager' in self.params['options'] else 'manager',
            '{connectors}': self.params['options']['connectors'] if 'connectors' in self.params['options'] else 'connectors',
            '{prefix}': self.params['options']['prefix'] if 'prefix' in self.params['options'] else 'modx_',
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

        # Nginx worker
        nginx = utils.template(config.path['templates'] + 'nginx/user.conf', placeholders)
        src = config.path['nginx'] + 'sites-available/' + self.user + '.conf'
        dst = config.path['nginx'] + 'sites-enabled/' + self.user + '.conf'
        file = open(src, 'w')
        file.write(nginx)
        file.close()
        if not os.path.islink(dst):
            os.symlink(src, dst)

        # Php-fpm pool
        php = str(self.params['php'])
        file = open(config.path['php' + php] + self.user + '.conf', 'w')
        file.write(utils.template(config.path['templates'] + 'php-fpm.conf', placeholders))
        file.close()
        utils.service('php' + php, 'restart')

        # MODX config
        modx = utils.template(config.path['templates'] + 'modx.xml', placeholders)
        file = open(config.path['home'] + self.user + '/config.xml', 'w')
        file.write(modx)
        file.close()
        utils.run(['chmod', '0400', config.path['home'] + self.user + '/config.xml'])

        # Passwords file
        passwords = utils.template(config.path['templates'] + 'pass.txt', placeholders)
        file = open(config.path['home'] + self.user + '/pass.txt', 'w')
        file.write(passwords)
        file.close()
        utils.run(['chmod', '0400', config.path['home'] + self.user + '/pass.txt'])

        # Copy config of Midnight Commander
        utils.run('mkdir ' + config.path['home'] + self.user + '/.config')
        utils.run('mkdir ' + config.path['home'] + self.user + '/.config/mc')
        utils.run('cp ' + config.path['templates'] + 'mc.ini ' + config.path['home'] + self.user + '/.config/mc/ini')

        # Logrotate
        logrotate = utils.template(config.path['templates'] + 'logrotate.conf', placeholders)
        file = open(config.path['logrotate'] + '_' + self.user, 'w')
        file.write(logrotate)
        file.close()
        utils.run(['chmod', '0644', config.path['logrotate'] + '_' + self.user])

        # Reloading Nginx
        utils.service('nginx', 'reload')

        # Set permissions to logs
        utils.run('chmod 0644 ' + config.path['home'] + self.user + '/log/*')
        utils.run('chmod 0655 ' + config.path['home'] + self.user + '/log/')

        # Set permissions to configs
        utils.run('chmod 0640 ' + config.path['home'] + self.user + '/etc/*')

    def download(self):
        download_link = self.params['download_link'] if 'download_link' in self.params else ''
        file = utils.download(self.params['system'], self.params['version'], download_link)
        if file:
            logging.info('{} package retrieved'.format(self.params['system']))
            src = utils.extract(file, config.path['tmp'] + self.params['system'] + '/')
            dst = config.path['home'] + self.user + '/'
            if src:
                logging.info('{} package unzipped'.format(self.params['system']))
                if not os.path.isdir(config.path['home']):
                    os.mkdir(config.path['home'])
                try:
                    os.renames(src, dst + 'www/')
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
            if 'core' not in self.params['options']:
                self.params['options']['core'] = 'core'
            elif self.params['options']['core'] != 'core':
                utils.run('mv {0}/www/core {0}/www/{1}'.format(
                    config.path['home'] + self.user, self.params['options']['core']
                ))
            res = utils.run('php {0}/www/setup/index.php --installmode=new --config={0}/config.xml \
                            --core_path={0}/www/{1}/'
                            .format(config.path['user_home'] + self.user, self.params['options']['core']))
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
                    res2 = utils.run_php(config.path['packages'] + 'modx_revo.php', self.user, params)
                    logging.info(res2['message'].replace('\n', ''))

                    params['action'] = 'package_install'
                    res2 = utils.run_php(config.path['packages'] + 'modx_revo.php', self.user, params)
                    logging.info(res2['message'].replace('\n', ''))

            utils.run('rm -rf {0}{1}/www/{2}/packages/core'.format(
                config.path['home'], self.user, self.params['options']['core']
            ))
            utils.run('rm -rf {0}{1}/www/{2}/packages/core.transport.zip'.format(
                config.path['home'], self.user, self.params['options']['core']
            ))
            return res['success']
        elif system == 'pma':
            cfg = config.path['home'] + self.user + '/www/config.inc.php'
            utils.run('mv {0}/www/config.sample.inc.php {1}'.format(config.path['home'] + self.user, cfg))

            tmp = utils.password(50)
            utils.file_replace(cfg, "\$cfg\['blowfish_secret'\] = '';", "$cfg['blowfish_secret'] = '{0}';".format(tmp))
            utils.file_replace(cfg, "\$cfg\['Servers'\]\[\$i\]\['host'\]", "$cfg['Servers'][$i]['host'] = '127.0.0.1';")
            utils.file_add(cfg, "$cfg['PmaNoRelation_DisableWarning'] = true;")

            utils.run('rm -rf {0}/www/setup {0}/www/examples {0}/www/doc'.format(config.path['home'] + self.user))

        elif system == '':
            logging.info('No CMS specified - skip installation')
        else:
            logging.info('Skip installation of unknown CMS: "{}".'.format(self.params['system']))

        return True
