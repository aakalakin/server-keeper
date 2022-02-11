#!/usr/bin/python3

import re
import sys
import os

path = os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + '/'
sys.path.append(path)
import config
import utils

res = utils.run('repquota / | grep \\#')
rows = str(res['message']).split('\n')

for row in rows:
    cols = re.split(r'\s+', row)
    if len(cols) is 9:
        user = cols[0].replace('#', '')
        limit = cols[5]
        if user != '999':
            print(row)
            cmd = 'find {0} -uid {1} -delete 2>/dev/null'.format(config.path['jail'], user)
            print(cmd)
            utils.run(cmd)
