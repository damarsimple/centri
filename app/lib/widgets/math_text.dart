import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';

/// Renders a string that mixes plain text with LaTeX math, so tutor/worksheet
/// content shows proper formulas. Recognises `$$…$$`, `$…$`, `\(…\)`, `\[…\]`.
/// Falls back to the raw text for any segment LaTeX can't parse.
class MathText extends StatelessWidget {
  final String text;
  final TextStyle? style;
  const MathText(this.text, {super.key, this.style});

  static final _re = RegExp(
    r'\$\$(.+?)\$\$|\$(.+?)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]',
    dotAll: true,
  );

  @override
  Widget build(BuildContext context) {
    final base = style ?? DefaultTextStyle.of(context).style;

    if (!text.contains(r'$') && !text.contains(r'\(') && !text.contains(r'\[')) {
      return Text(text, style: base);
    }

    final spans = <InlineSpan>[];
    int last = 0;
    for (final m in _re.allMatches(text)) {
      if (m.start > last) {
        spans.add(TextSpan(text: text.substring(last, m.start)));
      }
      final expr = m.group(1) ?? m.group(2) ?? m.group(3) ?? m.group(4) ?? '';
      final display = m.group(1) != null || m.group(4) != null; // $$…$$ or \[…\]
      spans.add(WidgetSpan(
        alignment: PlaceholderAlignment.middle,
        baseline: TextBaseline.alphabetic,
        child: Math.tex(
          expr,
          mathStyle: display ? MathStyle.display : MathStyle.text,
          textStyle: base,
          onErrorFallback: (_) => Text(
            display ? '\$\$$expr\$\$' : '\$$expr\$',
            style: base,
          ),
        ),
      ));
      last = m.end;
    }
    if (last < text.length) spans.add(TextSpan(text: text.substring(last)));
    if (spans.isEmpty) return Text(text, style: base);

    return Text.rich(TextSpan(style: base, children: spans));
  }
}
