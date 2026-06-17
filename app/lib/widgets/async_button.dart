import 'package:flutter/material.dart';

/// A FilledButton that shows a spinner while its async [onPressed] runs and
/// prevents double-taps. Pass null to disable.
class AsyncButton extends StatefulWidget {
  final Future<void> Function()? onPressed;
  final Widget child;
  final IconData? icon;
  final bool outlined;

  const AsyncButton({
    super.key,
    required this.onPressed,
    required this.child,
    this.icon,
    this.outlined = false,
  });

  @override
  State<AsyncButton> createState() => _AsyncButtonState();
}

class _AsyncButtonState extends State<AsyncButton> {
  bool _busy = false;

  Future<void> _run() async {
    if (widget.onPressed == null || _busy) return;
    setState(() => _busy = true);
    try {
      await widget.onPressed!();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null && !_busy;
    const spinner = SizedBox(
      height: 20,
      width: 20,
      child: CircularProgressIndicator(strokeWidth: 2),
    );
    if (_busy) {
      return widget.outlined
          ? const OutlinedButton(onPressed: null, child: spinner)
          : const FilledButton(onPressed: null, child: spinner);
    }
    if (widget.outlined) {
      return widget.icon != null
          ? OutlinedButton.icon(
              onPressed: enabled ? _run : null,
              icon: Icon(widget.icon),
              label: widget.child,
            )
          : OutlinedButton(onPressed: enabled ? _run : null, child: widget.child);
    }
    if (widget.icon != null) {
      return FilledButton.icon(
        onPressed: enabled ? _run : null,
        icon: Icon(widget.icon),
        label: widget.child,
      );
    }
    return FilledButton(onPressed: enabled ? _run : null, child: widget.child);
  }
}
