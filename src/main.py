import argparse
import math
import datetime
from collections import UserDict
import sys
import os

import gpxpy
import gpxpy.geo
from garmin_fit_sdk import Decoder, Encoder, Stream, Profile

EARTH_RAD: float = 6378137.0  # Earth radius in meters
EARTH_POLAR_RAD: float = 6356752.0  # Earth polar radius in meters
TRACK_NAME_LENGTH: int = 23
COURSE_POINT_NAME_LENGTH: int = 14
COURSE_POINT_MIN_DISTANCE: int = 1000  # meters


class FileID(UserDict):
    def __init__(self, manufacturer: str = None, product: str = None, time_created: datetime.datetime = None, type: str = None):
        super().__init__()
        self.data['manufacturer'] = manufacturer
        self.data['product'] = product
        self.data['time_created'] = time_created
        self.data['type'] = type

class Course(UserDict):
    def __init__(self, name: str = None, sport: int = None, sub_sport: int = None):
        super().__init__()
        self.data['name'] = name[:TRACK_NAME_LENGTH]
        self.data['sport'] = sport
        self.data['sub_sport'] = sub_sport

class Record(UserDict):
    def __init__(self, position: gpxpy.geo.Location = None, timestamp: datetime.datetime = None, speed: float = None, distance: float = None, position_deg: gpxpy.geo.Location = None):
        super().__init__()
        self.data['timestamp'] = timestamp
        self.data['position'] = position
        self.data['distance'] = round(distance, ndigits=2)
        self.data['speed'] = speed
        self.data['position_deg'] = position_deg
        self.data['position_lat'] = None
        self.data['position_long'] = None
        self.data['altitude'] = None
        if position is not None:
            self.data['position_lat'] = position.latitude
            self.data['position_long'] = position.longitude
            self.data['altitude'] = position.elevation

    @property
    def latitude(self):
        retvalue: float = None
        if self.data['position'] is not None:
            retvalue = self.data['position'].latitude
        return retvalue

    @property
    def longitude(self):
        retvalue: float = None
        if self.data['position'] is not None:
            retvalue = self.data['position'].longitude
        return retvalue

    @property
    def altitude(self):
        retvalue: float = None
        if self.data['position'] is not None:
            retvalue = self.data['position'].elevation
        return retvalue

    @property
    def timestamp(self):
        return self.data['timestamp']

    @property
    def speed(self):
        return self.data['speed']

    @property
    def distance(self):
        return self.data['distance']

    @property
    def position_lat_deg(self):
        retvalue: float = None
        if self.data['position_deg'] is not None:
            retvalue = self.data['position_deg'].latitude
        return retvalue

    @property
    def position_long_deg(self):
        retvalue: float = None
        if self.data['position_deg'] is not None:
            retvalue = self.data['position_deg'].longitude
        return retvalue

    @property
    def position_deg(self):
        return self.data['position_deg']

    @latitude.setter
    def latitude(self, latitude):
        if self.data['position'] is None:
            self.data['position'] = gpxpy.geo.Location(latitude=latitude, longitude=0.0, elevation=0.0)
        else:
            self.data['position'].latitude = latitude
        self.data['position_lat'] = self.data['position'].latitude

    @longitude.setter
    def longitude(self, longitude):
        if self.data['position'] is None:
            self.data['position'] = gpxpy.geo.Location(latitude=0.0, longitude=longitude, elevation=0.0)
        else:
            self.data['position'].longitude = longitude
        self.data['position_long'] = self.data['position'].longitude

    @altitude.setter
    def altitude(self, altitude):
        if self.data['position'] is None:
            self.data['position'] = gpxpy.geo.Location(latitude=0.0, longitude=0.0, elevation=altitude)
        else:
            self.data['position'].elevation = altitude
        self.data['altitude'] = self.data['position'].elevation

    @timestamp.setter
    def timestamp(self, timestamp):
        self.data['timestamp'] = timestamp

    @speed.setter
    def speed(self, speed):
        self.data['speed'] = speed

    @distance.setter
    def distance(self, distance):
        self.data['distance'] = round(distance, ndigits=2)

    @position_lat_deg.setter
    def position_lat_deg(self, position_lat_deg):
        if self.data['position_deg'] is None:
            self.data['position_deg'] = gpxpy.geo.Location(latitude=position_lat_deg, longitude=0.0, elevation=0.0)
        else:
            self.data['position_deg'].latitude = position_lat_deg

    @position_long_deg.setter
    def position_long_deg(self, position_long_deg):
        if self.data['position_deg'] is None:
            self.data['position_deg'] = gpxpy.geo.Location(latitude=0.0, longitude=position_long_deg, elevation=0.0)
        else:
            self.data['position_deg'].longitude = position_long_deg

class Lap(UserDict):
    def __init__(self, records: list[Record] = None, speed: float = None):
        super().__init__()
        elevations = [record.altitude for record in records]
        lats = [record.latitude for record in records]
        longs = [record.longitude for record in records]
        total_ascent, total_descent = gpxpy.geo.calculate_uphill_downhill(elevations)
        self.data['start_time'] = records[0].timestamp
        self.data['timestamp'] = records[0].timestamp
        self.data['start_position_lat'] = records[0].latitude
        self.data['start_position_long'] = records[0].longitude
        self.data['end_position_lat'] = records[-1].latitude
        self.data['end_position_long'] = records[-1].longitude
        self.data['total_ascent'] = total_ascent
        self.data['total_descent'] = total_descent
        self.data['swc_lat'] = min(lats)
        self.data['swc_long'] = min(longs)
        self.data['nec_lat'] = max(lats)
        self.data['nec_long'] = max(longs)
        self.data['total_elapsed_time'] = round(records[-1].distance / speed, ndigits=3)
        self.data['total_timer_time'] = round(records[-1].distance / speed, ndigits=3)
        self.data['total_distance'] = records[-1].distance

class Event(UserDict):
    def __init__(self, timestamp: datetime.datetime = None, event: str = None, event_type: str = None, event_group: int = None):
        super().__init__()
        self.data['timestamp'] = timestamp
        self.data['event'] = event
        self.data['event_type'] = event_type
        self.data['event_group'] = event_group

class EventTimerStart(Event):
    def __init__(self, timestamp: datetime.datetime = None):
        super().__init__(timestamp=timestamp, event='timer', event_type='start', event_group=0)

class EventTimerStop(Event):
    def __init__(self, timestamp: datetime.datetime = None):
        super().__init__(timestamp=timestamp, event='timer', event_type='stop_disable_all', event_group=0)

class CoursePoint(UserDict):
    def __init__(self, record: Record = None, name: str = None, type: str = None, message_index: int = None):
        super().__init__()
        self.data['timestamp'] = None
        self.data['distance'] = None
        self.data['position_lat'] = None
        self.data['position_long'] = None
        if record is not None:
            self.data['timestamp'] = record.timestamp
            self.data['distance'] = record.distance
            self.data['position_lat'] = record.latitude
            self.data['position_long'] = record.longitude
        self.data['name'] = name[:COURSE_POINT_NAME_LENGTH]

        self.data['type'] = type
        self.data['message_index'] = message_index

    @property
    def type(self):
        return self.data['type']

    @property
    def message_index(self):
        return self.data['message_index']

    @type.setter
    def type(self, type):
        self.data['type'] = type

    @message_index.setter
    def message_index(self, message_index):
        self.data['message_index'] = message_index

    def __str__(self):
        return f'{{\'name\': \'{self.data['name']}\', \'distance\': {self.data['distance'] / 1000:.2f}, \'position_lat\': {self.data['position_lat']}, \'position_long\': \'{self.data['position_long']}\', \'timestamp\': \'{self.data['timestamp']}\', \'message_index\': {self.data['message_index']}}}'

def degrees2semicircle(degrees):
    # Convert degrees to semicircle representation(180 * 2^31)
    return gpxpy.geo.Location(
        latitude=round(degrees.latitude / 180 * 0x80000000),
        longitude=round(degrees.longitude / 180 * 0x80000000),
        elevation=degrees.elevation,
    )

def cal_distance_Haversine(point1, point2):
    x1 = math.radians(point1.longitude)
    y1 = math.radians(point1.latitude)
    x2 = math.radians(point2.longitude)
    y2 = math.radians(point2.latitude)
    return EARTH_RAD * math.acos(math.sin(y1) * math.sin(y2) + math.cos(y1) * math.cos(y2) * math.cos(x2 - x1));

def cal_distance_Hubeny(point1, point2):
    phi1 = math.radians(point1.latitude)
    lam1 = math.radians(point1.longitude)
    phi2 = math.radians(point2.latitude)
    lam2 = math.radians(point2.longitude)

    # 緯度・経度の平均
    dphi = phi1 - phi2
    dlam = lam1 - lam2
    mean_phi = (phi1 + phi2) / 2.0

    # 地球楕円体定数（GRS80 / WGS84）
    a = EARTH_RAD                   # 赤道半径 [m]
    # b = 6356752.314140356         # 極半径 [m] (WGS84は 6356752.3142)
    b = EARTH_POLAR_RAD
    e2 = (a**2 - b**2) / (a**2)     # 第一離心率の二乗

    # 子午線曲率半径 M と 卯酉線曲率半径 N
    sin_mean_phi = math.sin(mean_phi)
    W = math.sqrt(1.0 - e2 * (sin_mean_phi**2))
    M = (a * (1.0 - e2)) / (W**3)
    N = a / W

    # 2点間の距離 [m]
    distance = math.sqrt((M * dphi)**2 + (N * math.cos(mean_phi) * dlam)**2)
    return distance

def makefit(course_name: str, records: list[Record], course_points: list[CoursePoint], speed: float):
    '''
    https://developer.garmin.com/fit/cookbook/encoding-course-files/
    Sequencing Course File Messages
    There is an expected message sequence for Course files that should be strictly adhered to. The first message in the file should be a File Id message with the file type set to 6 (Course). The second message in the file is a single Course message with the name and optional sport & sub sport types. A Lap message is required for all Course files and provides additional summary information about the course, including the starting position and overall distance of the course. Record messages are written to the file in chronological ascending order so no message_index is required. The optional Course Point messages provide information about Points Of Interest along the course.

    The sequence of messages for a Course file is:

    File Id [1]
    Course [1]
    Lap [1…n]
    Event Timer Start
    Record [1…n]
    Course Point [0…n]
    Event Timer Stop
    The optional Course Point messages can be grouped together after the Record messages or interleaved with the Record message by timestamp.

    '''

    encoder = Encoder()
    file_id = FileID(
        manufacturer='development',
        product=1,
        time_created=datetime.datetime.now(tz=datetime.timezone.utc),
        type='course',
    )
    encoder.on_mesg(Profile['mesg_num']['FILE_ID'], file_id.data)

    course = Course(
        name=course_name,
        sport=2,
        sub_sport=7
    )
    encoder.on_mesg(Profile['mesg_num']['COURSE'], course.data)

    laps = Lap(records=records, speed=speed)
    encoder.on_mesg(Profile['mesg_num']['LAP'], laps.data)

    event_start = EventTimerStart(timestamp=records[0].timestamp)
    encoder.on_mesg(Profile['mesg_num']['EVENT'], event_start.data)

    for record in records:
        encoder.on_mesg(Profile['mesg_num']['RECORD'], record)

    for counter, course_point in enumerate(course_points):
        course_point.type = 'generic'
        course_point.message_index = counter
        print(f'course_point: {course_point}')
        encoder.on_mesg(Profile['mesg_num']['COURSE_POINT'], course_point.data)

    event_stop = EventTimerStop(timestamp=records[-1].timestamp)
    encoder.on_mesg(Profile['mesg_num']['EVENT'], event_stop.data)

    uint8_array = encoder.close()
    return uint8_array

def gpx2fit(src_file, speed=25.0):

    with open(src_file, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

        print(f'GPX time: {gpx.time}')
        print(f'GPX name: {gpx.name}')
        print(f'track name: {gpx.tracks[0].name}')

        speed_ms = round(speed / (60**2 / 1000), ndigits=3) # km/h -> m/s

        distance: float = 0.
        records: list[Record] = []
        for track in gpx.tracks:
            for segment in track.segments:
                point_prev = None
                for point in segment.points:
                    point_semicircle = degrees2semicircle(point)
                    if point_prev is not None:
                        # distance += round(point_prev.distance_2d(point), ndigits=2)
                        distance = distance + cal_distance_Hubeny(point_prev, point)

                    record = Record(
                        position=point_semicircle,
                        timestamp=gpx.time + datetime.timedelta(seconds=round(distance / speed_ms)),
                        speed=speed_ms,
                        distance=distance,
                        position_deg=point,
                    )
                    records.append(record)
                    point_prev = point

            course_points: list[CoursePoint] = []
            for waypoint in gpx.waypoints:
                min_dist = float("inf")
                for counter, record in enumerate(records):
                    dist = cal_distance_Hubeny(waypoint, record.position_deg)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_counter = counter
                if min_dist <= COURSE_POINT_MIN_DISTANCE:
                    course_points.append(CoursePoint(record=records[nearest_counter], name=waypoint.name))

            uint8_array = makefit(course_name=track.name, records=records, course_points=course_points, speed=speed_ms)
            with open(f'{os.path.join('.', os.path.splitext(os.path.basename(src_file))[0])}.fit', 'wb') as f:
                f.write(uint8_array)
        
def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Convert GPX to FIT Course file.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('src_file', metavar='src_file',
                        help='The source file name(s). JPGIS(GML) DEM zip/xml files.')
    parser.add_argument('-s', '--speed', dest='speed', type=float, default=25.0,
                        help='Speed in km/h (default: 25.0)')

    args = parser.parse_args(argv[1:] if argv else None)

    gpx2fit(args.src_file, speed=args.speed)



if __name__ == "__main__":
    try:
        err = main(sys.argv)
        if err:
            sys.stderr.write(err + "\n")
            sys.exit(1)
        sys.exit(0)
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
