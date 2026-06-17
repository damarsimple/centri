import 'package:dio/dio.dart';

import '../models/inquiry.dart';
import '../models/measurement.dart';
import '../models/questions.dart';

/// Client for the pedagogy backend: the staged inquiry tutor + question generation.
class PedagogyApi {
  final Dio _dio;

  PedagogyApi({required String baseUrl})
      : _dio = Dio(BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 30),
          // LLM generation can be slow.
          receiveTimeout: const Duration(seconds: 180),
          headers: {'Content-Type': 'application/json'},
        ));

  Future<InquiryResponse> problemFinding({
    required String userId,
    String language = 'en',
  }) async {
    final r = await _dio.post('/inquiry/generate/problem-finding',
        data: {'user_id': userId, 'language': language});
    return InquiryResponse.fromJson(_m(r.data));
  }

  Future<InquiryResponse> exploringStage1({
    required String userId,
    required String objectLabel,
    String language = 'en',
  }) async {
    final r = await _dio.post('/inquiry/generate/problem-exploring-stage-1',
        data: {'user_id': userId, 'object_label': objectLabel, 'language': language});
    return InquiryResponse.fromJson(_m(r.data));
  }

  Future<InquiryResponse> exploringStage2({
    required String userId,
    required MeasurementContext measurement,
    String language = 'en',
  }) async {
    final r = await _dio.post('/inquiry/generate/problem-exploring-stage-2', data: {
      'user_id': userId,
      'measurement': measurement.toJson(),
      'language': language,
    });
    return InquiryResponse.fromJson(_m(r.data));
  }

  Future<GeneratedProblem> problemGenerating({
    required String userId,
    required MeasurementContext measurement,
    String? objectLabel,
    String language = 'en',
  }) async {
    final r = await _dio.post('/inquiry/generate/problem-generating', data: {
      'user_id': userId,
      'measurement': measurement.toJson(),
      'object_label': ?objectLabel,
      'language': language,
    });
    return GeneratedProblem.fromJson(_m(r.data));
  }

  Future<SubmitResult> submitResponse({
    required String userId,
    required String inquiry,
    required String userAnswer,
    String? inquiryId,
    String? objectLabel,
    MeasurementContext? measurement,
    String language = 'en',
  }) async {
    final r = await _dio.post('/inquiry/submit-response', data: {
      'user_id': userId,
      'inquiry': inquiry,
      'user_answer': userAnswer,
      'inquiry_id': ?inquiryId,
      'object_label': ?objectLabel,
      'measurement': ?measurement?.toJson(),
      'language': language,
    });
    return SubmitResult.fromJson(_m(r.data));
  }

  Future<QuestionSet> questions({
    required String userId,
    required MeasurementContext measurement,
    String? difficulty,
    int count = 3,
    String language = 'en',
  }) async {
    final r = await _dio.post('/questions/generate', data: {
      'user_id': userId,
      'measurement': measurement.toJson(),
      'difficulty': ?difficulty,
      'count': count,
      'language': language,
    });
    return QuestionSet.fromJson(_m(r.data));
  }

  Future<void> upsertProfile({
    required String userId,
    String? gradeLevel,
    String? iqRankOrder,
    String? abilityBand,
  }) =>
      _dio.post('/students/profile', data: {
        'user_id': userId,
        'grade_level': ?gradeLevel,
        'iq_rank_order': ?iqRankOrder,
        'ability_band': ?abilityBand,
      });

  Map<String, dynamic> _m(dynamic d) => (d as Map).cast<String, dynamic>();
}
