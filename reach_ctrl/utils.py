from datetime import datetime
from time import sleep, time
import logging
import serial
import sched
import ephem
import glob
import sys


def list_serial_ports():
    """ Lists serial port names
        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


def get_sidereal_time(longitude, latitude, date_time=None):
    """ Calculate current sidereal time at givel location """

    # Create observer at required position
    loc = ephem.Observer()
    loc.lon, loc.lat = longitude, latitude

    # Assign current or provided time
    if date_time is None:
        loc.date = datetime.utcnow()
    else:
        loc.date = datetime.fromtimestamp(date_time)

    # Return sidereal time
    return ephem.degrees(loc.sidereal_time()) / ephem.degree


def schedule_utc(date_time):
    """ Wait for the specified number of seconds to elapse """

    # If date_time is "now", then return immediately
    if date_time.upper() == "now":
        return

    # Format input date_time as required
    date_time = datetime.strptime(date_time, "%d/%m/%Y_%H:%M")
    start_time = datetime.fromtimestamp(int(time()))

    # Check for how long we have to wait
    total_seconds = (date_time - start_time).total_seconds()

    # Sanity check
    if total_seconds <= 5:
        logging.warning("Cannot schedule before 5 seconds in the future. Ignoring schedule")
        return

    # Wait for the required duration
    s = sched.scheduler(time, sleep)
    s.enter(total_seconds, 0, lambda: None, [])
    s.run()


def schedule_lst(date_time):
    """ Wait for the specified number of seconds to elapse """

    logging.warning("LST scheduling is not supported yet. Ignoring")

    # # If date_time is "now", then return immediately
    # if date_time.upper() == "now":
    #     return

    # # The time provided for LST is split into two: Date in UTC, time in LST
    # # First we wait for the date
    # utc_date, lst_time = date_time.split('_')
    # utc_date = datetime.strptime(utc_date, "%d/%m/%Y")

    # # While date not reached, sleep
    # while True:
    #     # Get current date
    #     current_date = datetime.utcnow()
    #     current_date = datetime(year=current_date.year, month=current_date.month, day=current_date.day)

    #     # If required date is in the past, ignore
    #     if current_date > utc_date:
    #         logging.error("Required date has elapsed, ignoring schedule")
    #         return

    #     # If required and current date are the same, break loop
    #     elif current_date == utc_date:
    #         break

    #     # Otherwise, wait for a while and repeat
    #     else:
    #         sleep(5)

    # # Required and current date are the same, wait for required time
    # lst_hour, lst_minute = lst_time.split(":")


def schedule(date_time, mode):
    """ Wait for specified time, with required mode """
    if mode == "UCT":
        schedule_utc(date_time)
    elif mode == "LST":
        schedule_lst(date_time)
    else:
        logging.error("Scheduling mode {} is not supported, ignoring".format(mode))


if __name__ == "__main__":
    # print(get_sidereal_time(25, 25))
    print(list_serial_ports())
