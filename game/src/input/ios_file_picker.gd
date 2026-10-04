extends RefCounted
## The native plugin owns the temporary copy until import finishes.

func choose(tree: SceneTree) -> Dictionary:
	if not Engine.has_singleton("GalaxianFiles"):
		return {"error": "The iOS file picker is missing from this build."}
	var picker = Engine.get_singleton("GalaxianFiles")
	picker.choose()
	while picker.is_pending():
		await tree.process_frame
	return picker.take_result()


func clear() -> void:
	if Engine.has_singleton("GalaxianFiles"):
		Engine.get_singleton("GalaxianFiles").clear_import()
