import pytest
from worker.event_parser import parse_pi_event


class TestParsePiEvent:
    def test_step1_parsing_scene_metadata(self):
        line = "Some log output [STEP START] step1 more output"
        log_str, step, pct = parse_pi_event(line)
        assert step == "Parsing scene & metadata"
        assert pct == 10

    def test_step5_trajectory_cleaning(self):
        line = "Processing [STEP START] step5 complete"
        log_str, step, pct = parse_pi_event(line)
        assert step == "Trajectory cleaning"
        assert pct == 55

    def test_step8_kinematics_summary(self):
        line = "Final step [STEP START] step8 done"
        log_str, step, pct = parse_pi_event(line)
        assert step == "Kinematics & summary"
        assert pct == 88

    def test_subagent_generating_figures(self):
        line = "Running Subagent for figure generation"
        log_str, step, pct = parse_pi_event(line)
        assert step == "Generating figures & questions"
        assert pct == 94

    def test_pdflatex_compiling_report(self):
        line = "Building pdflatex output"
        log_str, step, pct = parse_pi_event(line)
        assert step == "Compiling report"
        assert pct == 97

    def test_non_step_line_returns_none(self):
        line = "Some random log message without step info"
        log_str, step, pct = parse_pi_event(line)
        assert step is None
        assert pct is None

    def test_empty_line(self):
        line = ""
        log_str, step, pct = parse_pi_event(line)
        assert step is None
        assert pct is None