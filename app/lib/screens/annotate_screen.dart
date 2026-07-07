import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:video_thumbnail/video_thumbnail.dart';

import '../config/settings.dart';
import '../models/scene_suggestion.dart';
import '../models/sidecar.dart';
import '../services/clients.dart';
import '../widgets/async_button.dart';
import '../widgets/info_views.dart';
import 'progress_screen.dart';

class AnnotateScreen extends StatefulWidget {
  final String videoPath;
  const AnnotateScreen({super.key, required this.videoPath});

  @override
  State<AnnotateScreen> createState() => _AnnotateScreenState();
}

class _AnnotateScreenState extends State<AnnotateScreen> {
  String? _framePath; // extracted first frame
  int _imgW = 0;
  int _imgH = 0;
  String? _initError;

  bool _suggesting = false;
  String? _suggestError;
  SceneSuggestion? _suggestion;
  bool _suggestionApplied = false;

  VerifyResult? _verify;
  String? _verifyNote; // human-readable grounding result
  bool _verifyRan = false;

  // What the VLM originally predicted, kept to detect user corrections (HITL).
  String? _predObject;
  String? _predRef;
  double? _predSizeCm;
  ({double dx, double dy})? _predCenter;

  final _objectCtrl = TextEditingController();
  final _refCtrl = TextEditingController();
  final _sizeCtrl = TextEditingController(); // centimetres
  final _sceneCtrl = TextEditingController(); // free-text scene context (who/where…)

  // Rotation centre as a fraction (0..1) of the frame, so it survives any box size.
  Offset? _centerFrac;
  Size _lastBox = Size.zero;

  // Upload progress (0..1), null = indeterminate. Drives the upload dialog.
  final _uploadProgress = ValueNotifier<double?>(0);

  @override
  void initState() {
    super.initState();
    _prepare();
  }

  @override
  void dispose() {
    _objectCtrl.dispose();
    _refCtrl.dispose();
    _sizeCtrl.dispose();
    _sceneCtrl.dispose();
    _uploadProgress.dispose();
    super.dispose();
  }

  Future<void> _prepare() async {
    try {
      final path = await _extractFrame();
      if (path == null) {
        throw 'Could not read a frame from this video. Try a different clip '
            '(some phone recordings use a format the device can\'t decode here).';
      }
      final bytes = await File(path).readAsBytes();
      final codec = await ui.instantiateImageCodec(bytes);
      final frame = await codec.getNextFrame();
      if (!mounted) return;
      setState(() {
        _framePath = path;
        _imgW = frame.image.width;
        _imgH = frame.image.height;
      });
      frame.image.dispose();
      _scour(path);
    } catch (e) {
      if (mounted) setState(() => _initError = '$e');
    }
  }

  /// Grab a still frame from the video. `MediaMetadataRetriever` (under
  /// video_thumbnail) returns null for the very first frame on some codecs,
  /// so we try a few timestamps and validate the file actually has bytes.
  Future<String?> _extractFrame() async {
    for (final t in const [0, 200, 600, 1500, 3000]) {
      try {
        final path = await VideoThumbnail.thumbnailFile(
          video: widget.videoPath,
          imageFormat: ImageFormat.JPEG,
          quality: 90,
          timeMs: t,
          maxWidth: 1280,
        );
        if (path != null && await File(path).exists() &&
            await File(path).length() > 0) {
          return path;
        }
      } catch (_) {
        // try the next timestamp
      }
    }
    return null;
  }

  Future<void> _scour(String framePath) async {
    setState(() => _suggesting = true);
    try {
      final s = await context.read<Settings>().measurement
          .suggestScene(imagePath: framePath);
      if (!mounted) return;
      setState(() {
        _suggestion = s;
        _suggesting = false;
      });
      _applySuggestion(s);
    } catch (_) {
      if (mounted) {
        setState(() {
          _suggesting = false;
          _suggestError = 'Auto-detect didn\'t recognise the scene — fill in the fields below to continue.';
        });
      }
    }
  }

  void _applySuggestion(SceneSuggestion s) {
    // Remember the raw prediction so we can later see what the student changed.
    _predObject = s.movingObject?.label;
    _predRef = s.referenceObject?.label;
    final pm = s.referenceObject?.physicalSizeM;
    _predSizeCm = pm == null ? null : pm * 100;
    _predCenter = s.centerFrac;

    if (_objectCtrl.text.trim().isEmpty && s.movingObject?.label != null) {
      _objectCtrl.text = s.movingObject!.label!;
    }
    if (_refCtrl.text.trim().isEmpty && s.referenceObject?.label != null) {
      _refCtrl.text = s.referenceObject!.label!;
    }
    final sizeM = s.referenceObject?.physicalSizeM;
    if (_sizeCtrl.text.trim().isEmpty && sizeM != null) {
      _sizeCtrl.text = (sizeM * 100).toStringAsFixed(1);
    }
    final c = s.centerFrac;
    if (_centerFrac == null && c != null) {
      _centerFrac = Offset(c.dx, c.dy);
    }
    // Pre-fill the scene-context field with the VLM's advisory notes (the user can edit
    // or clear it); it becomes the authoritative narrative frame for the learning material.
    if (_sceneCtrl.text.trim().isEmpty && (s.notes ?? '').trim().isNotEmpty) {
      _sceneCtrl.text = s.notes!.trim();
    }
    setState(() => _suggestionApplied = true);
  }

  Future<void> _runVerify() async {
    final obj = _objectCtrl.text.trim();
    final ref = _refCtrl.text.trim();
    final targets = [obj, ref].where((s) => s.isNotEmpty).toList();
    if (_framePath == null || targets.isEmpty) return;
    try {
      final r = await context.read<Settings>().measurement
          .verifyObjects(imagePath: _framePath!, targets: targets);
      if (!mounted) return;
      // Verification confirms the objects are detectable; it must NOT move a
      // centre the user already placed (the reference may be a scale ruler off
      // the axis). Only auto-fill the centre if none has been set yet.
      final refObj = r.objects[ref];
      final c = r.centerFrac(refObj);
      final found = targets.where((t) => r.objects[t] != null).toList();
      final missing = targets.where((t) => r.objects[t] == null).toList();
      setState(() {
        _verify = r;
        _verifyRan = true;
        if (c != null && _centerFrac == null) _centerFrac = Offset(c.dx, c.dy);
        _verifyNote = missing.isEmpty
            ? 'The app can see both objects ✓'
            : "Couldn't spot: ${missing.join(', ')} — try describing it differently";
        if (found.isEmpty) {
          _verifyNote =
              "Couldn't spot any of these — try different words and check again";
        }
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Verify failed: $e')));
    }
  }

  bool get _canSubmit =>
      _framePath != null &&
      _centerFrac != null &&
      _objectCtrl.text.trim().isNotEmpty &&
      _refCtrl.text.trim().isNotEmpty;

  Future<void> _submit() async {
    final settings = context.read<Settings>();
    final cm = double.tryParse(_sizeCtrl.text.trim());

    final sidecar = Sidecar(
      objectLabel: _objectCtrl.text.trim(),
      referenceLabel: _refCtrl.text.trim(),
      // Authoritative rotation axis as a frame fraction (0..1).
      rotationCenterFrac: [_centerFrac!.dx, _centerFrac!.dy],
      physicalSize: cm == null ? null : cm / 100.0, // cm → metres
      sceneContext: _sceneCtrl.text.trim().isEmpty ? null : _sceneCtrl.text.trim(),
      videoW: _imgW,
      videoH: _imgH,
      displayW: _lastBox.width.round(),
      displayH: _lastBox.height.round(),
    );

    _uploadProgress.value = 0;
    _showUploadDialog();
    try {
      final resp = await settings.measurement.analyze(
        videoPath: widget.videoPath,
        sidecarJson: jsonEncode(sidecar.toJson()),
        onProgress: (sent, total) {
          _uploadProgress.value = total > 0 ? sent / total : null;
        },
      );
      _logSetupCorrection(settings, resp.jobId, cm);
      if (!mounted) return;
      Navigator.of(context).pop(); // dismiss the upload dialog
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => ProgressScreen(jobId: resp.jobId)),
      );
    } catch (e) {
      if (!mounted) return;
      Navigator.of(context).pop(); // dismiss the upload dialog
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Upload failed: $e')));
    }
  }

  /// Modal shown while the video uploads — a real progress bar (the file can be a
  /// few MB over wifi). Once bytes finish sending, the server is still preparing
  /// the job, so we switch to an indeterminate "Processing…" until it returns.
  void _showUploadDialog() {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => PopScope(
        canPop: false,
        child: AlertDialog(
          title: const Text('Uploading your video'),
          content: ValueListenableBuilder<double?>(
            valueListenable: _uploadProgress,
            builder: (context, frac, _) {
              final sending = frac != null && frac < 1.0;
              final pct = frac == null ? null : (frac * 100).clamp(0, 100).round();
              return Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: LinearProgressIndicator(
                      value: sending ? frac : null,
                      minHeight: 8,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    sending ? 'Sending… $pct%' : 'Processing on the server…',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  /// Fire-and-forget: record what the VLM/SAM3 predicted vs. what the student
  /// actually submitted, so we can later analyse where the models went wrong.
  void _logSetupCorrection(Settings settings, String jobId, double? finalCm) {
    if (!settings.telemetryEnabled) return; // user opted out of usage data
    if (_suggestion == null) return; // nothing was predicted
    final finalObject = _objectCtrl.text.trim();
    final finalRef = _refCtrl.text.trim();
    final finalCenter = _centerFrac;

    bool centreMoved() {
      final p = _predCenter, f = finalCenter;
      if (p == null || f == null) return p != null || f != null;
      return ((p.dx - f.dx).abs() + (p.dy - f.dy).abs()) > 0.02;
    }

    final edited = <String>[
      if (_predObject?.trim() != finalObject) 'object_label',
      if (_predRef?.trim() != finalRef) 'reference_label',
      if ((_predSizeCm?.toStringAsFixed(1)) != finalCm?.toStringAsFixed(1))
        'reference_size',
      if (centreMoved()) 'rotation_center',
    ];

    settings.measurement.sendFeedback(
      type: 'setup_correction',
      jobId: jobId,
      userId: settings.userId,
      payload: {
        'predicted': {
          'object_label': _predObject,
          'reference_label': _predRef,
          'reference_size_cm': _predSizeCm,
          'rotation_center_frac':
              _predCenter == null ? null : [_predCenter!.dx, _predCenter!.dy],
        },
        'sam_verified': _verifyRan
            ? {
                'object_found':
                    finalObject.isEmpty ? null : _verify?.objects[finalObject] != null,
                'reference_found':
                    finalRef.isEmpty ? null : _verify?.objects[finalRef] != null,
              }
            : null,
        'final': {
          'object_label': finalObject,
          'reference_label': finalRef,
          'reference_size_cm': finalCm,
          'rotation_center_frac':
              finalCenter == null ? null : [finalCenter.dx, finalCenter.dy],
        },
        'edited_fields': edited,
        'vlm_correct': edited.isEmpty,
      },
    ).catchError((_) {}); // never block the analysis on telemetry
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Set up the measurement')),
      body: _initError != null
          ? ErrorView(message: 'Could not open the video.\n$_initError')
          : _framePath == null
              ? const LoadingView(message: 'Loading video…')
              : _form(context),
    );
  }

  Widget _form(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        if (_suggesting) _suggestBanner(context, busy: true),
        if (!_suggesting && _suggestionApplied) _suggestBanner(context, busy: false),
        if (_suggestError != null) _suggestNotice(context, _suggestError!),
        const SizedBox(height: 12),
        Text('Tap the point it spins around',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        AspectRatio(
          aspectRatio: _imgW > 0 && _imgH > 0 ? _imgW / _imgH : 16 / 9,
          child: LayoutBuilder(
            builder: (context, constraints) {
              _lastBox = Size(constraints.maxWidth, constraints.maxHeight);
              return GestureDetector(
                onTapDown: (d) {
                  setState(() {
                    _centerFrac = Offset(
                      (d.localPosition.dx / _lastBox.width).clamp(0.0, 1.0),
                      (d.localPosition.dy / _lastBox.height).clamp(0.0, 1.0),
                    );
                  });
                },
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.file(File(_framePath!), fit: BoxFit.cover),
                      ..._overlayBoxes(scheme),
                      if (_centerFrac != null)
                        Positioned(
                          left: _centerFrac!.dx * _lastBox.width - 15,
                          top: _centerFrac!.dy * _lastBox.height - 15,
                          child: Icon(Icons.add_circle,
                              size: 30, color: scheme.primary),
                        ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
        const SizedBox(height: 8),
        Text(
          _centerFrac == null
              ? 'Tap the centre of the spin to begin.'
              : 'Centre set — tap again to fine-tune.',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: _centerFrac == null ? scheme.error : scheme.onSurfaceVariant),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _objectCtrl,
          decoration: const InputDecoration(
            labelText: "What's going in circles?",
            helperText: 'e.g. red ball, blue toy car, bottle cap',
          ),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _refCtrl,
          decoration: const InputDecoration(
            labelText: 'Spinning platform (for scale)',
            helperText: 'We measure the turntable/plate to turn pixels into real distances',
          ),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _sizeCtrl,
          decoration: InputDecoration(
            labelText: 'How wide is it, in cm? (optional)',
            helperText: _sizeHelper(),
            suffixText: 'cm',
          ),
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _sceneCtrl,
          minLines: 2,
          maxLines: 4,
          decoration: const InputDecoration(
            labelText: "What's happening in this video? (optional)",
            helperText: 'Who, where, why — used to write the learning material scenario',
            alignLabelWithHint: true,
          ),
        ),
        const SizedBox(height: 20),
        AsyncButton(
          outlined: true,
          icon: Icons.center_focus_strong,
          onPressed: _objectCtrl.text.trim().isEmpty &&
                  _refCtrl.text.trim().isEmpty
              ? null
              : _runVerify,
          child: const Text('Check the app can see them'),
        ),
        if (_verifyNote != null) ...[
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(
                _verifyNote!.contains('✓')
                    ? Icons.check_circle_outline
                    : Icons.info_outline,
                size: 16,
                color: _verifyNote!.contains('✓') ? scheme.primary : scheme.error,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(_verifyNote!,
                    style: Theme.of(context).textTheme.bodySmall),
              ),
            ],
          ),
        ],
        const SizedBox(height: 24),
        AsyncButton(
          icon: Icons.straighten,
          onPressed: _canSubmit ? _submit : null,
          child: const Text('Measure the motion'),
        ),
        const SizedBox(height: 8),
        if (!_canSubmit)
          Text(
            'Mark the centre and name both objects to continue.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant),
          ),
      ],
    );
  }

  String _sizeHelper() {
    final basis = _suggestion?.referenceObject?.sizeBasis;
    if (basis != null && basis.trim().isNotEmpty) return basis;
    return 'Leave blank to let the app estimate it';
  }

  Widget _boxOverlay(List<double> frac, Color color, String label, bool solid) {
    return Positioned(
      left: frac[0] * _lastBox.width,
      top: frac[1] * _lastBox.height,
      width: frac[2] * _lastBox.width,
      height: frac[3] * _lastBox.height,
      child: IgnorePointer(
        child: Container(
          decoration: BoxDecoration(
            border: Border.all(color: color, width: solid ? 2.5 : 1.5),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Align(
            alignment: Alignment.topLeft,
            child: Container(
              color: color,
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
              child: Text(label,
                  style: const TextStyle(color: Colors.white, fontSize: 10)),
            ),
          ),
        ),
      ),
    );
  }

  /// Prefer SAM3-verified boxes (solid); fall back to faint VLM suggestions.
  List<Widget> _overlayBoxes(ColorScheme scheme) {
    final v = _verify;
    final s = _suggestion;
    final out = <Widget>[];

    void add(String? label, List<double>? suggestBbox, Color color, String tag) {
      final verified = (label != null && v != null) ? v.objects[label] : null;
      final vf = verified == null ? null : v!.bboxFrac(verified.bbox);
      if (vf != null) {
        out.add(_boxOverlay(vf, color, '$tag ✓', true));
        return;
      }
      final sf = s?.bboxFrac(suggestBbox);
      if (sf != null) out.add(_boxOverlay(sf, color, tag, false));
    }

    add(_objectCtrl.text.trim().isEmpty ? null : _objectCtrl.text.trim(),
        s?.movingObject?.bbox, scheme.primary, 'object');
    add(_refCtrl.text.trim().isEmpty ? null : _refCtrl.text.trim(),
        s?.referenceObject?.bbox, scheme.tertiary, 'platform');
    return out;
  }

  Widget _suggestNotice(BuildContext context, String message) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(Icons.info_outline, size: 18, color: scheme.onErrorContainer),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: scheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }

  Widget _suggestBanner(BuildContext context, {required bool busy}) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: scheme.secondaryContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          if (busy)
            const SizedBox(
                height: 18,
                width: 18,
                child: CircularProgressIndicator(strokeWidth: 2))
          else
            Icon(Icons.auto_awesome, size: 18, color: scheme.onSecondaryContainer),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              busy
                  ? 'Looking at your video to suggest a setup…'
                  : 'Suggested setup filled in — check it and adjust if needed.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: scheme.onSecondaryContainer),
            ),
          ),
        ],
      ),
    );
  }
}
