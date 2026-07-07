// Models for the measurement backend (agent-backend).
import 'material.dart';

class AnalyzeResponse {
  final String jobId;
  AnalyzeResponse(this.jobId);
  factory AnalyzeResponse.fromJson(Map<String, dynamic> j) =>
      AnalyzeResponse((j['job_id'] ?? '') as String);
}

/// One concrete action the agent took, for the live feed.
class ActivityItem {
  final int seq;
  final String kind; // run | read | write | track
  final String title;
  final String? detail;
  final String status; // running | done | error

  ActivityItem({
    required this.seq,
    required this.kind,
    required this.title,
    this.detail,
    required this.status,
  });

  factory ActivityItem.fromJson(Map<String, dynamic> j) => ActivityItem(
        seq: (j['seq'] as num?)?.round() ?? 0,
        kind: (j['kind'] ?? 'run') as String,
        title: (j['title'] ?? '') as String,
        detail: j['detail'] as String?,
        status: (j['status'] ?? 'done') as String,
      );

  bool get isRunning => status == 'running';
  bool get isError => status == 'error';
}

/// A named pipeline stage shown as a checklist.
class StageItem {
  final String key;
  final String label;
  final String status; // pending | active | done

  StageItem({required this.key, required this.label, required this.status});

  factory StageItem.fromJson(Map<String, dynamic> j) => StageItem(
        key: (j['key'] ?? '') as String,
        label: (j['label'] ?? '') as String,
        status: (j['status'] ?? 'pending') as String,
      );

  bool get isDone => status == 'done';
  bool get isActive => status == 'active';
}

class JobStatus {
  final String jobId;
  final String status; // running | done | failed
  final String? step;
  final int progressPct;
  final String? message;
  final int? elapsedS;
  // Interactive agentic feed
  final String? phase;
  final String? currentAction;
  final String? thinking;
  final List<StageItem> stages;
  final List<ActivityItem> activities;

  JobStatus({
    required this.jobId,
    required this.status,
    this.step,
    this.progressPct = 0,
    this.message,
    this.elapsedS,
    this.phase,
    this.currentAction,
    this.thinking,
    this.stages = const [],
    this.activities = const [],
  });

  factory JobStatus.fromJson(Map<String, dynamic> j) => JobStatus(
        jobId: (j['job_id'] ?? '') as String,
        status: (j['status'] ?? 'unknown') as String,
        step: j['step'] as String?,
        progressPct: (j['progress_pct'] as num?)?.round() ?? 0,
        message: j['message'] as String?,
        elapsedS: (j['elapsed_s'] as num?)?.round(),
        phase: j['phase'] as String?,
        currentAction: j['current_action'] as String?,
        thinking: j['thinking'] as String?,
        stages: ((j['stages'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => StageItem.fromJson(e.cast<String, dynamic>()))
            .toList(),
        activities: ((j['activities'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => ActivityItem.fromJson(e.cast<String, dynamic>()))
            .toList(),
      );

  bool get isDone => status.toLowerCase() == 'done';
  bool get isFailed =>
      status.toLowerCase() == 'failed' || status.toLowerCase() == 'error';
}

class JobFiles {
  final String? studentPdf;
  final String? teacherPdf;
  final String? annotatedVideo;
  final String? summaryPanel;
  final String? kinematicsCsv;
  // Per-difficulty student PDFs on a tiered job (basic/intermediate/advanced → URL).
  final Map<String, String> tierPdfs;

  JobFiles({
    this.studentPdf,
    this.teacherPdf,
    this.annotatedVideo,
    this.summaryPanel,
    this.kinematicsCsv,
    this.tierPdfs = const {},
  });

  /// The student PDF for a difficulty level, falling back to the single studentPdf.
  String? studentPdfFor(String? level) =>
      (level != null ? tierPdfs[level] : null) ?? studentPdf;

  factory JobFiles.fromJson(Map<String, dynamic> j) => JobFiles(
        studentPdf: j['student_pdf'] as String?,
        teacherPdf: j['teacher_pdf'] as String?,
        annotatedVideo: j['annotated_video'] as String?,
        summaryPanel: j['summary_panel'] as String?,
        kinematicsCsv: j['kinematics_csv'] as String?,
        tierPdfs: ((j['tier_pdfs'] as Map?)?.cast<String, dynamic>() ?? const {})
            .map((k, v) => MapEntry(k, v as String)),
      );
}

/// Per-frame kinematics time-series for native charts (from /result.series).
class MotionSeries {
  final List<double> tS;
  final List<double> omega;
  final List<double> ac;
  final List<double> v;
  final List<double> rM;
  final List<double> theta;
  final List<int> active;

  MotionSeries({
    required this.tS,
    required this.omega,
    required this.ac,
    required this.v,
    required this.rM,
    required this.theta,
    required this.active,
  });

  static List<double> _d(dynamic l) =>
      ((l as List?) ?? const []).map((e) => (e as num).toDouble()).toList();

  factory MotionSeries.fromJson(Map<String, dynamic> j) => MotionSeries(
        tS: _d(j['t_s']),
        omega: _d(j['omega_rad_s']),
        ac: _d(j['ac_m_s2']),
        v: _d(j['v_m_s']),
        rM: _d(j['r_m']),
        theta: _d(j['theta_rad']),
        active: ((j['active'] as List?) ?? const [])
            .map((e) => (e as num).round())
            .toList(),
      );

  bool get isEmpty => tS.isEmpty;
}

/// One generated practice question (student sees stem; teacher sees answer+solution).
class ResultQuestion {
  final String? stem;
  final Map<String, dynamic>? given;
  final String? answer;
  final String? unit;
  final String? solution;
  final String? bloomLevel;
  final String? difficulty;
  final String? format;

  ResultQuestion({
    this.stem,
    this.given,
    this.answer,
    this.unit,
    this.solution,
    this.bloomLevel,
    this.difficulty,
    this.format,
  });

  factory ResultQuestion.fromJson(Map<String, dynamic> j) => ResultQuestion(
        stem: j['stem'] as String?,
        given: (j['given'] as Map?)?.cast<String, dynamic>(),
        answer: j['answer']?.toString(),
        unit: j['unit'] as String?,
        solution: j['solution'] as String?,
        bloomLevel: j['bloom_level'] as String?,
        difficulty: j['difficulty'] as String?,
        format: j['format'] as String?,
      );
}

/// The report content, structured for native rendering (no PDF).
class Worksheet {
  final String? objectName;
  final String? scenario;
  final List<ResultQuestion> questions;

  Worksheet({this.objectName, this.scenario, this.questions = const []});

  factory Worksheet.fromJson(Map<String, dynamic> j) => Worksheet(
        objectName: j['object_name'] as String?,
        scenario: j['scenario'] as String?,
        questions: ((j['questions'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => ResultQuestion.fromJson(e.cast<String, dynamic>()))
            .toList(),
      );
}

class JobResult {
  final String jobId;
  final Map<String, dynamic> stats;
  final JobFiles files;
  final MotionSeries? series;
  final Worksheet? worksheet;
  // Difficulty-tiered learning material (basic/intermediate/advanced), or null for
  // legacy/untiered jobs. Rendered natively on the results screen.
  final Map<String, MaterialLevel>? materials;

  JobResult({
    required this.jobId,
    required this.stats,
    required this.files,
    this.series,
    this.worksheet,
    this.materials,
  });

  factory JobResult.fromJson(Map<String, dynamic> j) => JobResult(
        jobId: (j['job_id'] ?? '') as String,
        stats: (j['stats'] as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{},
        files: JobFiles.fromJson(
            (j['files'] as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{}),
        series: j['series'] is Map
            ? MotionSeries.fromJson((j['series'] as Map).cast<String, dynamic>())
            : null,
        worksheet: j['worksheet'] is Map
            ? Worksheet.fromJson((j['worksheet'] as Map).cast<String, dynamic>())
            : null,
        materials: j['materials'] is Map
            ? (j['materials'] as Map).cast<String, dynamic>().map((k, v) =>
                MapEntry(k, MaterialLevel.fromJson((v as Map).cast<String, dynamic>())))
            : null,
      );
}

class JobEntry {
  final String jobId;
  final String? status;
  final String? step;
  final int progressPct;
  final int? elapsedS;
  final String? objectName;
  final DateTime? createdAt;

  JobEntry({
    required this.jobId,
    this.status,
    this.step,
    this.progressPct = 0,
    this.elapsedS,
    this.objectName,
    this.createdAt,
  });

  factory JobEntry.fromJson(Map<String, dynamic> j) => JobEntry(
        jobId: (j['job_id'] ?? '') as String,
        status: j['status'] as String?,
        step: j['step'] as String?,
        progressPct: (j['progress_pct'] as num?)?.round() ?? 0,
        elapsedS: (j['elapsed_s'] as num?)?.round(),
        objectName: j['object_name'] as String?,
        createdAt: j['created_at'] is num
            ? DateTime.fromMillisecondsSinceEpoch(
                ((j['created_at'] as num) * 1000).round())
            : null,
      );
}
