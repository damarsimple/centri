import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/settings.dart';
import '../models/inquiry.dart';
import '../models/measurement.dart';
import '../services/clients.dart';
import '../services/pedagogy_api.dart';
import '../widgets/math_text.dart';

enum _Role { tutor, student, feedback, problem }

class _Msg {
  final _Role role;
  final String text;
  final String? note; // misconception / concept coverage / difficulty
  _Msg(this.role, this.text, {this.note});
}

/// The four-stage Socratic inquiry, presented as a guided conversation.
const _stages = [
  'problem-finding',
  'exploring-stage-1',
  'exploring-stage-2',
  'problem-generating',
];

const _stageTitles = [
  'Finding the problem',
  'Exploring the object',
  'Exploring the data',
  'Your challenge',
];

class TutorScreen extends StatefulWidget {
  final MeasurementContext measurement;
  const TutorScreen({super.key, required this.measurement});

  @override
  State<TutorScreen> createState() => _TutorScreenState();
}

class _TutorScreenState extends State<TutorScreen> {
  late final PedagogyApi _api;
  late final String _userId;

  final _messages = <_Msg>[];
  final _input = TextEditingController();
  final _scroll = ScrollController();

  int _stage = 0;
  InquiryResponse? _open; // inquiry awaiting an answer
  GeneratedProblem? _problem; // final generated challenge
  bool _problemSolutionShown = false;
  bool _loading = false;
  bool _answered = false; // current stage's inquiry has been answered

  @override
  void initState() {
    super.initState();
    final s = context.read<Settings>();
    _api = s.pedagogy;
    _userId = s.userId;
    _startStage(0);
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _scrollDown() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      }
    });
  }

  Future<void> _startStage(int stage) async {
    setState(() {
      _stage = stage;
      _loading = true;
      _open = null;
      _problem = null;
      _answered = false;
    });
    try {
      if (stage == 0) {
        final r = await _api.problemFinding(userId: _userId);
        _onInquiry(r);
      } else if (stage == 1) {
        final r = await _api.exploringStage1(
          userId: _userId,
          objectLabel: widget.measurement.objectLabel ?? 'the object',
        );
        _onInquiry(r);
      } else if (stage == 2) {
        final r = await _api.exploringStage2(
          userId: _userId,
          measurement: widget.measurement,
        );
        _onInquiry(r);
      } else {
        final p = await _api.problemGenerating(
          userId: _userId,
          measurement: widget.measurement,
          objectLabel: widget.measurement.objectLabel,
        );
        if (!mounted) return;
        setState(() {
          _problem = p;
          _loading = false;
          _messages.add(_Msg(_Role.problem, p.problem,
              note: p.difficulty.isEmpty ? null : 'Difficulty: ${p.difficulty}'));
        });
        _scrollDown();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _messages.add(_Msg(_Role.feedback, 'Could not reach the tutor: $e'));
      });
      _scrollDown();
    }
  }

  void _onInquiry(InquiryResponse r) {
    if (!mounted) return;
    setState(() {
      _open = r;
      _loading = false;
      _messages.add(_Msg(_Role.tutor, r.inquiry,
          note: r.difficulty.isEmpty ? null : 'Difficulty: ${r.difficulty}'));
    });
    _scrollDown();
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _open == null || _loading) return;
    final inquiry = _open!;
    _input.clear();
    setState(() {
      _loading = true;
      _messages.add(_Msg(_Role.student, text));
    });
    _scrollDown();
    try {
      final res = await _api.submitResponse(
        userId: _userId,
        inquiry: inquiry.inquiry,
        userAnswer: text,
        inquiryId: inquiry.inquiryId,
        objectLabel: widget.measurement.objectLabel,
        measurement: widget.measurement,
      );
      if (!mounted) return;
      setState(() {
        _loading = false;
        _answered = true;
        _open = null;
        _messages.add(_Msg(
          res.isCorrect ? _Role.feedback : _Role.feedback,
          res.feedback.isEmpty
              ? (res.isCorrect ? 'Correct!' : 'Not quite.')
              : res.feedback,
          note: _feedbackNote(res),
        ));
      });
      _scrollDown();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _messages.add(_Msg(_Role.feedback, 'Could not submit: $e'));
      });
      _scrollDown();
    }
  }

  String? _feedbackNote(SubmitResult r) {
    final parts = <String>[];
    if (r.detectedMisconception != null && r.detectedMisconception!.isNotEmpty) {
      parts.add('Watch out: ${r.detectedMisconception}');
    }
    if (r.nextStep.isNotEmpty) parts.add(r.nextStep);
    return parts.isEmpty ? null : parts.join('\n');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Tutor'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(36),
          child: _StageBar(stage: _stage),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView.builder(
                controller: _scroll,
                padding: const EdgeInsets.all(16),
                itemCount: _messages.length + (_loading ? 1 : 0),
                itemBuilder: (context, i) {
                  if (i >= _messages.length) {
                    return const Padding(
                      padding: EdgeInsets.all(16),
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      ),
                    );
                  }
                  return _Bubble(msg: _messages[i]);
                },
              ),
            ),
            _composer(context),
          ],
        ),
      ),
    );
  }

  Widget _composer(BuildContext context) {
    // Awaiting an answer → show the text input.
    if (_open != null) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _input,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                decoration: const InputDecoration(
                    hintText: 'Type your answer…'),
                onSubmitted: (_) => _send(),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              onPressed: _loading ? null : _send,
              icon: const Icon(Icons.send),
            ),
          ],
        ),
      );
    }

    if (_loading) return const SizedBox(height: 8);

    // Final stage: the generated problem.
    if (_stage == _stages.length - 1 && _problem != null) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (!_problemSolutionShown &&
                (_problem!.solution != null || _problem!.answer != null))
              OutlinedButton.icon(
                onPressed: () {
                  setState(() {
                    _problemSolutionShown = true;
                    final sol = _problem!.solution ?? '';
                    final ans = _problem!.answer ?? '';
                    _messages.add(_Msg(
                      _Role.feedback,
                      [
                        if (ans.isNotEmpty) 'Answer: $ans',
                        if (sol.isNotEmpty) sol,
                      ].join('\n\n'),
                    ));
                  });
                  _scrollDown();
                },
                icon: const Icon(Icons.lightbulb_outline),
                label: const Text('Show solution'),
              ),
            const SizedBox(height: 8),
            FilledButton.icon(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.check),
              label: const Text('Finish'),
            ),
          ],
        ),
      );
    }

    // Answered an intermediate stage → advance.
    if (_answered && _stage < _stages.length - 1) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
        child: FilledButton.icon(
          onPressed: () => _startStage(_stage + 1),
          icon: const Icon(Icons.arrow_forward),
          label: Text('Next: ${_stageTitles[_stage + 1]}'),
        ),
      );
    }

    return const SizedBox(height: 8);
  }
}

class _StageBar extends StatelessWidget {
  final int stage;
  const _StageBar({required this.stage});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: Row(
        children: [
          for (var i = 0; i < _stages.length; i++) ...[
            if (i > 0) const SizedBox(width: 6),
            Expanded(
              child: Container(
                height: 5,
                decoration: BoxDecoration(
                  color: i <= stage ? scheme.primary : scheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  final _Msg msg;
  const _Bubble({required this.msg});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isStudent = msg.role == _Role.student;

    late Color bg;
    late Color fg;
    IconData? icon;
    switch (msg.role) {
      case _Role.student:
        bg = scheme.primary;
        fg = scheme.onPrimary;
        break;
      case _Role.tutor:
        bg = scheme.surfaceContainerHighest;
        fg = scheme.onSurface;
        icon = Icons.school_outlined;
        break;
      case _Role.feedback:
        bg = scheme.secondaryContainer;
        fg = scheme.onSecondaryContainer;
        icon = Icons.feedback_outlined;
        break;
      case _Role.problem:
        bg = scheme.tertiaryContainer;
        fg = scheme.onTertiaryContainer;
        icon = Icons.emoji_objects_outlined;
        break;
    }

    return Align(
      alignment: isStudent ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.82),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (icon != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Icon(icon, size: 18, color: fg),
              ),
            MathText(msg.text, style: TextStyle(color: fg, height: 1.35)),
            if (msg.note != null) ...[
              const SizedBox(height: 8),
              Text(msg.note!,
                  style: TextStyle(
                      color: fg.withValues(alpha: 0.75),
                      fontSize: 12,
                      fontStyle: FontStyle.italic)),
            ],
          ],
        ),
      ),
    );
  }
}
