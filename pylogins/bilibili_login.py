#! /usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'arthur_mao@live.com'
__date__ = '2017-01-29'

import os
import requests
import unittest
from requests.utils import dict_from_cookiejar
import rsa
import base64
from getpass import getpass
import logging

logger = logging.getLogger(__name__)

def prepare(captcha_file=None):
    ''' Get captcha and store in captcha_file
    captcha_file: path to store captcha image
    
    return: session, captcha_img(binary)
    '''
    session = requests.Session()
    session.get('https://passport.bilibili.com/ajax/miniLogin/minilogin')
    
    res = session.get('https://passport.bilibili.com/captcha')
    if captcha_file:
        with open(captcha_file, 'wb') as f:
            f.write(res.content)
        logger.debug('Captcha image has been store on: %s' % captcha_file)
    return session, res.content
    

def login(username, password, captcha, session=None):
    ''' Perform login with given arguments
    username: Your username
    password: Your password
    captcha: Your captcha code. Should run prepare first to get captcha
    session: session with cookies
    
    return: cookies, return_dict.
    '''
    
    if session == None:
        session = requests.Session()
    
    # get HASH and RSA pubkey
    logger.debug('get HASH and RSA pubkey')
    res = session.get('https://passport.bilibili.com/login?act=getkey')
    hash, pubkey = res.json()['hash'], res.json()['key']
    logger.debug('hash: %s, pubkey: %s' % (hash, pubkey))
    
    # encrypt password (RSA+base64)
    pwd = hash + password
    pwd = pwd.encode('utf-8')
    pubkey = rsa.PublicKey.load_pkcs1_openssl_pem(pubkey.encode('utf-8'))
    pwd = rsa.encrypt(pwd, pubkey)
    logger.debug('pwd[RSA]: %s' % (pwd))
    pwd = base64.b64encode(pwd)
    logger.debug('pwd[BASE64]: %s' % (pwd))
    
    # perform login
    res = session.post('https://passport.bilibili.com/ajax/miniLogin/login', data={
        'userid': username,
        'pwd': pwd,
        'captcha': captcha,
        'keep': 1,
    })
    res = res.json()
    if res['status']:
        logger.debug('Success!')
        logger.debug(res)
    else:
        ERROR_MAP = {
            "-105": "验证码错误",
            "-618": "昵称重复或含有非法字符",
            "-619": "昵称不能小于3个字符或者大于30个字符",
            "-620": "该昵称已被使用",
            "-622": "Email已存在",
            "-625": "密码错误次数过多",
            "-626": "用户不存在",
            "-627": "密码错误",
            "-628": "密码不能小于6个字符或大于16个字符",
            "-636": "系统繁忙，稍后再试",
            "-645": "昵称或密码过短",
            "-646": "请输入正确的手机号",
            "-647": "该手机已绑定另外一个账号",
            "-648": "验证码发送失败",
            "-652": "历史遗留问题，昵称与手机号重复，请联系管理员",
            "-662": "加密后的密码已过期"
        }
        logger.error(str(res))
        logger.error(ERROR_MAP[str(res['message']['code'])])
        res['message']['reason'] = ERROR_MAP[str(res['message']['code'])]
        return None, res
    
    cookie = dict_from_cookiejar(session.cookies)
    session.close()
    return cookie, res
    

class TestCases(unittest.TestCase):
    def getlogin(self):
        logging.basicConfig(level=logging.DEBUG)
        captcha_file = input('Path to store captcha image: ')
        session = None
        captcha = None
        while True:
            session, img = prepare(captcha_file)
            captcha = input('Please type captcha(type "retry" to refresh): ')
            if captcha == 'retry':
                session.close()
                continue
            else:
                break
        
        username = input('Username: ')
        password = getpass('Password: ')
        cookies = login(
            username, 
            password, 
            captcha,
            session = session
        )
        if cookies:
            logger.info('Success')
            import json
            with open('/var/tmp/bilibili.login', 'w') as f:
                f.write(json.dumps(cookies))
            logger.info('Cookie file has been stored on /var/tmp/bilibili.login')
            logger.info('Use test case "uselogin" and supply this file to verify.')
        else:
            logger.error('Failed')
        
    def uselogin(self):
        logging.basicConfig(level=logging.DEBUG)
        cookie_file = input('Cookie file path: ')
        import json
        with open(cookie_file, 'r') as f:
            cookies = json.loads(f.read())
        res = requests.get('http://space.bilibili.com/', cookies=cookies)
        import re
        regex = re.search('<title>(.+)的个人空间', res.text)
        if regex:
            username = regex.group(1)
            logger.info('success, login user: %s' % username)
        else:
            logger.error(res.text)
        
if __name__ == '__main__':
    unittest.main()