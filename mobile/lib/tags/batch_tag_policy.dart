enum BatchTagMode { add, remove, replace }

List<String> applyBatchTags(
  List<String> existing,
  List<String> requested,
  BatchTagMode mode,
) {
  final selected =
      requested.map((tag) => tag.trim()).where((tag) => tag.isNotEmpty).toSet();
  switch (mode) {
    case BatchTagMode.add:
      return List.unmodifiable({...existing, ...selected});
    case BatchTagMode.remove:
      return List.unmodifiable(
          existing.where((tag) => !selected.contains(tag)));
    case BatchTagMode.replace:
      return List.unmodifiable(selected);
  }
}
