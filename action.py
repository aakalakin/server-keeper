#!/usr/bin/python3

import re
import sys
import config
import utils
sys.path.append(config.path['actions'])
import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def action(command):
    actions = config.actions

    if isinstance(command, str):
        command = re.sub(r'\s+', ' ', command).split(' ')

    user, act = ('','')
    if isinstance(command, dict):
        if 'user' in command:
            user = command['user']
            del(command['user'])
        if 'action' in command:
            act = command['action']
            del(command['action'])
    else:
        act = command[0] if len(command) > 0 else ''
        user = command[1] if len(command) > 1 else ''
        command = command[2:]

    if not act:
        return utils.failure('You must specify action from list: "{}"'.format(', '.join(actions)))
    elif act not in actions:
        return utils.failure(
            'Unknown action "{0}". You must specify action from list: "{1}".'.format(act, ', '.join(actions))
        )
    else:
        cls = act[0].upper() + act[1:]

    # For localhost debug
    """
    if act in ['create', 'remove', 'resize', 'duplicate']:
        import time
        time.sleep(1.1)
    """
    # --

    if user == '':
        return utils.failure('You must specify the user of the site')

    processor = getattr(__import__('actions.' + act, fromlist=[cls]), cls)
    res = processor(user, command).process()

    return res


if __name__ == "__main__":
    params = sys.argv[1:]
    if len(params) and params[0][0] == '{':
        import json
        params = json.loads(params[0])

    result = action(params)
    if result['message']:
        print(result['message'].encode('utf-8'))
    else:
        if result['success']:
            print('Success')
        else:
            print('Failure')
    if 'data' in result:
        print(result['data'])