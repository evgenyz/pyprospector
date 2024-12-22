from pyprospector.block import Block

def test_process_output_probe_with_source():
    probe_src_dict = {
        'id': 'test_po_params',
        'title': '...',
        'type': 'probe',
        'kind': 'process_output',
        'parameters': {
            'items': ['1,', '2,', '3']
        },
        'properties': {
            "executable": "/usr/bin/echo",
            "arguments": ['[', '$$items', ']']
        }
    }
    probe_dict = {
        'id': 'test_po_src',
        'title': '...',
        'type': 'probe',
        'kind': 'process_output',
        'sources': ['test_po_params'],
        'properties': {
            "executable": "/usr/bin/echo",
            "arguments": ['{"result": "', '$1', '"}']
        }
    }
    ps = Block.create_from_dict(probe_src_dict)
    p = Block.create_from_dict(probe_dict)
    ps()
    p._sources[0] = ps
    p()
    assert p._result == {'result': ' 1 2 3 '}

def test_process_output_probe_with_parameters():
    probe_dict = {
        'id': 'test_po_params',
        'title': 'Test process_output probe which echoes list of params {"result": [param1, param2, ...]}',
        'type': 'probe',
        'kind': 'process_output',
        'parameters': {
            'items': ['1,', '2,', '3']
        },
        'properties': {
            "executable": "/usr/bin/echo",
            "arguments": ['{"result": [', '$$items', ']}']
        }
    }
    p = Block.create_from_dict(probe_dict)
    assert p is not None
    p()
    assert p._result == {'result': [1, 2, 3]}


def test_process_output_probe():
    probe_dict = {
        'id': 'test_po',
        'title': 'Test process_output probe which echoes {"result": true}',
        'type': 'probe',
        'kind': 'process_output',
        'properties': {
            "executable": "/usr/bin/echo",
            "arguments": ['{"result": true}']
        }
    }
    p = Block.create_from_dict(probe_dict)
    assert p is not None
    p()
    assert p._result == {'result': True}

def test_file_content_probe_auditd_key_value_wrapper():
    probe_dict = {
        'id': 'test_fc_auditd',
        'title': 'Get file content from data/audit.d (using key-value wrapper)',
        'type': 'probe',
        'kind': 'file_content',
        'properties': {
            'paths': ["data/auditd.conf"]
        },
        'wrapper': {
            'key_value': {
                'delimiter': ' = ',
                'quotes': ''
            }
        }
    }
    p = Block.create_from_dict(probe_dict)
    assert p is not None
    p()
    assert p._result == [{
            'file': 'data/auditd.conf',
            'content': {
                'freq': '50',
                'local_events': 'yes',
                'log_file': '/var/log/audit/audit.log',
                'log_format': 'ENRICHED',
                'tcp_client_ports': '1024-65535'
            }
        }
    ]

def test_file_content_probe_etc_os_release_key_value_wrapper():
    probe_dict = {
        'id': 'test_fc_etc_os',
        'title': 'Get file content from data/os-release',
        'type': 'probe',
        'kind': 'file_content',
        'properties': {
            'paths': ["data/os-release"]
        },
        'wrapper': {
            'key_value': {}
        }
    }
    p = Block.create_from_dict(probe_dict)
    assert p is not None
    p()
    assert p._result == [{
        'file': 'data/os-release',
        'content': {
            'NAME': 'Fedora Linux',
            'VERSION': '40 (Workstation Edition)',
            'VERSION_CODENAME': '',
            'ID': 'fedora',
            'VERSION_ID': '40',
            'SUPPORT_END': '2025-05-13'
        }
    }
    ]

def test_file_content_probe_etc_os_release():
    probe_dict = {
        'id': 'test_fc_etc_os',
        'title': 'Get file content from data/os-release',
        'type': 'probe',
        'kind': 'file_content',
        'properties': {
            'paths': ["data/os-release"]
        },
        'wrapper': {
            'regex': {
                'expression': '^(?P<name>[^=]+?)=["]?(?P<value>[^"]*?)["]?$'
            }
        }
    }
    p = Block.create_from_dict(probe_dict)
    assert p is not None
    p()
    assert p._result == [{
                'file': 'data/os-release',
                'content': [
                    {'name': 'NAME', 'value': 'Fedora Linux'},
                    {'name': 'VERSION', 'value': '40 (Workstation Edition)'},
                    {'name': 'ID', 'value': 'fedora'},
                    {'name': 'VERSION_ID', 'value': '40'},
                    {'name': 'VERSION_CODENAME', 'value': ''},
                    {'name': 'SUPPORT_END', 'value': '2025-05-13'}
                ]
            }
        ]

def test_file_content_probe_result_true_json():
    probe_dict = {
        'id': 'test_fc_rtjs',
        'title': 'Get contents from "data/result_true.json" file',
        'type': 'probe',
        'kind': 'file_content',
        'properties': {
            'paths': ["data/result_*.json"]
        }
    }
    p = Block.create_from_dict(probe_dict)
    assert p is not None
    p()
    assert p._result == [{'content': {'result': True}, 'file': 'data/result_true.json'},
                         {'content': {'result': False}, 'file': 'data/result_false.json'}]

def test_file_content_probe_result_true_json_sudo():
    probe_dict = {
        'id': 'test_fc_rtjs',
        'title': 'Get contents from "data/result_true.json" file',
        'type': 'probe',
        'kind': 'file_content',
        'sudo': True,
        'properties': {
            'paths': ["data/result_*.json"]
        }
    }
    p = Block.create_from_dict(probe_dict)
    assert p is not None
    p()
    assert p._result == [{'content': {'result': True}, 'file': 'data/result_true.json'},
                         {'content': {'result': False}, 'file': 'data/result_false.json'}]

def test_auditd_probe():
    probe_dict = {
        'id': 'test_ad',
        'title': '...',
        'type': 'probe',
        'kind': 'audit_rule_files_content',
        'properties': {
            'path': 'data/rules.d/*'
        }
    }
    p = Block.create_from_dict(probe_dict)
    assert p is not None
    p()
    assert p._result == {'config': [['-b 8192'], ['--backlog_wait_time 60000'], ['-f 1']],
                         'rules': [{'fields': ['-F path=/usr/sbin/setsebool',
                                               '-F arch=b64',
                                               '-F perm=x',
                                               '-F auid>=1000',
                                               '-F auid!=unset',
                                               '-F key=privileged'],
                                    'list_action': 'exit,always',
                                    'origin': {'file': 'data/rules.d/11-privileged.rules:1'},
                                    'status': {'correct': False,
                                               'problem': {'field': '-D',
                                                           'file': 'data/rules.d/32-power-abuse.rules:3'}}},
                                   {'fields': ['-F path=/usr/sbin/setsebool',
                                               '-F arch=b32',
                                               '-F perm=x',
                                               '-F auid>=1000',
                                               '-F auid!=unset',
                                               '-F key=privileged'],
                                    'list_action': 'exit,always',
                                    'origin': {'file': 'data/rules.d/11-privileged.rules:2'},
                                    'status': {'correct': False,
                                               'problem': {'field': '-D',
                                                           'file': 'data/rules.d/32-power-abuse.rules:3'}}},
                                   {'fields': ['-F arch=b64',
                                               '-S adjtimex',
                                               '-F auid=unset',
                                               '-F uid=chrony',
                                               '-F subj_type=chronyd_t'],
                                    'list_action': 'exit,never',
                                    'origin': {'file': 'data/rules.d/22-ignore-chrony.rules:2'},
                                    'status': {'correct': False,
                                               'problem': {'field': '-D',
                                                           'file': 'data/rules.d/32-power-abuse.rules:3'}}},
                                   {'fields': ['-S adjtimex',
                                               '-F arch=b32',
                                               '-F auid=unset',
                                               '-F uid=chrony',
                                               '-F subj_type=chronyd_t'],
                                    'list_action': 'exit,never',
                                    'origin': {'file': 'data/rules.d/22-ignore-chrony.rules:3'},
                                    'status': {'correct': False,
                                               'problem': {'field': '-D',
                                                           'file': 'data/rules.d/32-power-abuse.rules:3'}}},
                                   {'fields': ['-F dir=/home',
                                               '-F uid=0',
                                               '-F auid>=1000',
                                               '-F auid!=unset',
                                               '-C auid!=obj_uid',
                                               '-F key=power-abuse'],
                                    'list_action': 'exit,always',
                                    'origin': {'file': 'data/rules.d/32-power-abuse.rules:4'},
                                    'status': {'correct': True}},
                                   {'fields': ['-S openat,open_by_handle_at',
                                               '-F arch=b32',
                                               '-F a2&03',
                                               '-F path=/etc/passwd',
                                               '-F auid>=1000',
                                               '-F auid!=unset',
                                               '-F key=user-modify'],
                                    'list_action': 'exit,always',
                                    'origin': {'file': 'data/rules.d/32-power-abuse.rules:5'},
                                    'status': {'correct': False,
                                               'problem': {'field': '-S precedes -F arch=',
                                                           'file': 'data/rules.d/32-power-abuse.rules:5'}}},
                                   {'fields': ['-F arch=b64',
                                               '-S openat,open_by_handle_at',
                                               '-F a2&03',
                                               '-F path=/etc/passwd',
                                               '-F auid>=1000',
                                               '-F auid!=unset',
                                               '-F key=user-modify'],
                                    'list_action': 'exit,always',
                                    'origin': {'file': 'data/rules.d/32-power-abuse.rules:6'},
                                    'status': {'correct': True}}]}

def test_auditd_probe_single():
    probe_dict = {
        'id': 'test_ad_ar',
        'title': '...',
        'type': 'probe',
        'kind': 'audit_rule_files_content',
        'properties': {
            'path': 'data/audit.rules'
        }
    }
    p = Block.create_from_dict(probe_dict)
    assert p is not None
    p()
    assert p._result == {'config': [],
                         'rules': [{'fields': [],
                                    'list_action': 'task,never',
                                    'origin': {'file': 'data/audit.rules:5'},
                                    'status': {'correct': True}}]}
