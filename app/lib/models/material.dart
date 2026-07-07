/// One difficulty level of the grounded learning material (from /result.materials).
///
/// The backend emits a map difficulty → MaterialLevel (basic/intermediate/advanced).
/// `sections` preserves insertion order (Scenario, The variables we measured,
/// How the variables are related, What the video shows over time, Reading the figures).
class MaterialLevel {
  final String? objectName;
  final String? sceneTitle;
  final String? difficultyLevel;
  final String? bloomObjective;
  final String? elementInteractivity;
  final List<String> conceptsIntroduced;
  final Map<String, String> sections;

  MaterialLevel({
    this.objectName,
    this.sceneTitle,
    this.difficultyLevel,
    this.bloomObjective,
    this.elementInteractivity,
    this.conceptsIntroduced = const [],
    this.sections = const {},
  });

  factory MaterialLevel.fromJson(Map<String, dynamic> j) => MaterialLevel(
        objectName: j['object_name'] as String?,
        sceneTitle: j['scene_title'] as String?,
        difficultyLevel: j['difficulty_level'] as String?,
        bloomObjective: j['bloom_objective'] as String?,
        elementInteractivity: j['element_interactivity'] as String?,
        conceptsIntroduced: ((j['concepts_introduced'] as List?) ?? const [])
            .map((e) => e.toString())
            .toList(),
        sections: ((j['sections'] as Map?)?.cast<String, dynamic>() ?? const {})
            .map((k, v) => MapEntry(k, (v ?? '').toString())),
      );
}
