import os
import time

import requests
import uvicorn

from cachetools import TTLCache

from dotenv import load_dotenv

from expiring_dict import ExpiringDict

from fastapi import FastAPI ,Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_login.exceptions import InvalidCredentialsException
from fastapi_login import LoginManager

from json import JSONDecodeError

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler as rate_handler
from slowapi import Limiter
from slowapi.util import get_remote_address

from starlette.requests import Request

from typing import Annotated

# Configs

load_dotenv()

# Username and password for security
user_db = {
    os.environ.get('username') : {
        'password' : os.environ.get('password')
    }
}

# User login manager
manager = LoginManager(
    os.environ.get('SECRET'),
    token_url  = '/auth/token',
    use_cookie = True
)

# Setup Cache, whole cache expire after a year
# Item cache expires after 30 days
one_year     = 60*60*24*365
cache        = TTLCache(maxsize=200, ttl=one_year)
thirty_days  = 60*60*24*30
cache_expire = ExpiringDict(thirty_days)

# Rate limiter to never reach google API limit
limiter           = Limiter(key_func=get_remote_address)


# Default error messages
message = 'FAILURE'
error   = 'Only JSON Objects valid'
# Always False, please don't touch
test    = False

app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_handler)


# API Health status, returns SUCCESS and anything from the request
@app.get("/")
async def root(request: Request):

    global message
    global error

    # This is ugly but I want to ensure the root is
    # assessable by as many POST's as possible

    try:
        request        = await request.json()
        message, error = 'SUCCESS', ''
    except JSONDecodeError as Error:
        message = 'FAILURE'
        error   = Error.__str__()

    return {
        "status"   : message,
        "response" : error if error else request,
    }


@manager.user_loader()
def load_user(email: str):
    return user_db.get(email)


# User login to get token
# the python-multipart package is required to use the OAuth2PasswordRequestForm
@app.post('/api/v1/auth/token')
def login(data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    email    = data.username
    password = data.password
    user     = load_user(email)

    if not user:
        raise InvalidCredentialsException
    elif password != user['password']:
        raise InvalidCredentialsException

    access_token = manager.create_access_token(
        data = dict(sub=email)
    )

    return {
        'access_token' : access_token,
        'token_type'   : 'bearer'
    }


# On POST we setup rate limit
@app.post("/api/v1")
@limiter.limit("45/second")
async def root(request: Request):

    global message
    global error
    global test
    global cache_expire

    #  When we test, we can't hit google api
    if 'http://testserver/' in request.base_url.__str__():
        test = True

    # This Route only accepts json
    if 'application/json' in request.headers['content-type']:
        try:
            request        = await request.json()
            message, error = '', ''
        except JSONDecodeError as Error:
            message = 'FAILURE'
            error   = Error

    # Anything other than json gets rejected
    if message and error:
        return {
            "status" : message,
            "error"  : error,
        }

    return process_request(request)


def process_request(request):

    global test

    # Let's ensure we have the right data and type to continue
    if type(request) == dict \
            and 'apscan_data' in request:

        time.sleep(0.02)
        # I rebuild the apscan_data to just include mac addresses
        # Create list of mac addresses for cache key
        apscan_data = {'apscan_data': []}
        ap_list     = []
        for item in request['apscan_data']:
            ap_list.append(item['bssid'])
            apscan_data['apscan_data'].append({'macAddress': item['bssid']})

        # Sort the ap_list so that the keys are always the same
        # Get the cache key
        ap_list        = sorted(ap_list, key=lambda i: i)
        cache_key      = '.'.join(ap_list)

        # check cache
        cache_response = cache.get(cache_key)

        if not cache_response:

            # send geolocation service
            geolocation_response = request_geolocation(apscan_data, test)

            if geolocation_response:

                # Build the cache with response from Google's geolocations
                cache_expire[cache_key] = geolocation_response

                # If we are testing
                if test:
                    # Check if TTL is being set for the test
                    # and enable the correct cache, either normal or expires after 1 sec
                    if 'ttl' in request:
                        cache[cache_key] = cache_expire.ttl(cache_key, 'expired', request['ttl'])
                    else:
                        cache[cache_key] = cache_expire[cache_key]
                    geolocation_response['cached'] = False
                else:
                    # Not testing, let's build the cache
                    cache[cache_key] = cache_expire[cache_key]

                return geolocation_response
        else:
            # Testing description
            if test:
                cache_response['cached'] = True

            return cache_response

    # If we got here something went wrong with the geolocation services
    return {
        "status" : "FAILURE",
        "error"  : 'No geolocation Data from google'
    }


def request_geolocation(json, test):

    # Testing skips unwanted calls
    if not test:
        request = requests.post(
            os.environ.get('google-maps-url-json'),
            json=json
        )
        response = request.json()
    else:
        # return same data for testing
        response = {
            "location": {
                "lat": -26.2707593,
                "lng": 28.1122679
            },
            "accuracy": 1
        }

    # Check that we have the location
    if response.get('location'):
        return response
    else:
        # Or return None
        return None


if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host          = "0.0.0.0",
        port          = 8000,
        log_level     = "debug",
        proxy_headers = True,
        reload        = True,
        lifespan      = 'off'
    )
