import json
import os
import sys
import yaml


def compose_croquis(profile, tests_index, blocks_index):
    if "title" not in profile or \
        "tests" not in profile:
        return

    croquis = {
        "id": profile['id'],
        "title": profile['title'],
        "description": profile['description'],
        "tests": []
    }
    for test in profile['tests']:
        if test in tests_index:
            test_local_ids = {}
            if not tests_index[test].endswith('.yaml'):
                continue
            with (open(tests_index[test]) as f):
                test_obj = {
                    'id': test
                }
                test_obj.update(yaml.safe_load(f))

                for block in test_obj['blocks']:
                    if '/' in block['id']:
                        parent_bid = os.path.basename(block['id'])
                        local_bid = os.path.dirname(block['id'])
                        if parent_bid not in blocks_index:
                            raise ValueError(f'Block "{parent_bid}" not found.')
                        if blocks_index[parent_bid][0] != block['type']:
                            raise ValueError(f'Block "{parent_bid}" is incompatible with child\'s block type "{block['type']}".')
                        with open(blocks_index[parent_bid][1]) as ff:
                            parent_block_obj = yaml.safe_load(ff)
                            bid = block['id'].replace('/', '_')
                            test_local_ids[local_bid] = bid
                            block['id'] = bid
                            block['title'] = parent_block_obj['title']
                            block['kind'] = parent_block_obj['kind']
                            block['properties'] = parent_block_obj['properties']
                            if 'wrapper' in parent_block_obj:
                                block['wrapper'] = parent_block_obj['wrapper']
                            if 'sudo' in parent_block_obj:
                                block['sudo'] = parent_block_obj['sudo']
                    if 'sources' in block:
                        sources = []
                        for src in block['sources']:
                            if src.startswith('@'):
                                sources.append(test_local_ids[src[1:]])
                            else:
                                sources.append(src)
                        block['sources'] = sources

        croquis['tests'].append(test_obj)
    return croquis

def get_profiles(path):
    profiles = []
    if not os.path.isdir(path):
        raise ValueError(f"Invalid profiles directory path: {path}.")
    dir_path, dir_names, files_names = next(os.walk(path))
    for fn in files_names:
        with open(os.path.join(dir_path, fn)) as f:
            profile_obj = yaml.safe_load(f)
            if profile_obj is not None:
                profile_obj['id'] = os.path.splitext(fn)[0]
                profiles.append(profile_obj)
    return profiles

def get_block_ids(path):
    blocks = {}
    if not os.path.isdir(path):
        raise ValueError(f"Invalid blocks directory path: {path}.")
    dir_path, dir_names, files_names = next(os.walk(path))
    for fn in files_names:
        fid = os.path.splitext(fn)[0]
        btyp, bid = os.path.splitext(fid)
        blocks[bid.strip('.')] = (btyp, os.path.join(dir_path, fn))
    return blocks

def get_tests_ids(path):
    tests = {}
    if not os.path.isdir(path):
        raise ValueError(f"Invalid tests directory path: {path}.")
    dir_path, dir_names, files_names = next(os.walk(path))
    for fn in files_names:
        tid = os.path.splitext(fn)[0]
        tests[tid] = os.path.join(dir_path, fn)
    return tests

def main():
    profiles = get_profiles("./profiles")
    tests_index = get_tests_ids("./tests")
    blocks_index = get_block_ids("./blocks")
    for profile in profiles:
        print(f"Building {profile['id']}...")
        cqs = compose_croquis(profile, tests_index, blocks_index)
        with open('artifacts/' + profile['id'] + '.json', 'w', encoding="utf-8") as f:
            json.dump(cqs, f, indent=2)
        for test in cqs['tests']:
            with open('artifacts/' + test['id'] + '.json', 'w', encoding="utf-8") as f:
                json.dump(test, f, indent=2)
    sys.exit(0)


if __name__ == "__main__":
    main()