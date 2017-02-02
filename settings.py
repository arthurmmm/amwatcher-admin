import os
import yaml

# read local settings
LOCAL_CONFIG_YAML = '/etc/amwatcher-admin.yml'
with open(LOCAL_CONFIG_YAML, 'r') as f:
    LOCAL_CONFIG = yaml.load(f)

PORT = 5000
ADDRESS = '0.0.0.0'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'class': 'logging.Formatter',
            'format': '%(thread)d %(asctime)s %(levelname)s %(module)s/%(lineno)d: %(message)s',
        },
    },
    'handlers':{
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
        },
        '__main__': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'detailed',
            'filename': '/var/tmp/amwatcher-flask.main.log',
            'maxBytes': 1*1024*1024,
            'backupCount': 10,
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'DEBUG'
        },
        '__main__': {
            'propagate': False,
            'handlers': ['console', '__main__'],
            'level': 'DEBUG'
        },
    },
}