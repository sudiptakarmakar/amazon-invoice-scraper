import flask

app = flask.Flask(__name__)
app.config.from_object(__name__)
# app.config.from_envvar('FLASKR_SETTINGS', silent=True)
jinja_options = app.jinja_options.copy()
jinja_options.update(dict(
    block_start_string="<%",
    block_end_string="%>",
    variable_start_string="%%",
    variable_end_string="%%",
    comment_start_string="<#",
    comment_end_string="#>",
))
app.jinja_options = jinja_options

from . import view
# from . import view_api
