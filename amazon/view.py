from __future__ import print_function
import flask
from . import invoice
from . import app


@app.route('/')
def index():
    return flask.render_template('index.html', title='Home')


@app.errorhandler(404)
def page_not_found(e):
    return flask.render_template('404.html'), 404
