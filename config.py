import os
import utils
import logging
import re

servers = 10  # Total number of working servers
host = 'modhost.pro'  # Base domain name

timezone = 'Europe/Moscow'

admin = 'bezumkin'

allowed = {
    '213.219.36.159',  # Modhost
    'modhost.pro',  # Modhost
    'modhost.test',  # Develop
}

log = {
    'level': logging.DEBUG,
    'format': '%(threadName)s [%(asctime)s] %(levelname)-8s %(message)s',
    'file': '/var/log/server-keeper.log',
}

path = {
    'jail': '/jail/',
    'etc': '/etc/',
    'tmp': '/tmp/',
    'ssh': '/etc/ssh/',
    'nginx': '/etc/nginx/',
    # 'munin': '/etc/munin/',
    'php5.6': '/etc/php/5.6/fpm/pool.d/',
    'php7.0': '/etc/php/7.0/fpm/pool.d/',
    'php7.1': '/etc/php/7.1/fpm/pool.d/',
    'php7.2': '/etc/php/7.2/fpm/pool.d/',
    'php7.3': '/etc/php/7.3/fpm/pool.d/',
    'php7.4': '/etc/php/7.4/fpm/pool.d/',
    'php-cli': '/etc/php/7.0/cli/',
    'logrotate': '/etc/logrotate.d/',
    'run': '/var/run/',
    'log': '/var/log/',
    'home': '/jail/home/',
    'user_home': '/home/',
    'templates': os.path.dirname(os.path.realpath(__file__)) + '/templates/',
    'actions': os.path.dirname(os.path.realpath(__file__)) + '/actions/',
    'packages': os.path.dirname(os.path.realpath(__file__)) + '/packages/',
    'user': {
        'nginx': 'etc/nginx.conf',
        'rules': 'etc/rules.conf',
        'backups': '/var/user_backups/',
    },
    'pass': os.path.dirname(os.path.realpath(__file__)) + '/.pass'
}

password = {
    'mysql': 'zexEdx37KqyQv1fD3rf5IoYoezR1Z3ks1ZI1dvQ8e3iHGcvczW',
    'gpg': 'GQRI14HonJ6lec1Ce4vKLZWdfCSZa9JxTt4WakJ7G0BjHh97Uh',
    'admin': utils.password(),
    'disk_token': 'AQAEA7qhwds2AAN5GMJJsreJsUbls4svNY1Jd58',
    # 'user': {
    #    'mysql': utils.password(),
    #    'ssh': utils.password(),
    #    'manager': utils.password(),
    # }
}

commands = {
    'nginx': 'nginx',
    'mysql': 'mysql',
    'php5.6': 'php5.6-fpm',
    'php7.0': 'php7.0-fpm',
    'php7.1': 'php7.1-fpm',
    'php7.2': 'php7.2-fpm',
    'php7.3': 'php7.3-fpm',
    'php7.4': 'php7.4-fpm',
}

cache = {
    'time': 60 * 60 * 24 * 7
}

server = {
    'domain': open(path['etc'] + 'hostname').read().replace('\n', '')
    if os.path.isfile(path['etc'] + 'hostname')
    else '',
    'address': '',
    'port': 9000,
    'hdd_multiplier': 1024,
}

backup = {
    'cloud_endpoint': 'storage.yandexcloud.net/modhost',
    'cloud_id': 'HJRfGZjJZ40SLgtKXAnn',
    'cloud_key': '1cMpo7k_AOsPUTcBWDdj3zMjlEf1mZN-dB7NRNvq',
    'max_days': '30D',
    'max_full': 4,
    'max_increments': 4,
    'backup_options': '--allow-source-mismatch --volsize=1024 --no-encryption --s3-use-ia',
    'restore_options': '--force --ignore-errors',
    'verify_options': '--force',
    'remove_options': '--force --ignore-errors',
    'mysql_options': '--skip-lock-tables --add-drop-table --skip-comments --force --single-transaction --quick',
}

watchdog = {
    'timeout': 60,
    'receivers': ['bezumkin@yandex.ru'],
    'keep_backups': 1440  # in minutes, e.g. 12 hours
}

actions = []
for item in os.listdir(path['actions']):
    tmp = re.match(r'(.*?)\.py$', item)
    if tmp:
        actions.append(tmp.groups()[0])

logging.basicConfig(
    level=log['level'],
    format=log['format']
)
