FROM daocloud.io/python:3-onbuild

CMD [ "uwsgi", "--ini", "./uwsgi.ini" ]