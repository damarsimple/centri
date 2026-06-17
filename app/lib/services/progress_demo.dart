// A scripted stand-in for the live agent feed, so the interactive progress
// view can be experienced without the backend running. The shape of every
// frame matches exactly what /status returns (see app/progress_feed.py), so
// the UI code is identical for demo and real runs.
import '../models/job.dart';

const _stageDefs = [
  ['inspect', 'Look at the video'],
  ['track', 'Follow the moving object'],
  ['trajectory', 'Find the circular path'],
  ['kinematics', 'Measure speed & acceleration'],
  ['visuals', 'Draw the motion & graphs'],
  ['report', 'Write up the results'],
];

List<StageItem> _stages(String activeKey, Set<String> done) {
  return _stageDefs.map((d) {
    final key = d[0];
    final status = done.contains(key)
        ? 'done'
        : (key == activeKey ? 'active' : 'pending');
    return StageItem(key: key, label: d[1], status: status);
  }).toList();
}

class _Step {
  final String phase;
  final Set<String> done;
  final String currentAction;
  final String? thinking;
  final ActivityItem activity; // appended to the running feed
  final int pct;
  const _Step(this.phase, this.done, this.currentAction, this.thinking,
      this.activity, this.pct);
}

ActivityItem _act(int seq, String kind, String title,
        {String? detail, String status = 'done'}) =>
    ActivityItem(seq: seq, kind: kind, title: title, detail: detail, status: status);

final _script = <_Step>[
  _Step('inspect', {}, 'Looking at your video',
      'First I\'ll check how big the video is and how many frames it shows each second — I need that to turn frame numbers into real seconds.',
      _act(1, 'run', 'Looking at your video',
          detail: 'Checking the size, frame rate and length', status: 'running'),
      6),
  _Step('track', {'inspect'}, 'Following the spinning object',
      'It\'s a 7-second clip at 30 frames a second. The bright disc is the thing that\'s moving, so I\'ll follow its centre in every single frame.',
      _act(2, 'track', 'Following the spinning object',
          detail: 'Marking where the object is in each frame', status: 'running'),
      18),
  _Step('track', {'inspect'}, 'Following the spinning object',
      'I found the object in 221 frames. A few near the fastest part look a little shaky, so I\'ll smooth them out before drawing its path.',
      _act(3, 'read', 'Collecting the tracked points',
          detail: '221 positions found across the clip', status: 'done'),
      28),
  _Step('trajectory', {'inspect', 'track'}, 'Finding the circular path',
      'Now I\'ll fit a circle through all those points. The centre sits near the middle and the radius stays steady — so it really is going round in a clean circle.',
      _act(4, 'run', 'Fitting the circular path',
          detail: 'Drawing the best circle through the points', status: 'running'),
      44),
  _Step('kinematics', {'inspect', 'track', 'trajectory'},
      'Measuring how fast it spins',
      'I\'ll see how much the angle changes each frame to get the spin rate. Measuring the spinning platform (its real size) lets me turn pixels into real centimetres.',
      _act(5, 'run', 'Measuring the spin rate',
          detail: 'Turning the changing angle into a speed', status: 'running'),
      58),
  _Step('kinematics', {'inspect', 'track', 'trajectory'},
      'Measuring how fast it spins',
      'It spins about 6.4 radians a second — roughly 61 turns a minute, and very steady. That gives a centripetal acceleration of about 9.8 m/s². Saving the numbers.',
      _act(6, 'write', 'Saving your measurements',
          detail: 'Speed and acceleration at every moment', status: 'done'),
      66),
  _Step('visuals', {'inspect', 'track', 'trajectory', 'kinematics'},
      'Drawing the motion onto your video',
      'I\'ll draw the path, a speed arrow and an acceleration arrow onto each frame, so you can actually see the physics happening as it spins.',
      _act(7, 'run', 'Drawing on your video',
          detail: 'Adding the path, speed and acceleration arrows', status: 'running'),
      80),
  _Step('visuals', {'inspect', 'track', 'trajectory', 'kinematics'},
      'Drawing the motion onto your video',
      'Putting the path and the graphs of speed and acceleration together into one summary picture you can read at a glance.',
      _act(8, 'write', 'Making the summary picture',
          detail: 'The path and graphs in one view', status: 'done'),
      88),
  _Step('report', {'inspect', 'track', 'trajectory', 'kinematics', 'visuals'},
      'Writing up your results',
      'Finally I\'ll fill in your worksheet and the teacher\'s answer key with everything I measured, so you can check your understanding.',
      _act(9, 'write', 'Writing your report',
          detail: 'Your worksheet and the teacher\'s answer key', status: 'running'),
      96),
];

/// Emits frames roughly every [tick], building up the activity feed as it goes,
/// then finishes with a `done` status.
Stream<JobStatus> demoProgressStream(
    {Duration tick = const Duration(milliseconds: 1400)}) async* {
  final activities = <ActivityItem>[];
  final start = DateTime.now();
  int elapsed() => DateTime.now().difference(start).inSeconds;

  for (final s in _script) {
    // If the previous step's activity was "running", mark it done as we move on.
    if (activities.isNotEmpty && activities.last.isRunning) {
      final prev = activities.removeLast();
      activities.add(_act(prev.seq, prev.kind, prev.title,
          detail: prev.detail, status: 'done'));
    }
    activities.add(s.activity);
    yield JobStatus(
      jobId: 'demo',
      status: 'running',
      step: _stageDefs.firstWhere((d) => d[0] == s.phase)[1],
      progressPct: s.pct,
      message: s.currentAction,
      elapsedS: elapsed(),
      phase: s.phase,
      currentAction: s.currentAction,
      thinking: s.thinking,
      stages: _stages(s.phase, s.done),
      activities: List.of(activities),
    );
    await Future.delayed(tick);
  }

  // Close out the final running activity and report done.
  if (activities.isNotEmpty && activities.last.isRunning) {
    final prev = activities.removeLast();
    activities.add(_act(prev.seq, prev.kind, prev.title,
        detail: prev.detail, status: 'done'));
  }
  yield JobStatus(
    jobId: 'demo',
    status: 'done',
    step: 'All done',
    progressPct: 100,
    message: 'Your results are ready',
    elapsedS: elapsed(),
    phase: 'report',
    currentAction: 'Your results are ready',
    thinking: null,
    stages: _stages('', _stageDefs.map((d) => d[0]).toSet()),
    activities: List.of(activities),
  );
}
