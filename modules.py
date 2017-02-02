#!/usr/bin/env python3
#coding=utf-8

class User(object):
    _id = ''
    display_name = ''
    open_id = ''
    role = ''
    
    def __init__(self, user_info):
        for k,v in user_info.items():
            setattr(self, k, v)
    
    def is_authenticated(self):
        res = (self.role == 'admin')
        return res
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return str(self._id).encode('utf-8')
    def __repr__(self):
        return '<User %s(%s)>' % (self.open_id, self.display_name)