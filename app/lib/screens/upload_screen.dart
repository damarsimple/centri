import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import 'annotate_screen.dart';

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key});

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  final _picker = ImagePicker();
  String? _path;
  String? _error;

  Future<void> _pick(ImageSource source) async {
    setState(() => _error = null);
    try {
      final file = await _picker.pickVideo(
        source: source,
        maxDuration: const Duration(seconds: 30),
      );
      if (file == null) return;
      setState(() => _path = file.path);
    } catch (e) {
      setState(() => _error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final name = _path?.split('/').last;

    return Scaffold(
      appBar: AppBar(title: const Text('Choose a video')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Keep the camera still. Capture a few seconds of one object '
                'moving in a circle, with the spinning platform fully in frame.',
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: scheme.onSurfaceVariant),
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _pick(ImageSource.camera),
                      icon: const Icon(Icons.videocam),
                      label: const Text('Record'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _pick(ImageSource.gallery),
                      icon: const Icon(Icons.photo_library_outlined),
                      label: const Text('Gallery'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              if (_error != null)
                Text(_error!, style: TextStyle(color: scheme.error)),
              if (name != null)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.movie_outlined),
                    title: Text(name, overflow: TextOverflow.ellipsis),
                    subtitle: Text('${File(_path!).lengthSync() ~/ 1024} KB'),
                  ),
                ),
              const Spacer(),
              FilledButton.icon(
                onPressed: _path == null
                    ? null
                    : () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => AnnotateScreen(videoPath: _path!),
                          ),
                        ),
                icon: const Icon(Icons.arrow_forward),
                label: const Text('Continue'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
