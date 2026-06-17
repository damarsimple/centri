/// The scene-geometry sidecar sent with the video to the measurement backend.
/// Matches agent-backend's orchestrator Step 1 / the original app's SidecarJson.
class Sidecar {
  final String objectLabel; // tracked object visual cue (e.g. "red ball")
  final String referenceLabel; // calibration object label (e.g. "lazy susan")
  // The user-marked rotation centre as a fraction (0..1) of the frame — the
  // authoritative axis. Resolution/rotation-independent: the backend maps it to
  // its own decoded frame dims. Decoupled from the reference object, which may
  // be a scale ruler placed off the axis.
  final List<double>? rotationCenterFrac; // [fx, fy] in 0..1
  final double? physicalSize; // reference physical size in metres (optional)
  final int videoW;
  final int videoH;
  final int displayW;
  final int displayH;

  Sidecar({
    required this.objectLabel,
    required this.referenceLabel,
    this.rotationCenterFrac,
    this.physicalSize,
    required this.videoW,
    required this.videoH,
    required this.displayW,
    required this.displayH,
  });

  Map<String, dynamic> toJson() => {
        'tracked_object': {
          'visual_cues': [objectLabel],
        },
        'reference_geometry': {
          'label': referenceLabel,
          if (physicalSize != null) 'physical_size': physicalSize,
        },
        // Authoritative rotation axis, preferred by the orchestrator over the
        // reference-object median. Fraction of the frame, 0..1.
        if (rotationCenterFrac != null) 'rotation_center_frac': rotationCenterFrac,
        'display_w': displayW,
        'display_h': displayH,
        'video_w': videoW,
        'video_h': videoH,
      };
}
