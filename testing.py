#!/usr/bin/env python3
"""
A Comparative Analysis of Dijkstra’s and A Algorithms for Smart Flight Pathfinding
- User chooses Direct or Connected flights
- Finds shortest-duration route (Dijkstra + A*), with retry on invalid input
- Displays full VIA path and layover durations
"""

import json, heapq, itertools
from datetime import datetime, timedelta

# ----------------------------------
# Airline mapping
# ----------------------------------
DEFAULT_AIRLINE_NAMES = {
    "AI": "Air India", "SG": "SpiceJet", "UK": "Vistara", "6E": "IndiGo", "G8": "Go First",
    "IX": "Air India Express", "AK": "AirAsia", "QR": "Qatar Airways", "EK": "Emirates",
    "EY": "Etihad Airways", "BA": "British Airways", "LH": "Lufthansa", "TG": "Thai Airways",
    "UL": "SriLankan Airlines", "WY": "Oman Air", "KU": "Kuwait Airways", "TK": "Turkish Airlines",
    "FZ": "Flydubai", "VS": "Virgin Atlantic", "QF": "Qantas", "RJ": "Royal Jordanian",
    "ET": "Ethiopian Airlines", "CX": "Cathay Pacific", "MH": "Malaysia Airlines",
    "SQ": "Singapore Airlines", "H1": "Hahn Air"
}

# ----------------------------------
# Helpers
# ----------------------------------
def get_dep_time(f):
    d = f.get("departure") or f.get("dep") or f.get("from_time")
    if isinstance(d, dict): d = d.get("at")
    return datetime.fromisoformat(d)

def get_arr_time(f):
    a = f.get("arrival") or f.get("arr") or f.get("to_time")
    if isinstance(a, dict): a = a.get("at")
    return datetime.fromisoformat(a)

def travel_duration(dep, arr):
    secs = (arr - dep).total_seconds()
    h, m = divmod(int(secs // 60), 60)
    return f"{h}h {m}m", secs

def format_dur(secs):
    h, m = divmod(int(secs // 60), 60)
    return f"{h}h {m}m"

def airline_name(code, cache):
    return cache.get(code) or DEFAULT_AIRLINE_NAMES.get(code, code)

# ----------------------------------
# Build flight graph
# ----------------------------------
def build_graph(flights):
    g = {}
    for f in flights:
        a, b = f.get("from"), f.get("to")
        if not a or not b:
            continue
        g.setdefault(a, []).append((b, f))
    return g

# ----------------------------------
# Display
# ----------------------------------
def display_itinerary(segs, airline_cache):
    total_price = sum(s.get("price", 0) for s in segs)
    start = get_dep_time(segs[0])
    end = get_arr_time(segs[-1])
    total_time = format_dur((end - start).total_seconds())
    date_str = start.strftime("%Y-%m-%d")

    via = " → ".join(s["from"] for s in segs) + f" → {segs[-1]['to']}"
    via_display = f"VIA {', '.join(s['to'] for s in segs[:-1])}" if len(segs) > 1 else "Direct"

    print(f"📅 Date: {date_str} | 🧭 Total travel (incl. layovers): {total_time} | 💰 ₹{total_price:.0f}")
    print(f"✈️ Route: {via} ({via_display})")
    print("-" * 130)
    print(f"{'Leg':<4}{'From→To':<12}{'Dep':<10}{'Arr':<10}{'Dur':<8}{'Airline':<25}{'Flight':<10}{'Price':<8}")
    print("=" * 130)

    for i, s in enumerate(segs, 1):
        dep, arr = get_dep_time(s), get_arr_time(s)
        dur, _ = travel_duration(dep, arr)
        acode = s.get("carrier") or s.get("marketingCarrier", "NA")
        aname = airline_name(acode, airline_cache)
        flight = s.get("flight_number") or s.get("number") or "N/A"
        print(f"{i:<4}{s['from']}→{s['to']:<8}{dep.strftime('%H:%M'):<10}{arr.strftime('%H:%M'):<10}"
              f"{dur:<8}{aname:<25}{flight:<10}₹{s.get('price',0):<8.0f}")

        if i < len(segs):
            next_dep = get_dep_time(segs[i])
            layover = next_dep - arr
            print(f"{'':4}{'[Layover]':<12}{'':<10}{'':<10}{format_dur(layover.total_seconds()):<8}")
    print("=" * 130 + "\n")

# ----------------------------------
# Pathfinding (Dijkstra + A*)
# ----------------------------------
def heuristic(a, b):
    return 0

def find_connected(all_flights, start, end, date, max_legs=3, min_conn=30, max_conn=480, max_results=6):
    flts = [f for f in all_flights if get_dep_time(f).date() == date]
    g = build_graph(flts)
    pq, results, counter = [], [], itertools.count()
    for _, seg in g.get(start, []):
        dep, arr = get_dep_time(seg), get_arr_time(seg)
        cost = (arr - dep).total_seconds()
        heapq.heappush(pq, (cost, next(counter), seg["to"], [seg]))
    visited = set()
    while pq and len(results) < max_results:
        total_sec, _, curr, path = heapq.heappop(pq)
        state_key = (curr, tuple(s["from"] for s in path))
        if state_key in visited:
            continue
        visited.add(state_key)
        if curr == end and len(path) > 1:
            results.append((total_sec, path))
            continue
        if len(path) >= max_legs:
            continue
        last_arr = get_arr_time(path[-1])
        for nxt, seg in g.get(curr, []):
            if seg in path:
                continue
            dep, arr = get_dep_time(seg), get_arr_time(seg)
            layover_min = (dep - last_arr).total_seconds() / 60
            if layover_min < min_conn or layover_min > max_conn:
                continue
            new_total = (arr - get_dep_time(path[0])).total_seconds() + heuristic(seg["to"], end)
            heapq.heappush(pq, (new_total, next(counter), seg["to"], path + [seg]))
    return sorted(results, key=lambda x: x[0])

def find_direct(all_flights, start, end, date):
    directs = [f for f in all_flights if f["from"] == start and f["to"] == end and get_dep_time(f).date() == date]
    return sorted(directs, key=lambda f: (get_arr_time(f) - get_dep_time(f)).total_seconds())

def best_a_star(all_flights, start, end, date, connected=False):
    flts = [f for f in all_flights if get_dep_time(f).date() == date]
    g = build_graph(flts)
    pq, counter = [], itertools.count()
    if connected:
        for _, seg in g.get(start, []):
            dep, arr = get_dep_time(seg), get_arr_time(seg)
            heapq.heappush(pq, ((arr - dep).total_seconds() + heuristic(seg["to"], end),
                                next(counter), seg["to"], [seg]))
        visited = set()
        while pq:
            total, _, curr, path = heapq.heappop(pq)
            state_key = (curr, tuple(s["from"] for s in path))
            if state_key in visited:
                continue
            visited.add(state_key)
            if curr == end and len(path) > 1:
                return path
            if len(path) >= 3:
                continue
            last_arr = get_arr_time(path[-1])
            for nxt, seg in g.get(curr, []):
                if seg in path:
                    continue
                dep, arr = get_dep_time(seg), get_arr_time(seg)
                layover_min = (dep - last_arr).total_seconds() / 60
                if layover_min < 30 or layover_min > 480:
                    continue
                heapq.heappush(pq, ((arr - get_dep_time(path[0])).total_seconds() + heuristic(seg["to"], end),
                                    next(counter), seg["to"], path + [seg]))
        return None
    else:
        directs = find_direct(all_flights, start, end, date)
        return directs[0] if directs else None

# ----------------------------------
# Input validation with retry
# ----------------------------------
def get_valid_iata(prompt, all_airports):
    while True:
        code = input(prompt).upper()
        if code in all_airports:
            return code
        print("❌ Invalid IATA code. Please try again.")

def get_valid_date(prompt):
    while True:
        try:
            d_str = input(prompt).strip()
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
            return d
        except ValueError:
            print("❌ Invalid date format. Please enter YYYY-MM-DD.")

# ----------------------------------
# MAIN
# ----------------------------------
if __name__ == "__main__":
    cache_path = r"C:\Users\jashn\OneDrive\Desktop\Project\flights_cache.json"
    with open(cache_path, "r", encoding="utf-8") as f:
        all_flights = json.load(f)

    airline_cache = {}
    all_airports = set()
    for f in all_flights:
        c = f.get("carrier") or f.get("marketingCarrier")
        if c and f.get("airline"):
            airline_cache[c] = f["airline"]
        all_airports.add(f["from"])
        all_airports.add(f["to"])

    start = get_valid_iata("From (IATA): ", all_airports)
    end = get_valid_iata("To (IATA): ", all_airports)
    date = get_valid_date("Date (YYYY-MM-DD): ")

    allow_conn = input("Do you want connecting flights? (Y/N): ").upper()

    if allow_conn == "Y":
        results = find_connected(all_flights, start, end, date)
        if results:
            print("\n🏆 BEST CONNECTED OPTION (DIJKSTRA):")
            display_itinerary(results[0][1], airline_cache)

            a_star_best = best_a_star(all_flights, start, end, date, connected=True)
            if a_star_best:
                print("⭐ BEST CONNECTED OPTION (A*):")
                display_itinerary(a_star_best, airline_cache)

            if len(results) > 1:
                print("🪄 Other Available Connected Options:\n")
                for total, segs in results[1:]:
                    display_itinerary(segs, airline_cache)
        else:
            print("❌ No connected routes found.")
    else:
        directs = find_direct(all_flights, start, end, date)
        if directs:
            print("\n🏆 BEST DIRECT OPTION (DIJKSTRA):")
            display_itinerary([directs[0]], airline_cache)

            a_star_best = best_a_star(all_flights, start, end, date, connected=False)
            if a_star_best:
                print("⭐ BEST DIRECT OPTION (A*):")
                display_itinerary([a_star_best], airline_cache)

            if len(directs) > 1:
                print("🪄 Other Available Direct Options:\n")
                for f in directs[1:]:
                    display_itinerary([f], airline_cache)
        else:
            print("❌ No direct flights available for this date.")
