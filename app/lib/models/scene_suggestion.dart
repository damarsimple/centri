// Advisory annotation pre-fill from the measurement backend's /suggest-scene.

class DetectedObject {
  final String? label;
  final List<double>? bbox; // [x, y, w, h] in frame pixels
  final double? confidence;

  DetectedObject({this.label, this.bbox, this.confidence});

  factory DetectedObject.fromJson(Map<String, dynamic> j) => DetectedObject(
        label: j['label'] as String?,
        bbox: _nums(j['bbox']),
        confidence: (j['confidence'] as num?)?.toDouble(),
      );
}

class ReferenceObject extends DetectedObject {
  final double? physicalSizeM;
  final String? sizeBasis;

  ReferenceObject({
    super.label,
    super.bbox,
    super.confidence,
    this.physicalSizeM,
    this.sizeBasis,
  });

  factory ReferenceObject.fromJson(Map<String, dynamic> j) => ReferenceObject(
        label: j['label'] as String?,
        bbox: _nums(j['bbox']),
        confidence: (j['confidence'] as num?)?.toDouble(),
        physicalSizeM: (j['physical_size_m'] as num?)?.toDouble(),
        sizeBasis: j['size_basis'] as String?,
      );
}

class SceneSuggestion {
  final DetectedObject? movingObject;
  final ReferenceObject? referenceObject;
  final List<double>? rotationCenterPx; // [cx, cy] in frame pixels
  final int frameW;
  final int frameH;
  final String? notes;

  SceneSuggestion({
    this.movingObject,
    this.referenceObject,
    this.rotationCenterPx,
    required this.frameW,
    required this.frameH,
    this.notes,
  });

  factory SceneSuggestion.fromJson(Map<String, dynamic> j) => SceneSuggestion(
        movingObject: j['moving_object'] == null
            ? null
            : DetectedObject.fromJson(
                (j['moving_object'] as Map).cast<String, dynamic>()),
        referenceObject: j['reference_object'] == null
            ? null
            : ReferenceObject.fromJson(
                (j['reference_object'] as Map).cast<String, dynamic>()),
        rotationCenterPx: _nums(j['rotation_center_px']),
        frameW: (j['frame_w'] as num?)?.round() ?? 0,
        frameH: (j['frame_h'] as num?)?.round() ?? 0,
        notes: j['notes'] as String?,
      );

  /// Rotation centre as a 0..1 fraction of the frame (resolution-independent).
  ({double dx, double dy})? get centerFrac {
    final c = rotationCenterPx;
    if (c == null || c.length != 2 || frameW == 0 || frameH == 0) return null;
    return (dx: (c[0] / frameW).clamp(0.0, 1.0), dy: (c[1] / frameH).clamp(0.0, 1.0));
  }

  /// A detected box as fractional [left, top, w, h] of the frame, if present.
  List<double>? bboxFrac(List<double>? bbox) {
    if (bbox == null || bbox.length != 4 || frameW == 0 || frameH == 0) return null;
    return [
      bbox[0] / frameW,
      bbox[1] / frameH,
      bbox[2] / frameW,
      bbox[3] / frameH,
    ];
  }
}

/// SAM3 single-frame grounding result (from /verify-objects).
class VerifiedObject {
  final double? cx;
  final double? cy;
  final List<double>? bbox; // [x, y, w, h]

  VerifiedObject({this.cx, this.cy, this.bbox});

  factory VerifiedObject.fromJson(Map<String, dynamic> j) => VerifiedObject(
        cx: (j['cx'] as num?)?.toDouble(),
        cy: (j['cy'] as num?)?.toDouble(),
        bbox: _nums(j['bbox']),
      );
}

class VerifyResult {
  final int frameW;
  final int frameH;
  final Map<String, VerifiedObject?> objects;

  VerifyResult({required this.frameW, required this.frameH, required this.objects});

  factory VerifyResult.fromJson(Map<String, dynamic> j) {
    final raw = (j['objects'] as Map?)?.cast<String, dynamic>() ?? const {};
    return VerifyResult(
      frameW: (j['frame_w'] as num?)?.round() ?? 0,
      frameH: (j['frame_h'] as num?)?.round() ?? 0,
      objects: raw.map((k, v) => MapEntry(
            k,
            v == null
                ? null
                : VerifiedObject.fromJson((v as Map).cast<String, dynamic>()),
          )),
    );
  }

  /// A box as fractional [left, top, w, h] of the frame.
  List<double>? bboxFrac(List<double>? bbox) {
    if (bbox == null || bbox.length != 4 || frameW == 0 || frameH == 0) return null;
    return [bbox[0] / frameW, bbox[1] / frameH, bbox[2] / frameW, bbox[3] / frameH];
  }

  ({double dx, double dy})? centerFrac(VerifiedObject? o) {
    if (o?.cx == null || o?.cy == null || frameW == 0 || frameH == 0) return null;
    return (dx: (o!.cx! / frameW).clamp(0.0, 1.0), dy: (o.cy! / frameH).clamp(0.0, 1.0));
  }
}

List<double>? _nums(dynamic v) {
  if (v is! List) return null;
  final out = <double>[];
  for (final e in v) {
    if (e is num) {
      out.add(e.toDouble());
    } else {
      return null;
    }
  }
  return out;
}
