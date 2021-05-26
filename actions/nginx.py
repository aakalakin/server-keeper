import os
import logging
import config
import utils
import re
import shutil


class Nginx:
    def __init__(self, user, params):
        self.user = user

        default = {
            'command': '',
            'data': {},
        }
        if isinstance(params, dict):
            self.params = params
            for key in default:
                if key not in self.params:
                    self.params[key] = default[key]
        else:
            self.params = {
                'command': params[0] if len(params) > 0 else default['command'],
                'data': params[1] if len(params) > 1 else default['data'],
            }

    def process(self):
        if self.user == '':
            return utils.failure('You must specify user')

        if self.params['command'] == 'config':
            return self.config(self.params['data'])
        elif self.params['command'] == 'get_rules':
            return self.get_rules()
        elif self.params['command'] == 'update_rules':
            return self.update_rules(self.params['data'])
        elif self.params['command'] == 'disable':
            return self.disable()
        elif self.params['command'] == 'enable':
            return self.enable()
        elif self.params['command'] == 'get_cert':
            return self.get_cert(self.params['data'])
        elif self.params['command'] == 'put_cert':
            return self.put_cert(self.params['data'])
        elif self.params['command'] == 'remove_cert':
            return self.remove_cert()
        elif self.params['command'] == 'get_main_cert':
            return self.get_main_cert()
        else:
            msg = 'Unknown command "{}", exit.'.format(self.params['command'])
            logging.error(msg)
            return utils.failure(msg)

    def config(self, new_config):
        if not isinstance(new_config, dict):
            return utils.failure('Wrong config. It must be an array of values.')

        logging.info('Updating Nginx config for user "{}"'.format(self.user))

        conf = config.path['home'] + self.user + '/' + config.path['user']['nginx']
        backup = config.path['home'] + self.user + '/' + config.path['user']['nginx'] + '.tmp'
        utils.run('cp {0} {1}'.format(conf, backup))

        for key in new_config:
            utils.file_remove(conf, key)
            if len(new_config[key]):
                utils.file_add(conf, '{0}    {1};'.format(key, ' '.join(new_config[key])))

        return self.test(conf, backup)

    def get_rules(self):
        conf = config.path['home'] + self.user + '/' + config.path['user']['rules']
        if os.path.isfile(conf):
            file = open(conf, 'r')
            rules = file.read()
            file.close()
        else:
            rules = ''

        logging.info('Returning Nginx rules for user "{}"'.format(self.user))
        return utils.success(data=rules)

    def update_rules(self, rules=''):
        if not isinstance(rules, str):
            return utils.failure('Wrong config. It must be an plain text with rules.')
        elif rules is '':
            rules = open(config.path['templates'] + 'nginx/rules.conf', 'r').read()

        logging.info('Saving Nginx rules for user "{}"'.format(self.user))

        # Escape nested brackets
        opened = 0
        escaped = ''
        for l in rules:
            if l == '{':
                opened += 1
                if opened > 1:
                    l = '[[['
            elif l == '}':
                if opened > 1:
                    l = ']]]'
                opened -= 1
            escaped += l

        # Only location and if rules are allowed
        rules = re.findall(r'(?=location|if).*?\{.*?\}', escaped, flags=re.DOTALL)

        conf = config.path['home'] + self.user + '/' + config.path['user']['rules']
        backup = config.path['home'] + self.user + '/' + config.path['user']['rules'] + '.tmp'
        utils.run('cp {0} {1}'.format(conf, backup))
        """
        if not os.path.isfile(conf):
            file = open(conf, 'w')
            file.close()
        else:
            shutil.copyfile(conf, backup)
        """

        file = open(conf, 'w')
        file.write('\n\n'.join(rules).replace('[[[', '{').replace(']]]', '}'))
        file.close()

        test = self.test(conf, backup)
        if test['success']:
            rules = self.get_rules()
            return utils.success(data={'test': 'ok', 'rules': rules['data']})
        else:
            return utils.success(data={'test': 'fail', 'error': test['message']})

    def disable(self):
        logging.info('Disabling the site "{0}"'.format(self.user))
        conf = config.path['nginx'] + 'sites-enabled/' + self.user + '.conf'
        if os.path.islink(conf):
            os.remove(conf)
            utils.service('nginx', 'restart')

            return utils.success()
        else:
            msg = 'Could not find site config. Maybe it not exists?'
            logging.error(msg)

            return utils.failure(msg)

    def enable(self):
        logging.info('Enabling the site "{0}"'.format(self.user))
        src = config.path['nginx'] + 'sites-available/' + self.user + '.conf'
        dst = config.path['nginx'] + 'sites-enabled/' + self.user + '.conf'
        if not os.path.isfile(src):
            msg = 'Could not find site config. Maybe it not exists?'
            logging.error(msg)

            return utils.failure(msg)
        elif not os.path.islink(dst):
            os.symlink(src, dst)
            utils.service('nginx', 'restart')

            return utils.success()
        else:
            msg = 'Site is already enabled.'
            logging.info(msg)

            return utils.success()

    def get_cert(self, domains):
        if isinstance(domains, list) is not True or len(domains) == 0:
            return utils.failure('You must enter a list of domains to sign')
        else:
            logging.info('Trying to sign certificate for user "{}"'.format(self.user))

        etc = config.path['home'] + self.user + '/'

        conf = etc + config.path['user']['nginx']
        if utils.file_remove(conf, 'location    /.well-known/acme-challenge/'):
            logging.info('Removed old settings for user "{}"'.format(self.user))
            utils.service('nginx', 'restart')

        conf = etc + config.path['user']['rules']
        backup = conf + '.tmp'
        if os.path.exists(backup) is True:
            return utils.failure('The backup rules are still here! Please, fix it.')
        else:
            shutil.copyfile(conf, backup)
            with open(conf, 'w') as file:
                file.write('')
            logging.info('Clean user rules'.format(self.user))
            utils.service('nginx', 'restart')

        cmd = 'certbot certonly --non-interactive --cert-name {0} --webroot -w /home/{0}/www/ --domains {1} ' \
              '--agree-tos --email {2} --quiet'.format(self.user, ','.join(domains), config.watchdog['receivers'][0])
        logging.info(cmd)

        res = utils.run(cmd)
        logging.info('Restore user rules'.format(self.user))
        shutil.copyfile(backup, conf)
        os.remove(backup)
        if res['success'] is True:
            certs = '{0}letsencrypt/live/{1}/'.format(config.path['etc'], self.user)
            res = self.put_cert({
                'cert': open(certs + 'fullchain.pem').read(),
                'key': open(certs + 'privkey.pem').read()
            })
        else:
            logging.error(res['message'])
            utils.service('nginx', 'restart')

        return res

    def put_cert(self, data):
        logging.info('Trying to activate certificate for user "{}"'.format(self.user))
        with open(config.path['home'] + self.user + '/etc/cert.crt', 'w') as file:
            file.write(data['cert'])
        with open(config.path['home'] + self.user + '/etc/cert.key', 'w') as file:
            file.write(data['key'])

        home = config.path['home'] + self.user + '/'
        conf = home + config.path['user']['nginx']
        backup = home + config.path['user']['nginx'] + '.tmp'
        utils.run('cp {0} {1}'.format(conf, backup))

        utils.file_remove(conf, '(ssl_|listen)')
        utils.file_add(conf, 'listen 443 ssl http2;')
        utils.file_add(conf, 'listen [::]:443 ssl http2;')
        utils.file_add(conf, 'ssl_certificate {}etc/cert.crt;'.format(home))
        utils.file_add(conf, 'ssl_certificate_key {}etc/cert.key;'.format(home))
        utils.file_add(conf, 'ssl_session_timeout 1d;')
        utils.file_add(conf, 'ssl_session_cache shared:SSL:50m;')
        # utils.file_add(conf, 'ssl_session_tickets off;')
        utils.file_add(conf, 'ssl_protocols TLSv1 TLSv1.1 TLSv1.2;')
        utils.file_add(conf, 'ssl_prefer_server_ciphers on;')
        utils.file_add(conf,
                       'ssl_ciphers \'ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256:ECDHE-ECDSA-AES128-SHA:ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES128-SHA:ECDHE-ECDSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA:ECDHE-RSA-AES256-SHA:DHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA:DHE-RSA-AES256-SHA256:DHE-RSA-AES256-SHA:ECDHE-ECDSA-DES-CBC3-SHA:ECDHE-RSA-DES-CBC3-SHA:EDH-RSA-DES-CBC3-SHA:AES128-GCM-SHA256:AES256-GCM-SHA384:AES128-SHA256:AES256-SHA256:AES128-SHA:AES256-SHA:DES-CBC3-SHA:!DSS\';')
        utils.file_add(conf, 'ssl_stapling on;')
        utils.file_add(conf, 'ssl_stapling_verify on;')
        # utils.file_add(conf, 'ssl_dhparam /path/to/dhparam.pem;')
        utils.permissions(config.path['home'] + self.user, self.user)

        return self.test(conf, backup)

    def remove_cert(self, reload=True):
        cert = '{0}letsencrypt/live/{1}/cert.pem'.format(config.path['etc'], self.user)
        if os.path.exists(cert):
            logging.info('Trying to revoke SSL certificate')
            cmd = 'certbot revoke --non-interactive --quiet --cert-path ' + cert
            logging.info(cmd)
            res = utils.run(cmd)
            if res['success'] is True:
                utils.run('certbot delete --cert-name {0}'.format(self.user))
                logging.info('Certificate was successfully revoked')
            else:
                logging.error(res['message'])

        path = config.path['home'] + self.user + '/'
        if os.path.exists(path + 'etc/cert.crt'):
            utils.run('rm {0}etc/cert.*'.format(path))
            if utils.file_remove(path + config.path['user']['nginx'], '(ssl_|listen)') is True:
                if reload is True:
                    utils.service('nginx', 'restart')

        return utils.success()

    @staticmethod
    def get_main_cert():
        domains = [utils.file_read('/etc/hostname')]
        logging.info('Trying to sign certificate for "{}"'.format(domains[0]))
        conf = config.path['etc'] + 'letsencrypt/live/main/'
        cmd = 'certbot certonly --non-interactive --cert-name main --webroot -w {0} --domains {1} ' \
              '--agree-tos --email {2} --quiet' \
            .format(config.path['templates'] + 'default_site/', ','.join(domains), config.watchdog['receivers'][0])
        logging.debug(cmd)

        res = utils.run(cmd)
        if res['success'] is True:
            ssl = config.path['nginx'] + 'ssl/'
            utils.run('mkdir ' + ssl)
            with open(ssl + '/nginx_ssl.crt', 'w') as cert:
                cert.write(open(conf + 'fullchain.pem').read())
            with open(ssl + '/nginx_ssl.key', 'w') as cert:
                cert.write(open(conf + 'privkey.pem').read())
            utils.service('nginx', 'restart')

            utils.run('cp -f {0}ssl/nginx_ssl.crt {0}ssl/sprutio.crt'.format(config.path['nginx']))
            utils.run('cp -f {0}ssl/nginx_ssl.key {0}ssl/sprutio.key'.format(config.path['nginx']))
            utils.service('sprutio', 'restart')

            return res
        else:
            logging.error(res['message'])

            return res

    @staticmethod
    def test(conf, backup):
        response = utils.run('nginx -t')

        if response['code'] == 0:
            utils.service('nginx', 'restart')
            os.remove(backup)
            logging.info('Done!')

            return utils.success()
        else:
            shutil.move(backup, conf)
            tmp = response['message'].split('\n')
            for i in tmp:
                if i is not '':
                    logging.error(i)
            return utils.failure(response['message'])
