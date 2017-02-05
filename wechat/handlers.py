# -*- coding: utf-8 -*-

import re
import settings
import logging
from redis import StrictRedis
from pymongo import MongoClient
from flask import url_for

from . import reply, receive

logger = logging.getLogger('__main__')

local = settings.LOCAL_CONFIG
redis_db = StrictRedis(
    host=local['REDIS_HOST'], 
    port=local['REDIS_PORT'], 
    password=local['REDIS_PASSWORD'],
    db=local['REDIS_DB']
)

def mongoCollection(cname):
    mongo_client = MongoClient(local['MONGO_URI'])
    mongo_db = mongo_client[local['MONGO_DATABASE']]
    return mongo_db[cname]

def getHandler(msg):
    hkey = settings.CONTEXT_KEY % msg.FromUserName
    target_handler = redis_db.get(hkey)
    if target_handler:
        target_handler = target_handler.decode('utf-8')
        logger.debug(globals())
        hcls = globals()[target_handler]
    else:
        hcls = RootHandler
    return hcls(msg)

class Handler(object):
    router = {}
    
    def __init__(self, msg):
        self.msg = msg
        self.msg_type = msg.MsgType
        self.to_user = msg.FromUserName
        self.from_user = msg.ToUserName
        self.hkey = settings.CONTEXT_KEY % self.to_user
        if isinstance(msg, receive.TextMsg):
            self.router_key = msg.Content.decode('utf-8')
        elif isinstance(msg, receive.EventMsg):
            self.router_key = msg.Event.decode('utf-8')
        else:
            self.router_key = 'default'
    
    def reply(self):
        router = self.router[self.msg_type]
        for pattern, fname in router:
            regex = re.compile(pattern)
            if regex.match(self.router_key):
                func = getattr(self, fname)
                reply_msg = func()
                break
        else:
            reply_msg = self.default_reply()
        logger.debug(reply_msg.format())
        return reply_msg
            
    def default_reply(self):
        return reply.TextMsg(
            self.to_user, 
            self.from_user, 
            'Error!'
        )

class RootHandler(Handler):
    router = {
        'text': [
            ('^[\?\？]$', 'show_help'),
            ('^[!！]$', 'get_status'),
            ('^登陆$', 'set_logins'),
            ('^\d{6}$', 'pin_login')
        ],
        'event': [
            ('^subscribe$', 'active_user'),
            ('^unsubscribe$', 'deactive_user'),
        ],
    }
    
    def default_reply(self):
        return self.show_help()
        
    def show_help(self):
        return reply.TextMsg(
            self.to_user, 
            self.from_user, 
            'Hello~'
        )
    
    def get_status(self):
        return reply.TextMsg(
            self.to_user, 
            self.from_user, 
            'Hey~'
        )
    
    def set_logins(self):
        captcha_url = url_for('login', _external=True)
        captcha_url += '?open_id=%s&next=%s' % (self.to_user, url_for('captcha_login_get', _external=True))
        return reply.NewsMsg(
            self.to_user, 
            self.from_user, 
            [{'title': '机器人登陆', 'description': '', 'url': captcha_url}],
        )
        
    def pin_login(self):
        pin_key = settings.PIN_KEY % self.router_key
        pin_val = redis_db.get(pin_key)
        if not pin_val:
            return reply.TextMsg(
                self.to_user, 
                self.from_user, 
                '您输入的PIN码不存在',
            )
        else:
            redis_db.setex(pin_key, 30, self.to_user)
            return reply.TextMsg(
                self.to_user, 
                self.from_user, 
                '登陆成功！浏览器将自动跳转。',
            )
            
    def active_user(self):
        mongo_user = mongoCollection('users')
        res = mongo_user.update({
            'open_id': self.to_user,
        },{
            '$set': {
                'active': True,
                'open_id': self.to_user,
            }
        }, upsert=True)
        user_exists = res['updatedExisting']
        if user_exists:
            return reply.TextMsg(
                self.to_user, 
                self.from_user, 
                '欢迎回来！',
            )
        else:
            return reply.TextMsg(
                self.to_user, 
                self.from_user, 
                '感谢关注！',
            )
    
    def deactive_user(self):
        mongo_user = mongoCollection('users')
        mongo_user.update({
            'open_id': self.to_user,
        },{
            '$set': {
                'active': False,
            }
        })
        return reply.TextMsg(
            self.to_user, 
            self.from_user, 
            'See you',
        )