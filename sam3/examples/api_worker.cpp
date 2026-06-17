#include "sam3.h"
#include <iostream>
#include <vector>
#include <string>
#include <map>
#include <iomanip>

struct Detection {
    int frame;
    float cx, cy;
    float x0, y0, x1, y1;
};

struct TargetResult {
    std::string label;
    int instance_id = -1;
    float initial_conf = 0.0f;
    std::vector<Detection> trajectory;
};

// Very simple JSON string escaper
std::string json_escape(const std::string& s) {
    std::string res;
    for (char c : s) {
        if (c == '"') res += "\\\"";
        else if (c == '\\') res += "\\\\";
        else res += c;
    }
    return res;
}

int main(int argc, char** argv) {
    std::string model_path;
    std::string video_path;
    std::vector<std::string> targets;
    bool use_gpu = true;
    int n_threads = 4;
    int n_frames = -1;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--model" && i + 1 < argc) { model_path = argv[++i]; }
        else if (arg == "--video" && i + 1 < argc) { video_path = argv[++i]; }
        else if (arg == "--n-frames" && i + 1 < argc) { n_frames = atoi(argv[++i]); }
        else if (arg == "--targets" && i + 1 < argc) {
            std::string t_str = argv[++i];
            // Primitive parsing: if starts with [, try to strip and split by comma
            if (t_str.front() == '[') {
                std::string inner = t_str.substr(1, t_str.size() - 2);
                size_t start = 0, end;
                while ((end = inner.find(',', start)) != std::string::npos) {
                    std::string t = inner.substr(start, end - start);
                    // strip quotes
                    if (t.front() == '"') t = t.substr(1, t.size() - 2);
                    targets.push_back(t);
                    start = end + 1;
                }
                std::string t = inner.substr(start);
                if (t.front() == '"') t = t.substr(1, t.size() - 2);
                targets.push_back(t);
            } else {
                targets.push_back(t_str);
            }
        }
        else if (arg == "--no-gpu") { use_gpu = false; }
        else if (arg == "--threads" && i + 1 < argc) { n_threads = atoi(argv[++i]); }
    }

    if (model_path.empty() || video_path.empty() || targets.empty()) {
        std::cerr << "Usage: api_worker --model <path> --video <path> --targets <json_array>" << std::endl;
        return 1;
    }

    sam3_params params;
    params.model_path = model_path;
    params.use_gpu = use_gpu;
    params.n_threads = n_threads;

    auto model = sam3_load_model(params);
    if (!model) {
        std::cerr << "Failed to load model" << std::endl;
        return 1;
    }

    auto state = sam3_create_state(*model, params);
    if (!state) {
        std::cerr << "Failed to create state" << std::endl;
        return 1;
    }

    auto vinfo = sam3_get_video_info(video_path);
    if (vinfo.n_frames <= 0) {
        std::cerr << "Failed to get video info or video empty" << std::endl;
        return 1;
    }

    sam3_visual_track_params vtp;
    auto tracker = sam3_create_visual_tracker(*model, vtp);

    // Process Frame 0 for detection
    auto frame0 = sam3_decode_video_frame(video_path, 0);
    if (frame0.data.empty()) {
        std::cerr << "Failed to decode frame 0" << std::endl;
        return 1;
    }

    if (!sam3_encode_image(*state, *model, frame0)) {
        std::cerr << "Failed to encode frame 0" << std::endl;
        return 1;
    }

    std::map<int, TargetResult> active_targets;
    std::map<std::string, float> detections;

    for (const auto& target : targets) {
        sam3_pcs_params pcs;
        pcs.text_prompt = target;
        pcs.score_threshold = 0.1f;
        auto res = sam3_segment_pcs(*state, *model, pcs);

        std::cerr << "Searching for '" << target << "'... found " << res.detections.size() << " candidates" << std::endl;

        if (!res.detections.empty()) {
            const auto& best = res.detections[0];
            sam3_pvs_params pvs;
            pvs.box = best.box;
            pvs.use_box = true;
            
            int inst_id = sam3_tracker_add_instance(*tracker, *state, *model, pvs);
            if (inst_id >= 0) {
                TargetResult tr;
                tr.label = target;
                tr.instance_id = inst_id;
                tr.initial_conf = best.score;
                
                float cx = (best.box.x0 + best.box.x1) / 2.0f;
                float cy = (best.box.y0 + best.box.y1) / 2.0f;
                tr.trajectory.push_back({0, cx, cy, best.box.x0, best.box.y0, best.box.x1, best.box.y1});
                
                active_targets[inst_id] = tr;
                detections[target] = best.score;
            }
        }
    }

    if (active_targets.empty()) {
        std::cerr << "No targets found in frame 0" << std::endl;
        return 1;
    }

    if (n_frames < 0 || n_frames > vinfo.n_frames) n_frames = vinfo.n_frames;

    for (int f = 1; f < n_frames; f++) {
        auto frame = sam3_decode_video_frame(video_path, f);
        if (frame.data.empty()) break;

        auto res = sam3_propagate_frame(*tracker, *state, *model, frame);
        
        for (const auto& det : res.detections) {
            if (active_targets.count(det.instance_id)) {
                float cx = (det.box.x0 + det.box.x1) / 2.0f;
                float cy = (det.box.y0 + det.box.y1) / 2.0f;
                active_targets[det.instance_id].trajectory.push_back({f, cx, cy, det.box.x0, det.box.y0, det.box.x1, det.box.y1});
            }
        }
    }

    // Manual JSON output
    std::cout << "{\n";
    std::cout << "  \"status\": \"success\",\n";
    std::cout << "  \"detections\": {\n";
    bool first = true;
    for (auto const& [label, conf] : detections) {
        if (!first) std::cout << ",\n";
        std::cout << "    \"" << json_escape(label) << "\": " << conf;
        first = false;
    }
    std::cout << "\n  },\n";
    std::cout << "  \"trajectories\": {\n";
    first = true;
    for (auto& pair : active_targets) {
        if (!first) std::cout << ",\n";
        std::cout << "    \"" << json_escape(pair.second.label) << "\": [\n";
        bool f_first = true;
        for (const auto& d : pair.second.trajectory) {
            if (!f_first) std::cout << ",\n";
            std::cout << "      {\"frame\": " << d.frame << ", \"cx\": " << d.cx << ", \"cy\": " << d.cy 
                      << ", \"bbox\": [" << d.x0 << ", " << d.y0 << ", " << d.x1 << ", " << d.y1 << "]}";
            f_first = false;
        }
        std::cout << "\n    ]";
        first = false;
    }
    std::cout << "\n  }\n";
    std::cout << "}" << std::endl;

    return 0;
}
