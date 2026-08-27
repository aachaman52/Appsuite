extends Node3D

var line_edit: LineEdit
var button: Button
var label: Label
var panel: Panel

func _ready():
	# Create UI overlay
	var canvas = CanvasLayer.new()
	add_child(canvas)
	
	panel = Panel.new()
	panel.custom_minimum_size = Vector2(650, 220)
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	canvas.add_child(panel)
	
	var vbox = VBoxContainer.new()
	vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	panel.add_child(vbox)
	
	# Add spacing and styling
	var spacer1 = Control.new()
	spacer1.custom_minimum_size = Vector2(0, 10)
	vbox.add_child(spacer1)
	
	var title = Label.new()
	title.text = "AppSuite AI Scene Generator"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	# Make title stand out
	title.add_theme_font_size_override("font_size", 24)
	vbox.add_child(title)
	
	var spacer2 = Control.new()
	spacer2.custom_minimum_size = Vector2(0, 10)
	vbox.add_child(spacer2)
	
	line_edit = LineEdit.new()
	line_edit.placeholder_text = "What would you like to build? (e.g. medieval village with houses, trees)"
	line_edit.custom_minimum_size = Vector2(550, 45)
	vbox.add_child(line_edit)
	
	var spacer3 = Control.new()
	spacer3.custom_minimum_size = Vector2(0, 10)
	vbox.add_child(spacer3)
	
	button = Button.new()
	button.text = "Generate & Open Scene"
	button.custom_minimum_size = Vector2(250, 45)
	vbox.add_child(button)
	
	var spacer4 = Control.new()
	spacer4.custom_minimum_size = Vector2(0, 10)
	vbox.add_child(spacer4)
	
	label = Label.new()
	label.text = "Type your prompt above and press Enter or click Generate."
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vbox.add_child(label)
	
	# Connect signals
	button.pressed.connect(self._on_generate_pressed)
	line_edit.text_submitted.connect(self._on_text_submitted)

func _on_text_submitted(text: String):
	_on_generate_pressed()

func _on_generate_pressed():
	var prompt = line_edit.text.strip_edges()
	if prompt == "":
		label.text = "Please enter a valid prompt!"
		return
		
	label.text = "Generating scene... Running Blender and Godot in the background..."
	button.disabled = true
	line_edit.editable = false
	
	# Wait a brief moment to allow UI refresh
	await get_tree().create_timer(0.1).timeout
	
	var output = []
	var python_exe = "python"
	var args = ["scripts/run_job.py", prompt]
	
	var err = OS.execute(python_exe, args, output, true)
	
	if err != OK:
		label.text = "Failed to run pipeline. Verify python is in your environment PATH."
		button.disabled = false
		line_edit.editable = true
		return
		
	var result_str = "".join(output)
	print(result_str)
	
	var godot_path = ""
	var lines = result_str.split("\n")
	for line in lines:
		if line.begins_with("Godot project:"):
			godot_path = line.replace("Godot project:", "").strip_edges()
			break
			
	if godot_path == "":
		label.text = "Failed to parse the generated project path from script output."
		button.disabled = false
		line_edit.editable = true
		return
		
	label.text = "Generation complete! Opening the project..."
	
	# Read Godot executable path from config
	var godot_binary = "godot"
	var config_file = FileAccess.open("config/config.json", FileAccess.READ)
	if config_file:
		var config_text = config_file.get_as_text()
		var json = JSON.new()
		if json.parse(config_text) == OK:
			var data = json.data
			if data.has("workers") and data["workers"].has("godot"):
				godot_binary = data["workers"]["godot"].get("binary", "godot")
				
	# Launch the newly generated Godot project
	var launch_args = ["--path", godot_path]
	OS.create_process(godot_binary, launch_args)
	
	label.text = "Opened scene in new Godot window! Ready for next prompt."
	button.disabled = false
	line_edit.editable = true
