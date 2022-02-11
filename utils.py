import os
import subprocess
import config
import logging
import string
import re
import json


def template(file, placeholders):
    tmp = open(file)
    tpl = tmp.read()

    for key in placeholders:
        tpl = tpl.replace(key, str(placeholders[key]))

    return tpl


def service(name, command='reload'):
    if command == 'restart' and re.match(r'^php', name) and name in config.commands:
        ver = re.sub(r'[^0-9\.]', '', name)
        res = run('/usr/sbin/php-fpm{0} -t'.format(ver))
        if res['code'] == 0:
            run('service {0} stop && killall {0}'.format(config.commands[name]))
            res = run('service {} start'.format(config.commands[name]))
        else:
            send_email('Could not restart PHP', res['message'], config.watchdog['receivers'])
    elif name == 'sprutio':
        res = run('cd /opt/sprutio/ && ./docker-compose -p sprutio {} 2>/dev/null'.format(command))
    elif name == 'mysql':
        res = run('service mysql {} 2>/dev/null'.format(command))
    elif name in config.commands:
        if name == 'nginx':
            res = run('nginx -t'.format(config.commands[name]))
            if res['code'] == 0:
                res = run(['service', config.commands[name], command])
            else:
                send_email('Could not restart NGINX', res['message'], config.watchdog['receivers'])
        else:
            res = run(['service', config.commands[name], command])
    else:
        res = run(['service', name, command])

    if res['success'] is not True:
        logging.error('Could not {0} {1}: {2}'.format(command, name, res['message']))
    else:
        logging.info(name + ' was successfully {}ed'.format(command))

    return res


def run(args):
    shell = isinstance(args, str)
    res = subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=shell)
    out, err = res.communicate()

    if res.returncode is not 0:
        return {'success': False, 'message': err.decode('utf8', 'ignore'), 'code': res.returncode}
    else:
        return {'success': True, 'message': out.decode('utf-8', 'ignore'), 'code': res.returncode}


def run_php(file, user, args=''):
    if not isinstance(args, str):
        args = json.dumps(args)

    script = '{0}{1}/tmp.php'.format(config.path['home'], user)
    data = file_read(file)
    if data:
        file_write(script, data)
        run('chown {0}:{0} {1} && chmod 644 {1}'.format(user, script))

    res = run('sudo -i -u {0} php {1} \'{2}\''.format(user, script, args))
    run('rm {}'.format(script))

    return res


def mysql(args):
    return run(['mysql', '-uroot', '-e', args])


def download(system, version, download_link=''):
    system = str(system).lower()
    if system == 'modx' or system == 'modx_revo':
        if download_link is not '':
            file = 'modx-' + version + '.zip'
            dst = config.path['tmp'] + file
            src = download_link
        elif version not in ['', 'latest']:
            file = 'modx-' + version + '.zip'
            dst = config.path['tmp'] + file
            src = 'http://modx.com/download/direct/' + file
        else:
            dst = config.path['tmp'] + 'modx-latest.zip'
            src = 'http://modx.com/download/latest/'
    elif system == 'pma':
        if version == '':
            version = 'latest'
        file = 'pma-' + version + '.zip'
        dst = config.path['tmp'] + file
        if download_link is not '':
            src = download_link
        elif version == 'latest':
            src = 'https://www.phpmyadmin.net/downloads/phpMyAdmin-latest-all-languages.zip'
        else:
            src = 'https://files.phpmyadmin.net/phpMyAdmin/{0}/phpMyAdmin-{0}-all-languages.zip'.format(version)
    elif system == '':
        logging.info('No CMS specified - skip downloading')
        return False
    else:
        logging.info('Skip download distribution of unknown CMS: "{}"'.format(system))
        return False

    if not checkcache(dst):
        logging.info('Downloading file from ' + src)
        res = run('wget {0} -O {1}'.format(src, dst))
        if not res['success']:
            logging.error('Could not download file: ' + res['message'])
            run('rm {0}'.format(dst))
        else:
            logging.info('Downloading complete')

    if os.path.isfile(dst):
        return dst
    else:
        return False


def post_response(url, values, retry=1, timeout=5):
    import urllib.request, urllib.parse, socket, time

    if retry == 1:
        values = json.dumps(values).encode('utf-8')
    else:
        time.sleep(2)
        logging.info('Post response to control panel... Attempt {0} '.format(retry))

    try:
        request = urllib.request.Request(url, data=values, headers={})
        # request.add_header('Content-type', 'application/x-www-form-urlencoded')
        urllib.request.urlopen(request, timeout=timeout)
    except socket.timeout:
        logging.info('Timeout, retrying...')
        return post_response(url, values, retry + 1)
    except urllib.request.HTTPError as e:
        if e.code >= 500:
            logging.info('Error {}, retrying...'.format(e.code))
            return post_response(url, values, retry + 1)
        else:
            logging.error('Error {}'.format(e.code))
            return failure('Error {}'.format(e.code))
    except Exception as e:
        logging.error(e)

    return success()


def checkcache(file):
    if os.path.isfile(file):
        import time

        if time.time() - os.path.getctime(file) > config.cache['time']:
            return False
        else:
            return True
    else:
        return False


def extract(file, to):
    if os.path.isdir(to):
        run('rm -rf ' + to)

    tmp = re.match(r'.*?\.([a-z]+)$', file, flags=re.IGNORECASE)
    type = tmp.groups()[0]
    type = str(type).lower()

    if type == 'zip':
        import zipfile
        archive = zipfile.ZipFile(file)
        archive.extractall(to)

        root = os.listdir(to)[0]
        path = to + root
        for item in os.listdir(path):
            os.renames(path + '/' + item, to + '/' + item)
        return to
    else:
        logging.error('Skip unknown type of archive: "{}"'.format(type))
        return False


def password(length=12, chars=string.ascii_letters + string.digits):
    from random import choice

    word = ''
    for i in range(length):
        word += choice(chars)

    return word


def move_dir(src, dst):
    import shutil

    for src_dir, dirs, files in os.walk(src):
        dst_dir = src_dir.replace(src, dst)
        if not os.path.exists(dst_dir):
            os.mkdir(dst_dir)
        for file_ in files:
            src_file = os.path.join(src_dir, file_)
            dst_file = os.path.join(dst_dir, file_)
            if os.path.exists(dst_file):
                os.remove(dst_file)
            shutil.move(src_file, dst_dir)


def permissions(path, user, group='www-data'):
    commands = [
        'chown -R {0}:{1} {2}',
        'chown -R root:root {2}/etc && chmod 0755 {2}/etc && find {2}/etc/ -iname "*[conf|crt|key]" | xargs chmod 640;',
        'chown -R root:root {2}/log && chmod 0755 {2}/log',
        'chown -R root:root {2}/pass.txt && chmod 0600 {2}/pass.txt',
        'chown -R root:root {2}/config.xml && chmod 0600 {2}/config.xml 2> /dev/null',
        'chmod -R go=rX,u=rwX {2}/www',
        'chmod 0750 {2}',
    ]
    for command in commands:
        res = run(command.format(user, group, path))
        if not res['success']:
            logging.error(res['message'])


def success(message='', data=''):
    return {
        'success': True,
        'message': message,
        'data': data
    }


def failure(message='', data=''):
    return {
        'success': False,
        'message': message,
        'data': data
    }


def file_add(filename, text):
    try:
        file = open(filename, 'r')
    except Exception as e:
        print('Could not open file "{0}" for reading: {1}'.format(filename, e))
        return False

    found = False
    strings = file.read().split('\n')
    file.close()

    for string in strings:
        if string == text:
            found = True

    if not found:
        if strings[-1] in ['', '#']:
            strings[-1] = text
            strings.append('')
        else:
            strings.append(text)

        try:
            file = open(filename, 'w')
        except Exception as e:
            print('Could not open file "{0}" for writing: {1}'.format(filename, e))
            return False

        file.write('\n'.join(strings))
        file.close()

    return True


def file_remove(filename, text):
    try:
        file = open(filename, 'r')
    except Exception as e:
        print('Could not open file "{0}" for reading: {1}'.format(filename, e))
        return False

    found = False
    strings = file.read().split('\n')
    file.close()

    new_strings = []
    for string in strings:
        if re.match(text, string):
            found = True
        else:
            new_strings.append(string)

    if found:
        try:
            file = open(filename, 'w')
        except Exception as e:
            print('Could not open file "{0}" for writing: {1}'.format(filename, e))
            return False
        file.write('\n'.join(new_strings))
        file.close()

    return found


def file_replace(filename, src, dst):
    try:
        file = open(filename, 'r')
    except Exception as e:
        print('Could not open file "{0}" for reading: {1}'.format(filename, e))
        return False

    found = False
    strings = file.read().split('\n')
    file.close()

    i = 0
    for string in strings:
        if re.match(src, string):
            strings[i] = dst
            found = True
        i += 1

    if found:
        try:
            file = open(filename, 'w')
        except Exception as e:
            print('Could not open file "{0}" for writing: {1}'.format(filename, e))
            return False
        file.write('\n'.join(strings))
        file.close()

    return found


def file_read(filename):
    try:
        file = open(filename, 'r')
    except Exception as e:
        print('Could not open file "{0}" for reading: {1}'.format(filename, e))
        return False
    data = file.read().strip()
    file.close()

    return data

def file_write(filename, data):
    try:
        file = open(filename, 'w')
    except Exception as e:
        print('Could not open file "{0}" for writing: {1}'.format(filename, e))
        return False
    file.write(data)
    file.close()

    return True


def get_port(user):
    tmp = re.sub('\D', '', user)
    if tmp.isdigit():
        port = 10000 + int(tmp)
    else:
        # Check open ports
        res = run('netstat -nl | grep 127.0.0.1')
        matches = re.findall('127\.0\.0\.1:(\d+)', res["message"], re.MULTILINE)
        if len(matches):
            ports = []
            for i in matches:
                ports.append(int(i))
            # if port in ports:
            port = max(ports) + 1
            if port < 10001:
                port = 10001
        else:
            port = 10001

    return port


def get_site_info(home_dir):
    pass_txt = home_dir + '/pass.txt'
    if os.path.isfile(pass_txt):
        try:
            file = open(pass_txt, 'r')
        except Exception as e:
            print('Could not open file "{0}" for reading: {1}'.format(pass_txt, e))
            return False

        strings = file.read().split('\n')
        file.close()

        data = {}
        for string in strings:
            search = re.search(r'^(SSH/SFTP|MySQL|Manager) password: (.*?)$', string)
            if search:
                if search.group(1) == 'SSH/SFTP':
                    key = 'ssh'
                elif search.group(1) == 'MySQL':
                    key = 'mysql'
                else:
                    key = 'manager'
                data[key] = search.group(2)
        return data
    else:
        logging.error('Could not find file {}'.format(pass_txt))
        return False


def get_site_config(home_dir):
    config_xml = home_dir + '/config.xml'
    if os.path.isfile(config_xml):
        import xml.etree.ElementTree as Et
        tree = Et.parse(config_xml)
        root = tree.getroot()

        data = {}
        for key in root:
            data[key.tag] = key.text
        return data
    else:
        logging.error('Could not find file {}'.format(config_xml))
        return False


def restart_services(host='', type='none'):
    for com in config.commands:
        service(com, 'restart')

    if host != '':
        from time import gmtime, strftime
        message = "Services were restarted at {0}\n\n    {1}: \"{2}\"".format(
            strftime("%Y-%m-%d %H:%M:%S", gmtime()), host, type
        )
        send_email('Restarting services', message, config.watchdog['receivers'])
    return True


def get_php_ver(user):
    php = ['5.6', '7.0', '7.1', '7.2', '7.3', '7.4']
    for i in php:
        cnf = config.path['php' + i] + user + '.conf'
        if os.path.isfile(cnf):
            return i
    return False


def send_email(subject, message, receivers):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if type(receivers) is not list:
        receivers = [receivers]

    sender = 'root@' + config.server['domain']
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = 'root@' + config.server['domain']
    msg['To'] = receivers[0]
    msg.attach(MIMEText(message, 'plain'))
    msg.attach(MIMEText("<html><head></head><body>{0}</body></html>".format(message), 'html'))

    try:
        smtp = smtplib.SMTP('127.0.0.1')
        smtp.sendmail(sender, receivers, msg.as_string())
        smtp.quit()
    except smtplib.SMTPException as e:
        print(e)
