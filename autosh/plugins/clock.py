import datetime
from agentia.plugins import tool, Plugin
import tzlocal

from autosh.plugins import Banner


class ClockPlugin(Plugin):
    @tool(metadata={"banner": Banner("GET TIME")})
    def get_current_time(self):
        """Get the current UTC time in ISO format"""
        utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        local = datetime.datetime.now().isoformat()
        timezone = tzlocal.get_localzone_name()
        return {
            "utc": utc,
            "local": local,
            "timezone": timezone,
        }
