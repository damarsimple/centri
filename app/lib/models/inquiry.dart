// Models for the pedagogy backend's inquiry tutor.

class InquiryResponse {
  final String inquiryId;
  final String stage;
  final String inquiry;
  final String difficulty;

  InquiryResponse({
    required this.inquiryId,
    required this.stage,
    required this.inquiry,
    required this.difficulty,
  });

  factory InquiryResponse.fromJson(Map<String, dynamic> j) => InquiryResponse(
        inquiryId: (j['inquiry_id'] ?? '') as String,
        stage: (j['stage'] ?? '') as String,
        inquiry: (j['inquiry'] ?? '') as String,
        difficulty: (j['difficulty'] ?? '') as String,
      );
}

class SubmitResult {
  final bool isCorrect;
  final String feedback;
  final String nextStep;
  final String? detectedMisconception;
  final List<String> conceptCoverage;

  SubmitResult({
    required this.isCorrect,
    required this.feedback,
    required this.nextStep,
    this.detectedMisconception,
    this.conceptCoverage = const [],
  });

  factory SubmitResult.fromJson(Map<String, dynamic> j) => SubmitResult(
        isCorrect: (j['is_correct'] ?? false) as bool,
        feedback: (j['feedback'] ?? '') as String,
        nextStep: (j['next_step'] ?? '') as String,
        detectedMisconception: j['detected_misconception'] as String?,
        conceptCoverage: ((j['concept_coverage'] as List?) ?? const [])
            .map((e) => e.toString())
            .toList(),
      );
}

class GeneratedProblem {
  final String problem;
  final String? answer;
  final String? solution;
  final String difficulty;

  GeneratedProblem({
    required this.problem,
    this.answer,
    this.solution,
    required this.difficulty,
  });

  factory GeneratedProblem.fromJson(Map<String, dynamic> j) => GeneratedProblem(
        problem: (j['problem'] ?? '') as String,
        answer: j['answer'] as String?,
        solution: j['solution'] as String?,
        difficulty: (j['difficulty'] ?? '') as String,
      );
}
