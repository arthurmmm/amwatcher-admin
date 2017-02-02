#!/usr/bin/env python3
#coding=utf-8
from gevent import monkey
monkey.patch_all()

import os
import time
import logging
import logging.config
import argparse
import hashlib
import requests
import json
import random
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, make_response, jsonify, session, escape, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from pymongo import MongoClient
from redis import StrictRedis
from bson.objectid import ObjectId

import settings
from wechat import reply, receive, handlers
import pylogins.bilibili_login
from modules import User

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)
app.secret_key = ']~\xa1\x81\xe6\xf0\xe9\x1c\x02\xf9\x10\xdb\xa9|%\xb3\xcb(\x95\x0b\xc2\xbe>\x90'

logging.config.dictConfig(settings.LOGGING)
logger = logging.getLogger('__main__')

local = settings.LOCAL_CONFIG

def mongoCollection(cname):
    mongo_client = MongoClient(local['MONGO_URI'])
    mongo_db = mongo_client[local['MONGO_DATABASE']]
    return mongo_db[cname]

redis_db = StrictRedis(
    host=local['REDIS_HOST'], 
    port=local['REDIS_PORT'], 
    password=local['REDIS_PASSWORD'],
    db=local['REDIS_DB']
)

login_session = {}

@login_manager.user_loader
def load_user(user_id):
    logger.debug(user_id)
    mongo_users = mongoCollection('users')
    user_info = mongo_users.find_one({'_id': ObjectId(user_id.decode('utf-8'))})
    logger.debug(user_info)
    return User(user_info)
    
@app.route('/login/', methods=['GET', 'POST'])
def login():
    open_id = request.args.get('open_id', '')
    next = request.args.get('next', url_for('notify', _external=True, title='登陆成功', msg='登陆成功，您可以继续访问其他网页。'))
    mongo_users = mongoCollection('users')
    if not open_id:
        # PIN Login logic
        # Generate a 4-digit pin code
        # Bind pin code with HTML page
        # In HTML page, start rolling checking for pin_login view
        for i in range(10): # Retry 10 times at most
            pin_code = int(random.random() * 1000000)
            pin_code = str(pin_code).zfill(6)
            pin_key = 'amwatcher:admin:pin:%s' % pin_code
            if not redis_db.exists(pin_key):
                break
        else:
            return '错误：找不到可用的PIN码'
        redis_db.setex(pin_key, 125, 'EMPTY') # Expire after 120 sec, add another 5 sec for network delay
        return render_template('login.html', pin_code=pin_code)
        
    user_info = mongo_users.find_one({'open_id': open_id})
    logger.debug(user_info)
    if not user_info:
        return render_template('login.html')
    user = User(user_info)
    login_user(user)
    logger.info('Login success')
    
    return redirect(next)

@app.route('/test/')
def test():
    time.sleep(10)
    return render_template('notify.html', title='测试', msg='测试完成')
    
@app.route('/notify/<title>/<msg>/')
def notify(title, msg):
    return render_template('notify.html', title=title, msg=msg)

@app.route('/pin/<pin_code>/', methods=['GET'])
def pin_login(pin_code):
    ''' accquire by ajax page, getting pin status
    Check redis key, if user send pin code in wechat, open_id will be set on redis
    if key was set, return login page with open_id and redirect to next
    '''
    pin_key = 'amwatcher:admin:pin:%s' % pin_code
    pin_val = redis_db.get(pin_key)
    if not pin_val or pin_val.decode('utf-8') == 'EMPTY':
        return jsonify({'status': False})
    else:
        return jsonify({'status': True, 'open_id': pin_val.decode('utf-8')})
    
@app.route('/captcha_prepare/<source>/<username>/', methods=['GET'])
def captcha_prepare(source, username):
    session, data = pylogins.bilibili_login.prepare()
    login_session[username] = session
    return data

@app.route('/captcha_login/', methods=['GET'])
@login_required
def captcha_login_get():
    logger.debug(current_user.role)
    if not current_user.is_authenticated():
        return render_template('notify.html', title='权限不足', msg='您没有足够的权限浏览该页面')
    mongo_accounts = mongoCollection('accounts')
    accounts = mongo_accounts.find({})
    return render_template('captcha_login.html', accounts=accounts)

@app.route('/captcha_login/', methods=['POST'])
def captcha_login_post():
    mongo_accounts = mongoCollection('accounts')
    data = request.get_data().decode('utf-8')
    data = json.loads(data)
    logger.debug(data)
    if data['username'] not in login_session:
        return jsonify({'status': False, 'message': {'reason': '更换用户名后请刷新验证码'}})
    session = login_session[data['username']]
    cookies, result = pylogins.bilibili_login.login(data['username'], data['password'], data['captcha'], session)
    # Write cookie to mongo
    if cookies:
        logger.debug('Write login to mongo...')
        mongo_accounts.update_one({
            'username': data['username'],
            'source': data['source'],
        }, {
            '$set': {
                'cookies': cookies,
                'update_ts': datetime.now(),
            }
        })
    return jsonify(result)
    
@app.route('/', methods=['GET'])
def wechat_get():
    ''' Token validation logic 
    '''
    timestamp = request.args.get('timestamp', '')
    if not timestamp:
        return 'This page is used for wechat validation'
    signature = request.args.get('signature', '')
    timestamp = request.args.get('timestamp', '')
    nonce = request.args.get('nonce', '')
    echostr = request.args.get('echostr', '')
    token = 'amwatcher'
    
    list = [token, timestamp, nonce]
    list.sort()
    list = ''.join(list).encode('utf-8')
    logger.debug(list)
    hashcode = hashlib.sha1(list).hexdigest()
    logger.info('handle/GET func: hashcode %s, signature %s' % (hashcode, signature))
    if hashcode == signature:
        return echostr
    else:
        return ''
        
@app.route('/', methods=['POST'])
def wechat_post():
    ''' WeChat reply bot
    '''
    data = request.get_data()
    logger.info('Receiving data: %s' % data)
    msg = receive.parse_xml(data)
    chat_handler = handlers.getHandler(msg)
    return chat_handler.reply().format()
            
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=settings.PORT, metavar='PORT')
    parser.add_argument('-a', '--address', default=settings.ADDRESS, metavar='IP_ADDRESS')
    parser.add_argument('--debug', default=False, action='store_true')
    args = parser.parse_args()
    
    app.debug = args.debug
    app.run(host='0.0.0.0', port=5000)