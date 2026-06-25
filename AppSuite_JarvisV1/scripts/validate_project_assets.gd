@tool
extends SceneTree

func _init():
	print("--- STARTING GODOT RUNTIME VALIDATOR ---")
	var report = {
		"status": "success",
		"main_scene_loaded": false,
		"mesh_instances_count": 0,
		"meshes": [],
		"materials": [],
		"textures": [],
		"warnings": [],
		"errors": [],
		"diagnostics": {
			"mesh_count": 0,
			"material_count": 0,
			"texture_count": 0,
			"material_assignments": [],
			"texture_assignments": [],
			"missing_assignments": []
		}
	}
	
	# Try res://Scenes/main.tscn first, fallback to res://main.tscn
	var scene_path = "res://Scenes/main.tscn"
	if not FileAccess.file_exists(scene_path):
		scene_path = "res://main.tscn"
		
	if not FileAccess.file_exists(scene_path):
		report["status"] = "error"
		report["errors"].append("main.tscn does not exist in res://Scenes/ or res://")
		write_report(report)
		quit(1)
		return
		
	var scene = load(scene_path)
	if not scene:
		report["status"] = "error"
		report["errors"].append("Failed to load main.tscn")
		write_report(report)
		quit(1)
		return
		
	report["main_scene_loaded"] = true
	var instance = scene.instantiate()
	if not instance:
		report["status"] = "error"
		report["errors"].append("Failed to instantiate main.tscn")
		write_report(report)
		quit(1)
		return
		
	# Check if textures are present in the Assets folder
	var textures_expected = false
	var dir = DirAccess.open("res://Assets")
	if not dir:
		dir = DirAccess.open("res://assets") # fallback
	if dir:
		dir.list_dir_begin()
		var file_name = dir.get_next()
		while file_name != "":
			if not dir.current_is_dir():
				var ext = file_name.get_extension().to_lower()
				if ext in ["png", "jpg", "jpeg", "tga", "bmp", "webp"]:
					textures_expected = true
					break
			file_name = dir.get_next()
			
	inspect_node(instance, report, textures_expected)
	instance.queue_free()
	
	# Check if any errors occurred
	if report["errors"].size() > 0:
		report["status"] = "error"
		
	print("--- GODOT RUNTIME VALIDATION COMPLETED ---")
	write_report(report)
	quit(0)

func inspect_node(node: Node, report: Dictionary, textures_expected: bool):
	var is_mesh = false
	var mesh_obj = null
	
	if node is MeshInstance3D:
		is_mesh = true
		mesh_obj = node.mesh
	elif node.has_method("get_mesh"):
		is_mesh = true
		mesh_obj = node.call("get_mesh")
		
	if is_mesh:
		report["mesh_instances_count"] += 1
		report["diagnostics"]["mesh_count"] += 1
		
		if mesh_obj:
			var mesh_info = {
				"node_name": node.name,
				"mesh_name": mesh_obj.resource_name if mesh_obj.resource_name != "" else "Unnamed Mesh",
				"surfaces": mesh_obj.get_surface_count(),
				"class": mesh_obj.get_class()
			}
			report["meshes"].append(mesh_info)
			
			var surface_count = mesh_obj.get_surface_count()
			for i in range(surface_count):
				var mat = null
				if node is MeshInstance3D:
					mat = node.get_active_material(i)
				if not mat and mesh_obj.has_method("surface_get_material"):
					mat = mesh_obj.surface_get_material(i)
					
				if mat:
					report["diagnostics"]["material_count"] += 1
					var mat_name = mat.resource_name if mat.resource_name != "" else "Material_" + str(i)
					var mat_info = {
						"node_name": node.name,
						"surface_index": i,
						"material_name": mat_name,
						"class": mat.get_class()
					}
					report["diagnostics"]["material_assignments"].append({
						"mesh": node.name,
						"surface": i,
						"material": mat_name
					})
					
					# Inspect material textures
					var has_tex = false
					var tex_properties = ["albedo_texture", "texture_albedo", "normal_texture", "texture_normal"]
					for prop in tex_properties:
						if prop in mat and mat.get(prop) != null:
							var tex = mat.get(prop)
							has_tex = true
							mat_info[prop] = tex.resource_path
							report["diagnostics"]["texture_count"] += 1
							report["diagnostics"]["texture_assignments"].append({
								"material": mat_name,
								"property": prop,
								"texture": tex.resource_path
							})
							if not tex.resource_path in report["textures"]:
								report["textures"].append(tex.resource_path)
								
							# Verify resource path is valid and file exists
							if not FileAccess.file_exists(tex.resource_path):
								report["errors"].append("TEXTURE_NOT_FOUND: Texture resource path " + tex.resource_path + " does not exist.")
							
							# Try loading the texture to verify actual connection and visibility
							var loaded_tex = load(tex.resource_path)
							if not loaded_tex:
								report["errors"].append("TEXTURE_IMPORT_FAILURE: Failed to load texture resource at " + tex.resource_path)
							elif not (loaded_tex is Texture2D or loaded_tex is Texture):
								report["errors"].append("TEXTURE_INVALID: Resource at " + tex.resource_path + " is not a valid texture")
							elif loaded_tex.get_width() <= 0 or loaded_tex.get_height() <= 0:
								report["errors"].append("TEXTURE_INVISIBLE: Texture at " + tex.resource_path + " has invalid dimensions: " + str(loaded_tex.get_width()) + "x" + str(loaded_tex.get_height()))
								
					if textures_expected and not has_tex:
						report["errors"].append("TEXTURE_NOT_ASSIGNED: Material " + mat_name + " has no texture assigned.")
						report["diagnostics"]["missing_assignments"].append({
							"type": "texture",
							"material": mat_name
						})
					
					report["materials"].append(mat_info)
				else:
					report["errors"].append("MATERIAL_NOT_ASSIGNED: MeshInstance3D '" + node.name + "' surface " + str(i) + " has no material assigned.")
					report["diagnostics"]["missing_assignments"].append({
						"type": "material",
						"mesh": node.name,
						"surface": i
					})
		else:
			report["warnings"].append("MeshInstance3D '" + node.name + "' has no mesh assigned.")
	
	# Recursively inspect children
	for child in node.get_children():
		inspect_node(child, report, textures_expected)

func write_report(report: Dictionary):
	var file = FileAccess.open("res://validation_report.json", FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(report, "  "))
		file.close()
		print("Wrote validation_report.json")
	else:
		print("Error: Could not write validation_report.json")
