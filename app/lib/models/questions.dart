// Tiered question generation models (pedagogy backend /questions/*).

class Question {
  final String stem;
  final String? type;
  final String? answer;
  final String? solution;

  Question({required this.stem, this.type, this.answer, this.solution});

  factory Question.fromJson(Map<String, dynamic> j) => Question(
        stem: (j['stem'] ?? '') as String,
        type: j['type'] as String?,
        answer: j['answer'] as String?,
        solution: j['solution'] as String?,
      );
}

class QuestionSet {
  final String difficulty;
  final List<Question> questions;

  QuestionSet({required this.difficulty, required this.questions});

  factory QuestionSet.fromJson(Map<String, dynamic> j) => QuestionSet(
        difficulty: (j['difficulty'] ?? '') as String,
        questions: ((j['questions'] as List?) ?? const [])
            .map((e) => Question.fromJson((e as Map).cast<String, dynamic>()))
            .toList(),
      );
}
