# DEM_Extraction_BespokePoints.py 

#Created by Lasinidu Jayarathna (Lasinidu.Jayarathna@rdmw.qld.gov.au) 

# Remote Sensing Team  

# Department of Regional Development, Manufacturing and Water  

# 2/10/2024 

import arcpy 

import os 

import time 

def run_model_builder_script(): 

    """ 

    Function to run the ModelBuilder generated script. 

    """ 

    # Set arcpy environment settings 

    arcpy.env.overwriteOutput = True 

    arcpy.CheckOutExtension("3D") 

    arcpy.CheckOutExtension("spatial") 

    # Set the workspace 

    arcpy.env.workspace = r"C:\projects\2RP37125\2RP37125\points\points_new" 

    # Define paths 

    DEM = r"C:\projects\topo_update\DEM.lyrx" 

    BespokePoints = r"C:\projects\2RP37125\2RP37125\points\points_new\points" 

    output_folder = r"C:\projects\2RP37125\2RP37125\points\points_new" 

    start_time = time.time()     

    # Define a list to store paths of individual contour polygon shapefiles 

    contour_polygon_files = [] 

    # Iterate over each point in "BespokePoints" 

    with arcpy.da.SearchCursor(FarmSites, ["OID@", "SHAPE@"]) as cursor: 

        for oid, point in cursor: 

            print(f"Processing point {oid}...") 

            # Create a buffer for the current point 

            buffer_distance = "1000 Meters"  # Adjust as needed 

            Buffer = f"BespokePoints_{oid}.shp" 

            arcpy.analysis.Buffer(in_features=point, out_feature_class=Buffer, buffer_distance_or_field=buffer_distance) 

            # Perform contour analysis 

            Contour_Clip = f"Contours_DEM_Clip_{oid}.shp"  # Modify output name 

            with arcpy.EnvManager(extent=Buffer): 

                contour_result = arcpy.sa.Contour(DEM, f"memory\\contour_temp_{oid}", 0.1, 0, 1, "CONTOUR", None) 

                arcpy.CopyFeatures_management(contour_result, Contour_Clip) 

            # Measure time for getting maximum elevation 

            start_time_get_max_elevation = time.time() 

            max_elevation = max([row[0] for row in arcpy.da.SearchCursor(Contour_Clip, ["Contour"])]) 

            print("Time taken for getting maximum elevation:", time.time() - start_time_get_max_elevation) 

            # Measure time for creating feature layer 

            start_time_create_feature_layer = time.time() 

            arcpy.management.MakeFeatureLayer(FarmSites, "CrestPointLayer") 

            print("Time taken for creating feature layer:", time.time() - start_time_create_feature_layer) 

            # Measure time for Near analysis 

            start_time_near_analysis = time.time() 

            arcpy.analysis.Near(Contour_Clip, "CrestPointLayer", method="GEODESIC") 

            print("Time taken for Near analysis:", time.time() - start_time_near_analysis) 

            # Measure time for geometry check 

            start_time_geometry_check = time.time() 

            arcpy.management.CheckGeometry(Contour_Clip) 

            print("Time taken for geometry check:", time.time() - start_time_geometry_check) 

            # Create a spatial index on contour lines 

            arcpy.management.AddSpatialIndex(Contour_Clip) 

            # Bounding box of the current point 

            start_time_bounding_box = time.time() 

            point_extent = point.extent 

            print("Time taken for bounding box:", time.time() - start_time_geometry_check) 

            # Measure time for contour iteration 

            start_time_contour_iteration = time.time() 

            # Initialize variables to track the highest contour 

            highest_contour = None 

            highest_elevation = float("-inf") 

            # Iterate through contours 

            with arcpy.da.SearchCursor(Contour_Clip, ["SHAPE@", "Contour", "NEAR_DIST"], spatial_reference=point.spatialReference) as contour_cursor: 

                for contour_shape, contour_elevation, near_dist in contour_cursor: 

                    # Quick bounding box check 

                    if not contour_shape.extent.contains(point_extent): 

                        continue 

                    # Check if contour elevation is higher than current highest elevation 

                    if contour_elevation > highest_elevation: 

                        try: 

                            # Convert contour feature to polygon 

                            arcpy.management.FeatureToPolygon([contour_shape], r"memory\ContourPolygon") 

                        except arcpy.ExecuteError as e: 

                            print(f"Error converting contour to polygon: {e}") 

                            continue 

                        # Check if point is inside the polygon 

                        arcpy.management.SelectLayerByLocation("CrestPointLayer", "COMPLETELY_WITHIN", 

                                                               r"memory\ContourPolygon") 

                        if int(arcpy.management.GetCount("CrestPointLayer")[0]) > 0: 

                            highest_contour = {"shape": contour_shape, "Contour": contour_elevation, "near_dist": near_dist} 

                            highest_elevation = contour_elevation 

                            print(f"Current contour elevation: {contour_elevation}") 

                            print(f"Highest elevation so far: {highest_elevation}") 

                    if highest_elevation >= max_elevation: 

                        break 

            print(f"Point {oid} processing complete.") 

            if highest_contour: 

                extracted_info = {"Contour": highest_elevation} 

                print(extracted_info) 

                # Convert contour line to polygon 

                try: 

                    # Define the output polygon feature class path 

                    output_polygon_path = os.path.join(output_folder, f"ContourPolygon_{oid}.shp") 

                    # Convert contour line to polygon and save it in the output folder 

                    arcpy.management.FeatureToPolygon(highest_contour["shape"], output_polygon_path) 

                    contour_polygon_files.append(output_polygon_path) 

                    print("Contour line converted to polygon and saved successfully.") 

                except arcpy.ExecuteError as e: 

                    print(f"Error converting contour to polygon: {e}") 

            # Clean up intermediate files 

            arcpy.Delete_management(Buffer) 

            arcpy.Delete_management(f"memory\\contour_temp_{oid}") 

    print("Contour analysis and additional processing complete.") 

    # Merge all contour polygon shapefiles into a single shapefile 

    output_merged_shapefile = os.path.join(output_folder, "MergedContours2.shp") 

    arcpy.management.Merge(contour_polygon_files, output_merged_shapefile) 

    print("All contour polygons merged successfully into:", output_merged_shapefile) 

    print("Total execution time:", time.time() - start_time) 

if __name__ == '__main__': 

    run_model_builder_script() 
