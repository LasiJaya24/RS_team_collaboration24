# DEM_Extraction_WaterbodyAreas.py 

#Created by Lasinidu Jayarathna (Lasinidu.Jayarathna@rdmw.qld.gov.au) 

# Remote Sensing Team  

# Department of Regional Development, Manufacturing and Water  

# 2/10/2024 

import arcpy 

import os 

import time 

def create_tiles(extent, tile_size): 

    # Function to create a grid of tiles covering the given extent 

    xmin, ymin, xmax, ymax = extent 

    xstep, ystep = tile_size     

    tiles = [] 

    for x in range(int(xmin), int(xmax), xstep): 

        for y in range(int(ymin), int(ymax), ystep): 

            tiles.append((x, y, x + xstep, y + ystep)) 

    return tiles 

def run_model_builder_script(): 

    # Function to run the modelbuilder generated script 

    # Set arcpy environment settings 

    arcpy.env.overwriteOutput = True 

    arcpy.CheckOutExtension("3D") 

    arcpy.CheckOutExtension("spatial")     

    # Set the workspace 

    arcpy.env.workspace = r"C:\projects\Crest DEM Clip\inputs\DEM"     

    # Define Paths 

    DEM = "Queensland DEM.lyrx" 

    WaterStorage = "sample_1" 

    output_folder = r"C:\projects\Crest DEM Clip\inputs\DEM" 

    start_time = time.time()     

    # Define tile size and buffer distance 

    tile_size = (2000, 2000) 

    buffer_distance = "50 Meters"     

    # Get extent of water storage area 

    desc = arcpy.Describe(WaterStorage) 

    extent = desc.extent     

    # Create tiles covering the extent of the water storage area 

    tiles = create_tiles((extent.XMin, extent.YMin, extent.XMax, extent.YMax), tile_size)     

    # List to store paths of extracted DEM tiles 

    dem_tiles = []     

    # Iterate over each tile 

    for i, (xmin, ymin, xmax, ymax) in enumerate(tiles): 

        print(f"Processing Tile {i + 1}/{len(tiles)}...")         

        # Define tile name 

        tile_name = f"Tile_{i}.tif"         

        # Extract DEM within the buffer zone of the tile 

        buffer_file = f"Tile_{i}_Buffer.shp" 

        buffer_file_path = os.path.join(arcpy.env.workspace, buffer_file) 

        print("Buffer file path:", buffer_file_path)  # Print buffer file path         

        # Clip operation 

        try: 

            arcpy.analysis.Buffer(WaterStorage, buffer_file, buffer_distance) 

            arcpy.management.Clip(DEM, buffer_file_path, tile_name) 

            dem_tiles.append(tile_name) 

        except arcpy.ExecuteError as e: 

            print(f"Error clipping DEM for Tile {i}: {e}") 

            continue  # Skip to the next tile     

    # Merge DEM tiles 

    print("Merging DEM tiles....") 

    if dem_tiles: 

        arcpy.management.MosaicToNewRaster(dem_tiles, output_folder, "Merged_DEM1.tif", "", "32_BIT_FLOAT", "", 1, "LAST", "FIRST") 

        print("DEM tiles merged successfully") 

    else: 

        print("No DEM tiles to merge.")     

    # Clean up intermediate files 

    for tile_name in dem_tiles: 

        arcpy.Delete_management(tile_name)     

    print("Contour analysis and additional processing complete") 

    print("Total execution time:", time.time() - start_time) 

if __name__ == '__main__': 

    run_model_builder_script() 
