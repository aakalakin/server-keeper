import utils
import config
import logging
import subprocess
import re
import json
import os


class Scan:
    def __init__(self, user, params):
        self.user = user
        self.params = {
            'command': params['command'] if 'command' in params else 'aibolit',
            'mode': params['mode'] if 'mode' in params else None,
            'report': True if 'report' in params else False,
            'params': params['params'] if 'params' in params else '--all'
        }

    def process(self):
        if self.params['command'] == 'clamav':
            res = self.clamav()
        else:
            res = self.aibolit(self.params['mode'])

        if res['success'] is not True:
            return res

        if len(res['data']['files']) and self.params['report']:
            utils.post_response('https://modhost.pro/assets/components/hoster/check.php', res['data'])

        return utils.success('', res['data'])

    def aibolit(self, mode):
        if mode is None:
            mode = 1
        target = config.path['home'] + self.user + '/www/'
        if not os.path.exists(target):
            msg = 'Target path {0} not found'.format(target)
            logging.error(msg)
            return utils.failure(msg)

        data = {
            'user': self.user,
            'files': {},
            'info': {},
        }

        ai = config.path['packages'] + 'ai-bolit-hoster.php'
        if os.path.isfile(ai):
            report = config.path['home'] + self.user + '/aibolit.json'
            logging.info('Scanning {}...'.format(target))
            cmd = 'php {0} -p {1} --mode={2} --json_report={3} --no-html --delay=5 {4} > /dev/null'.format(
                ai, target, mode, report, self.params['params']
            )

            subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True).communicate()
            output = json.load(open(report, 'r'))

            data['info']['time'] = int(output['summary']['scan_time'])
            data['info']['scanned'] = int(output['summary']['total_files'])
            data['info']['infected'] = 0

            if 'php_malware' in output:
                for item in output['php_malware']:
                    if item['sig'] == 'BIG FILE. SKIPPED.':
                        continue
                    name = re.sub(r'/jail/home/' + self.user + '/', '', item['fn'])
                    data['files'][name] = item['sig'].replace('[1] ', '')
                    data['info']['infected'] += 1
            elif 'js_malware' in output:
                for item in output['js_malware']:
                    if item['sig'] == 'BIG FILE. SKIPPED.':
                        continue
                    name = re.sub(r'/jail/home/' + self.user + '/', '', item['fn'])
                    data['files'][name] = item['sig'].replace('[1] ', '')
                    data['info']['infected'] += 1
        else:
            msg = 'Could not found {}'.format(ai)
            return utils.failure(msg)

        return utils.success('', data)

    def clamav(self):
        target = config.path['home'] + self.user
        if not os.path.exists(target):
            msg = 'Target path {0} not found'.format(target)
            logging.error(msg)
            return utils.failure(msg)

        logging.info('Scanning {}...'.format(target))
        cmd = 'nice -n 10 clamscan {} -i -r --max-filesize=1m --include="\.(php|js|html|sh)$"'.format(target)
        res = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        out, err = res.communicate()
        output = out.decode('utf-8', 'ignore').strip().split('----------- SCAN SUMMARY -----------')

        files = output[0].strip().split('\n')
        info = output[1].strip().split('\n')
        data = {
            'user': self.user,
            'files': {},
            'info': {},
        }

        for item in files:
            if item != '':
                tmp = item.split(': ')
                data['files'][re.sub(r'/jail/home/' + self.user + '/', '', tmp[0])] = re.sub(r' FOUND$', '', tmp[1])
        for item in info:
            tmp = item.split(': ')
            if tmp[0] == 'Scanned files':
                data['info']['scanned'] = int(tmp[1])
            elif tmp[0] == 'Infected files':
                data['info']['infected'] = int(tmp[1])
            elif tmp[0] == 'Time':
                data['info']['time'] = int(re.sub(r'\..*', '', tmp[1]))

        return utils.success('', data)

    def shell(self):
        target = config.path['home'] + self.user
        if not os.path.exists(target):
            msg = 'Target path {0} not found'.format(target)
            logging.error(msg)
            return utils.failure(msg)

        logging.info('Scanning {}...'.format(target))
        info = utils.get_site_config(target)

        if not isinstance(info, dict):
            utils.send_email('No config.xml in {}'.format(self.user), 'Please, fix it', config.watchdog['receivers'])
            return utils.success()
        elif not os.path.exists(info['core_path']):
            return utils.success()

        cmd = 'find {0} -name \'modx.class.php\' -exec {1} -print'.format(
            info['core_path'], 'grep -i \'Smarty5::redirect\' {} \;'
        )
        res = utils.run(cmd)

        if res['message'] == '':
            return utils.success('')

        tmp = res['message'].strip().split('\n')
        logging.info('Found shell in "{}"'.format(tmp[1]))

        utils.file_replace(tmp[1], r'.*?Smarty5::redirect', '')
        for i in ['ajax.api.php', 'readme.txt', 'Smarty.php']:
            utils.run('rm {0}lexicon/en/{1}'.format(info['core_path'], i))

        utils.send_email('Found shell in modx.class {}'.format(self.user), tmp[1] + '<br><pre>' + tmp[0] + '</pre>',
                         config.watchdog['receivers'])

        return utils.success('', tmp)
