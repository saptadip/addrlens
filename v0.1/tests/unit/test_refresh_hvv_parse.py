"""Pure-parser tests for refresh_hvv — no network."""
import io

from scripts.refresh_hvv import (
    _classify_su_mode, _extract_stops_for_route_types, _peak_only_from_calendar,
)


def test_classify_su_mode_s_only():
    assert _classify_su_mode({"S1"}) == "S"


def test_classify_su_mode_u_only():
    assert _classify_su_mode({"U3"}) == "U"


def test_classify_su_mode_combined():
    assert _classify_su_mode({"S1", "U3"}) == "S+U"


def test_extract_stops_by_route_type_filters_ferry():
    stops_txt = ("stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
                 "1,Landungsbrücken,53.5459,9.9683,1,\n"
                 "2,Airbus,53.5300,9.8500,1,\n")
    routes_txt = ("route_id,route_type,route_short_name\n"
                  "62,4,Fähre 62\n"
                  "68,4,Fähre 68\n")
    trips_txt = "route_id,trip_id,service_id\n62,t1,d1\n68,t2,d2\n"
    stop_times_txt = ("trip_id,stop_id,stop_sequence\n"
                      "t1,1,1\nt2,2,1\n")
    stops = _extract_stops_for_route_types(
        stops_csv=stops_txt, routes_csv=routes_txt,
        trips_csv=trips_txt, stop_times_csv=stop_times_txt,
        route_types={"4"},
    )
    names = {s["name"] for s in stops}
    assert names == {"Landungsbrücken", "Airbus"}


def test_peak_only_detects_weekday_only_service():
    calendar_txt = ("service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday\n"
                    "d_peak,1,1,1,1,1,0,0\n"
                    "d_allday,1,1,1,1,1,1,1\n")
    assert _peak_only_from_calendar(calendar_txt, "d_peak") is True
    assert _peak_only_from_calendar(calendar_txt, "d_allday") is False
