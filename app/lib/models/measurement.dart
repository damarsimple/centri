/// The seam: physics measured from the video, sent to the pedagogy backend.
/// Built from agent-backend's /result `stats` (prefers stable-phase values).
class MeasurementContext {
  final String? objectLabel;
  final double? radiusM;
  final double? meanOmegaRadS;
  final double? meanAcMs2;
  final double? periodS;

  MeasurementContext({
    this.objectLabel,
    this.radiusM,
    this.meanOmegaRadS,
    this.meanAcMs2,
    this.periodS,
  });

  factory MeasurementContext.fromStats(Map<String, dynamic> s) {
    double? num2(List<String> keys) {
      for (final k in keys) {
        final v = s[k];
        if (v is num) return v.toDouble();
      }
      return null;
    }

    return MeasurementContext(
      objectLabel: s['object_name']?.toString(),
      radiusM: num2(['r_fit_m', 'mean_r_m']),
      meanOmegaRadS: num2(['stable_mean_omega', 'mean_omega']),
      meanAcMs2: num2(['stable_mean_ac', 'mean_ac']),
      periodS: num2(['period_s']),
    );
  }

  Map<String, dynamic> toJson() => {
        if (objectLabel != null) 'object_label': objectLabel,
        if (radiusM != null) 'radius_m': radiusM,
        if (meanOmegaRadS != null) 'mean_omega_rad_s': meanOmegaRadS,
        if (meanAcMs2 != null) 'mean_ac_m_s2': meanAcMs2,
        if (periodS != null) 'period_s': periodS,
      };

  bool get hasData => meanOmegaRadS != null || meanAcMs2 != null;
}
