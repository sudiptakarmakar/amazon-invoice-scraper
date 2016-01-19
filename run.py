#!/usr/bin/env python
from __future__ import print_function
from amazon import app
import os

app.secret_key = os.urandom(24)
port = int(os.environ.get('PORT', 5000))

if __name__ == "__main__":
    app.run(debug=True, port=port, host='0.0.0.0')
