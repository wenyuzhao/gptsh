import datetime
from agentia.plugins import tool, Plugin
import tzlocal
import rich

from autosh.plugins import banner


class ClockPlugin(Plugin):
    @tool
    def get_current_time(self):
        """Get the current UTC time in ISO format"""
        banner("GET TIME")
        utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        local = datetime.datetime.now().isoformat()
        timezone = tzlocal.get_localzone_name()
        return {
            "utc": utc,
            "local": local,
            "timezone": timezone,
        }
