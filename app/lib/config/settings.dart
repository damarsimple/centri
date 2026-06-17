import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// App settings: the two backend endpoints + the student id. Persisted locally.
class Settings extends ChangeNotifier {
  static const _kMeasUrl = 'measurement_url';
  static const _kMeasKey = 'measurement_key';
  static const _kPedaUrl = 'pedagogy_url';
  static const _kUserId = 'user_id';
  static const _kConsent = 'consent_accepted';
  static const _kTelemetry = 'telemetry_enabled';
  static const _kBriefingSeen = 'briefing_seen';

  static const defaultMeasurementUrl = 'http://192.168.1.13:8088';
  static const defaultMeasurementKey = 'changeme-random-secret-key-12345';
  static const defaultPedagogyUrl = 'http://192.168.1.13:8090';
  static const defaultUserId = 'student-1';

  String measurementUrl;
  String measurementKey;
  String pedagogyUrl;
  String userId;
  bool consentAccepted;
  bool telemetryEnabled;

  /// Whether the user has already seen (or chosen to skip) the experiment
  /// briefing. The pre-read is shown on first use only.
  bool briefingSeen;

  Settings({
    this.measurementUrl = defaultMeasurementUrl,
    this.measurementKey = defaultMeasurementKey,
    this.pedagogyUrl = defaultPedagogyUrl,
    this.userId = defaultUserId,
    this.consentAccepted = false,
    this.telemetryEnabled = true,
    this.briefingSeen = false,
  });

  static Future<Settings> load() async {
    final p = await SharedPreferences.getInstance();
    return Settings(
      measurementUrl: p.getString(_kMeasUrl) ?? defaultMeasurementUrl,
      measurementKey: p.getString(_kMeasKey) ?? defaultMeasurementKey,
      pedagogyUrl: p.getString(_kPedaUrl) ?? defaultPedagogyUrl,
      userId: p.getString(_kUserId) ?? defaultUserId,
      consentAccepted: p.getBool(_kConsent) ?? false,
      telemetryEnabled: p.getBool(_kTelemetry) ?? true,
      briefingSeen: p.getBool(_kBriefingSeen) ?? false,
    );
  }

  /// Record that the briefing has been seen. [skip] reflects the
  /// "don't show this again" choice; when false the briefing will show again.
  Future<void> setBriefingSeen(bool skip) async {
    briefingSeen = skip;
    final p = await SharedPreferences.getInstance();
    await p.setBool(_kBriefingSeen, skip);
    notifyListeners();
  }

  Future<void> update({
    String? measurementUrl,
    String? measurementKey,
    String? pedagogyUrl,
    String? userId,
    bool? telemetryEnabled,
  }) async {
    this.measurementUrl = measurementUrl ?? this.measurementUrl;
    this.measurementKey = measurementKey ?? this.measurementKey;
    this.pedagogyUrl = pedagogyUrl ?? this.pedagogyUrl;
    this.userId = userId ?? this.userId;
    this.telemetryEnabled = telemetryEnabled ?? this.telemetryEnabled;
    final p = await SharedPreferences.getInstance();
    await p.setString(_kMeasUrl, this.measurementUrl);
    await p.setString(_kMeasKey, this.measurementKey);
    await p.setString(_kPedaUrl, this.pedagogyUrl);
    await p.setString(_kUserId, this.userId);
    await p.setBool(_kTelemetry, this.telemetryEnabled);
    notifyListeners();
  }

  /// One-time consent. [telemetry] sets whether implicit usage data is shared.
  Future<void> acceptConsent({required bool telemetry}) async {
    consentAccepted = true;
    telemetryEnabled = telemetry;
    final p = await SharedPreferences.getInstance();
    await p.setBool(_kConsent, true);
    await p.setBool(_kTelemetry, telemetry);
    notifyListeners();
  }

  bool get isConfigured => measurementUrl.isNotEmpty && pedagogyUrl.isNotEmpty;
}
