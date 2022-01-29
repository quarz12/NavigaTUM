import json
import math
import copy

import utm


def assign_coordinates(data):
    """
    Assign coordinates to all entries (except root) and make sure they match the data format.
    """
    # TODO: In the future we might calculate the coordinates from OSM data
    
    # The inference of coordinates in this function for all entries is based on the
    # coordinates of buildings, so it is necessary, that at least all buildings have
    # a coordinate.
    buildings_without_coord = set()
    for _id, entry in data.items():
        if entry["type"] == "building":
            if "coords" not in entry:
                buildings_without_coord.add(entry["id"])
    if len(buildings_without_coord) > 0:
        print(f"Error: No coordinates known for the following buildings: "
              f"{buildings_without_coord}")
        exit(1)
    
    # All errors are collected first before quitting in the end if any
    # error occured.
    error = False
    
    for _id, entry in data.items():
        if entry["type"] == "root":
            continue
        
        if "coords" in entry:
            # While not observed so far, coordinate values of zero are typical for missing
            # data so we check this here.
            if entry["coords"].get("lat", None) == 0. or entry["coords"].get("lon", None) == 0.:
                print(f"Error: Lat and/or lon coordinate is zero for '{_id}': "
                      f"{entry['coords']}")
                error = True
                continue
            if "utm" in entry["coords"] \
               and (   entry["coords"]["utm"]["easting"]  == 0.
                    or entry["coords"]["utm"]["northing"] == 0.):
                print(f"Error: UTM coordinate is zero for '{_id}': "
                      f"{entry['coords']}")
                error = True
                continue
            
            # Convert between utm and lat/lon if necessary
            if "utm" not in entry["coords"]:
                utm_coord = utm.from_latlon(entry["coords"]["lat"], entry["coords"]["lon"])
                entry["coords"]["utm"] = {
                    "zone_number": utm_coord[2],
                    "zone_letter": utm_coord[3],
                    "easting": utm_coord[0],
                    "northing": utm_coord[1],
                }
            if "lat" not in entry["coords"]:
                utm_coord = entry["coords"]["utm"]
                latlon_coord = utm.to_latlon(utm_coord["easting"], utm_coord["northing"],
                                             utm_coord["zone_number"], utm_coord["zone_letter"])
                entry["coords"]["lat"] = latlon_coord[0]
                entry["coords"]["lat"] = latlon_coord[1]
            
            # If no source is provided, "navigatum" is assumed because Roomfinder
            # provided coordinates will have "roomfinder" set.
            if "source" not in entry["coords"]:
                entry["coords"]["source"] = "navigatum"
        else:
            # For rooms we check whether its parent has a coordinate
            if entry["type"] in {"room", "virtual_room"}:
                building_parent = list(filter(lambda e: data[e]["type"] == "building",
                                              entry["parents"]))
                if len(building_parent) != 1:
                    print(f"Error: Could not find distinct parent building for {_id}")
                    error = True
                    continue
                building_parent = data[building_parent[0]]
                
                # Copy probably not required, but this could avoid unwanted side effects
                entry["coords"] = copy.deepcopy(building_parent["coords"])
                entry["coords"]["accuracy"] = "building"
                entry["coords"]["source"] = "inferred"
            elif entry["type"] in {"site", "area", "campus", "joined_building"}:
                # Calculate the average coordinate of all children buildings
                # TODO: garching-interims
                if "children_flat" not in entry:
                    print(f"Error: Cannot infer coordinate of '{_id}' because it has no children")
                    error = True
                    continue
                
                lats, lons = ([], [])
                for c in entry["children_flat"]:
                    if data[c]["type"] == "building":
                        lats.append(data[c]["coords"]["lat"])
                        lons.append(data[c]["coords"]["lon"])
                lat_coord = sum(lats) / len(lats)
                lon_coord = sum(lons) / len(lons)
                utm_coord = utm.from_latlon(lat_coord, lon_coord)
                entry["coords"] = {
                    "lat": lat_coord,
                    "lon": lon_coord,
                    "utm": {
                        "zone_number": utm_coord[2],
                        "zone_letter": utm_coord[3],
                        "easting": utm_coord[0],
                        "northing": utm_coord[1],
                    },
                    "source": "inferred"
                }
            else:
                print(f"Error: Don't know how to infer coordinate for entry type '{entry['type']}'")
                error = True
                continue
    
    if error:
        print("Aborting due to errors")
        exit(1)
                


def assign_roomfinder_maps(data):
    """
    Assign roomfinder maps to all entries if there are none yet specified.
    """
    # Read the Roomfinder maps
    with open("external/maps_roomfinder.json") as f:
        maps_list = json.load(f)
    
    world_map = None
    for m in maps_list:
        if m["id"] == 9:  # World map is not used
            world_map = m
        else:
            m["latlonbox"]["north"] = float(m["latlonbox"]["north"])
            m["latlonbox"]["south"] = float(m["latlonbox"]["south"])
            m["latlonbox"]["east"] = float(m["latlonbox"]["east"])
            m["latlonbox"]["west"] = float(m["latlonbox"]["west"])
    maps_list.remove(world_map)
    
    for _id, entry in data.items():
        if entry["type"] == "root":
            continue
        
        if len(entry.get("maps", {}).get("roomfinder", {}).get("available", [])) > 0:
            continue
        
        # Use maps from parent building, if the is no precise coordinate known
        if entry["type"] in {"room", "virtual_room"} and \
           entry["coords"]["accuracy"] == "building":
            building_parent = list(filter(lambda e: data[e]["type"] == "building",
                                            entry["parents"]))
            # Verification of this already done for coords, see above
            building_parent = data[building_parent[0]]
            
            if len(building_parent.get("maps", {})
                                  .get("roomfinder", {})
                                  .get("available", [])) == 0:
                roomfinder_map_data = {"is_only_building": True}
                # Both share the reference now, assuming that the parening_parent
                # will be processed some time later in this loop.
                building_parent.setdefault("maps", {})["roomfinder"] = roomfinder_map_data
                entry.setdefault("maps", {})["roomfinder"] = roomfinder_map_data
            else:
                # TODO: 5510.02.001
                roomfinder_map_data = entry.setdefault("maps", {}).get("roomfinder", {})
                roomfinder_map_data.update(building_parent["maps"]["roomfinder"])
                roomfinder_map_data["is_only_building"] = True
            
            continue
        
        # TODO: Sort & unique
        available_maps = []
        lat_coord, lon_coord = (entry["coords"]["lat"], entry["coords"]["lon"])
        for m in maps_list:
            # Assuming coordinates in Central Europe
            if m["latlonbox"]["south"] < lat_coord < m["latlonbox"]["north"] and \
               m["latlonbox"]["west"]  < lon_coord < m["latlonbox"]["east"]:
                available_maps.append(m)
        
        # For entries of these types only show maps that contain all (direct) children.
        # This is to make sure that only (high scale) maps are included here that make sense.
        # TODO: zentralgelaende
        if entry["type"] in {"site", "campus", "area", "joined_building", "building"} \
           and "children" in entry:
            exclude_maps = []
            for m in available_maps:
                for c in entry["children"]:
                    lat_coord, lon_coord = (data[c]["coords"]["lat"], data[c]["coords"]["lon"])
                    if not (m["latlonbox"]["south"] < lat_coord < m["latlonbox"]["north"] and
                            m["latlonbox"]["west"]  < lon_coord < m["latlonbox"]["east"]):
                        exclude_maps.append(m)
                        break
            for m in exclude_maps:
                available_maps.remove(m)
        
        if len(available_maps) == 0:
            print(f"Warning: No Roomfinder maps available for '{_id}'")
            continue
        
        # Select map with lowest scale as default
        default_map = available_maps[0]
        for m in available_maps:
            if int(m["scale"]) < int(default_map["scale"]):
                default_map = m
        
        roomfinder_map_data = {
            "default": default_map["id"],
            "available": [
                {
                    "id":     m["id"],
                    "scale":  m["scale"],
                    "name":   m["desc"],
                    "width":  m["width"],
                    "height": m["height"],
                }
                for m in available_maps
            ],
        }
        entry.setdefault("maps", {})["roomfinder"] = roomfinder_map_data
    

def build_roomfinder_maps(data):
    """ Generate the map information for the Roomfinder maps. """
    
    # Read the Roomfinder maps
    with open("external/maps_roomfinder.json") as f:
        maps_list = json.load(f)
    
    # For each map, we calculate the boundaries in UTM, because 
    maps = {}
    for m in maps_list:
        if "latlonbox" in m:
            latlonbox = m["latlonbox"]
            
            zones_n = set()
            zones_letter = set()
            
            latlonbox["north_west"] = (float(latlonbox["north"]), float(latlonbox["west"]))
            latlonbox["south_east"] = (float(latlonbox["south"]), float(latlonbox["east"]))
            
            maps[m["id"]] = m

    for _id, entry in data.items():
        if len(entry.get("maps", {}).get("roomfinder", {}).get("available", [])) > 0:
            world_map = None
            for entry_map in entry["maps"]["roomfinder"]["available"]:
                # The world map (id 9) is currently excluded, because it would need a different
                # projection treatment.
                if entry_map["id"] == 9:
                    world_map = entry_map
                    continue
                
                m = maps[entry_map["id"]]
                box = m["latlonbox"]
                
                # For the map regions used we can assume that the lat/lon graticule is
                # rectangular within that map. It is however not square (roughly 2:3 aspect),
                # so for simplicity we first map it into the cartesian pixel coordinate
                # system of the image and then apply the rotation.
                # Note: x corrsp. to longitude, y corresp. to latitude
                ex, ey = (entry["coords"]["lon"],
                          entry["coords"]["lat"])
                
                box_delta_x = abs(box["north_west"][1] - box["south_east"][1])
                box_delta_y = abs(box["north_west"][0] - box["south_east"][0])
                
                rel_x, rel_y = (abs(box["north_west"][1] - ex) / box_delta_x,
                                abs(box["north_west"][0] - ey) / box_delta_y)
                
                ix0, iy0 = (rel_x * entry_map["width"],
                            rel_y * entry_map["height"])
                
                cx, cy = (entry_map["width"] / 2,
                          entry_map["height"] / 2)
                
                angle = math.radians(float(box["rotation"]))
                ix, iy = (cx + (ix0-cx)*math.cos(angle) - (iy0-cy)*math.sin(angle),
                          cy + (ix0-cx)*math.sin(angle) + (iy0-cy)*math.cos(angle))
                
                # The result is the position of the pixel in this image corresponding
                # to the coordinate.
                entry_map["x"] = round(ix)
                entry_map["y"] = round(iy)
            
            if world_map is not None:
                entry["maps"]["roomfinder"]["available"].remove(world_map)
            

