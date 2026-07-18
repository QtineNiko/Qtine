import atexit
import os

from qtine.core.app import QtineApp

os.environ["QTINE_MANAGED_SERVER"] = "1"
qtine = QtineApp(os.environ.get("QTINE_CONFIG_FILE", "config.yml"))
qtine.bot.start()
atexit.register(qtine.shutdown)
application = qtine.flask_app
