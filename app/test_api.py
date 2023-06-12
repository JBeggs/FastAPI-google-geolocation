import json

import os
import os.path

from dotenv import load_dotenv

from fastapi.testclient import TestClient

from main import app

load_dotenv()


# Meat and bones of the two tests
def process_request(client, auth_url, api_url, json_data):
    access_token = client.post(
        auth_url,
        data={
            'username': os.environ.get('username'),
            'password': os.environ.get('password')
        },
    )

    token = json.loads(access_token.content)
    headers = {
        "content-type": "application/json",
        "Authorization": f'Bearer {token["access_token"]}',
    }

    response = client.post(
        api_url,
        headers=headers,
        json=json_data
    )

    return response


# Check the API to make sure cache is working or not
def test_api_no_cache():

    api_url  = "/api/v1"
    auth_url = "/api/v1/auth/token"
    client   = TestClient(app)

    root_response = client.get(
        '/',
        params={'message' : 'working'}
    )
    assert root_response.status_code == 200

    with open('scan.json') as json_file:
        test_json = json.loads(json_file.read())

    stats = {
        'cached'   : 0,
        'uncached' : 0,
    }

    for test_data in test_json:

        # NB enable instant expire on cache with this key
        test_data['ttl'] = 0
        request_response = process_request(client, auth_url, api_url, test_data)
        json_content     = json.loads(request_response.content)
        if 'cached' in json_content:
            if json_content['cached']:
                stats['cached'] += 1
            else:
                stats['uncached'] += 1
            assert request_response.status_code == 200
        else:
            assert request_response.status_code == 429
    assert stats['cached'] == 0
    assert stats['uncached'] == 1604


def test_api_cache():

    api_url  = "/api/v1"
    auth_url = "/api/v1/auth/token"
    client   = TestClient(app)

    root_response = client.get(
        '/',
        params={'message' : 'working'}
    )
    assert root_response.status_code == 200

    with open('scan.json') as json_file:
        test_json = json.loads(json_file.read())

    stats = {
        'cached'   : 0,
        'uncached' : 0,
    }

    for test_data in test_json:
        request_response = process_request(client, auth_url, api_url, test_data)
        json_content = json.loads(request_response.content)
        if 'cached' in json_content:
            if json_content['cached']:
                stats['cached'] += 1
            else:
                stats['uncached'] += 1
            assert request_response.status_code == 200
        else:
            assert request_response.status_code == 429

    assert stats['cached'] == 1563
    assert stats['uncached'] == 41

