import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart' show MediaType;

import '../models/job.dart';
import '../models/scene_suggestion.dart';

/// Client for the measurement backend (agent-backend): video → physics.
class MeasurementApi {
  final Dio _dio;

  MeasurementApi({required String baseUrl, required String apiKey})
      : _dio = Dio(BaseOptions(
          baseUrl: baseUrl,
          headers: {'X-API-Key': apiKey},
          connectTimeout: const Duration(seconds: 30),
          receiveTimeout: const Duration(seconds: 60),
        ));

  String get baseUrl => _dio.options.baseUrl;

  Future<AnalyzeResponse> analyze({
    required String videoPath,
    required String sidecarJson,
    String? template,
    void Function(int sent, int total)? onProgress,
  }) async {
    final form = FormData.fromMap({
      'video': await MultipartFile.fromFile(
        videoPath,
        filename: videoPath.split('/').last,
        contentType: _videoMime(videoPath),
      ),
      'sidecar': sidecarJson,
      'template': ?template,
    });
    final resp = await _dio.post('/analyze', data: form, onSendProgress: onProgress);
    return AnalyzeResponse.fromJson(_map(resp.data));
  }

  /// Advisory scene scour: send one extracted frame, get pre-fill suggestions.
  Future<SceneSuggestion> suggestScene({required String imagePath}) async {
    final form = FormData.fromMap({
      'image': await MultipartFile.fromFile(
        imagePath,
        filename: imagePath.split('/').last,
        contentType: MediaType('image', 'jpeg'),
      ),
    });
    final resp = await _dio.post(
      '/suggest-scene',
      data: form,
      options: Options(receiveTimeout: const Duration(seconds: 120)),
    );
    return SceneSuggestion.fromJson(_map(resp.data));
  }

  /// Ground the given labels in one frame via SAM3 — returns tight boxes/centroids.
  Future<VerifyResult> verifyObjects({
    required String imagePath,
    required List<String> targets,
  }) async {
    final form = FormData.fromMap({
      'image': await MultipartFile.fromFile(
        imagePath,
        filename: imagePath.split('/').last,
        contentType: MediaType('image', 'jpeg'),
      ),
      'targets': jsonEncode(targets),
    });
    final resp = await _dio.post(
      '/verify-objects',
      data: form,
      options: Options(receiveTimeout: const Duration(seconds: 90)),
    );
    return VerifyResult.fromJson(_map(resp.data));
  }

  Future<JobStatus> status(String jobId) async {
    final resp = await _dio.get('/status/$jobId');
    return JobStatus.fromJson(_map(resp.data));
  }

  Future<JobResult> result(String jobId) async {
    final resp = await _dio.get('/result/$jobId');
    return JobResult.fromJson(_map(resp.data));
  }

  Future<List<JobEntry>> jobs() async {
    final resp = await _dio.get('/jobs');
    final list = (_map(resp.data)['jobs'] as List?) ?? const [];
    return list
        .map((e) => JobEntry.fromJson((e as Map).cast<String, dynamic>()))
        .toList();
  }

  Future<void> deleteJob(String jobId) => _dio.delete('/job/$jobId');

  /// Fire-and-forget HITL feedback (setup correction or result feedback).
  Future<void> sendFeedback({
    required String type,
    String? jobId,
    String? userId,
    String? role,
    Map<String, dynamic> payload = const {},
  }) async {
    await _dio.post('/feedback', data: {
      'type': type,
      'job_id': ?jobId,
      'user_id': ?userId,
      'role': ?role,
      'payload': payload,
    });
  }

  /// Resolve a server-relative file path (e.g. "/files/...") to an absolute URL.
  String fileUrl(String path) {
    if (path.startsWith('http')) return path;
    final b = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    return '$b$path';
  }

  MediaType _videoMime(String path) {
    switch (path.split('.').last.toLowerCase()) {
      case 'mov':
        return MediaType('video', 'quicktime');
      case 'avi':
        return MediaType('video', 'x-msvideo');
      case 'mkv':
        return MediaType('video', 'x-matroska');
      default:
        return MediaType('video', 'mp4');
    }
  }

  Map<String, dynamic> _map(dynamic d) => (d as Map).cast<String, dynamic>();
}
