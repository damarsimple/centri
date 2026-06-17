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
    std::vector<Detection> trajectory;
};

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
    std::vector<std::string> labels;
    std::vector<sam3_box> initial_boxes;
    bool use_gpu = true;
    int n_threads = 4;
    int n_frames = -1;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--model" && i + 1 < argc) { model_path = argv[++i]; }
        else if (arg == "--video" && i + 1 < argc) { video_path = argv[++i]; }
        else if (arg == "--n-frames" && i + 1 < argc) { n_frames = atoi(argv[++i]); }
        else if (arg == "--boxes" && i + 1 < argc) {
            // Expected format: label,x0,y0,x1,y1;label2,x0,y0,x1,y1...
            std::string boxes_str = argv[++i];
            size_t start = 0, end;
            while ((end = boxes_str.find(';', start)) != std::string::npos) {
                std::string item = boxes_str.substr(start, end - start);
                size_t c1 = item.find(',');
                size_t c2 = item.find(',', c1+1);
                size_t c3 = item.find(',', c2+1);
                size_t c4 = item.find(',', c3+1);
                labels.push_back(item.substr(0, c1));
                sam3_box b;
                b.x0 = std::stof(item.substr(c1+1, c2-c1-1));
                b.y0 = std::stof(item.substr(c2+1, c3-c2-1));
                b.x1 = std::stof(item.substr(c3+1, c4-c3-1));
                b.y1 = std::stof(item.substr(c4+1));
                initial_boxes.push_back(b);
                start = end + 1;
            }
            std::string item = boxes_str.substr(start);
            if (!item.empty()) {
                size_t c1 = item.find(',');
                size_t c2 = item.find(',', c1+1);
                size_t c3 = item.find(',', c2+1);
                size_t c4 = item.find(',', c3+1);
                labels.push_back(item.substr(0, c1));
                sam3_box b;
                b.x0 = std::stof(item.substr(c1+1, c2-c1-1));
                b.y0 = std::stof(item.substr(c2+1, c3-c2-1));
                b.x1 = std::stof(item.substr(c3+1, c4-c3-1));
                b.y1 = std::stof(item.substr(c4+1));
                initial_boxes.push_back(b);
            }
        }
        else if (arg == "--no-gpu") { use_gpu = false; }
        else if (arg == "--threads" && i + 1 < argc) { n_threads = atoi(argv[++i]); }
    }

    if (model_path.empty() || video_path.empty() || initial_boxes.empty()) {
        std::cerr << "Usage: sam2_api_worker --model <path> --video <path> --boxes \"label,x0,y0,x1,y1;...\"" << std::endl;
        return 1;
    }

    sam3_params params;
    params.model_path = model_path;
    params.use_gpu = use_gpu;
    params.n_threads = n_threads;

    auto model = sam3_load_model(params);
    if (!model) return 1;
    auto state = sam3_create_state(*model, params);
    if (!state) return 1;

    auto vinfo = sam3_get_video_info(video_path);
    if (vinfo.n_frames <= 0) return 1;

    sam3_visual_track_params vtp;
    auto tracker = sam3_create_visual_tracker(*model, vtp);

    // Frame 0: Add instances
    auto frame0 = sam3_decode_video_frame(video_path, 0);
    if (frame0.data.empty()) return 1;
    if (!sam3_encode_image(*state, *model, frame0)) return 1;

    std::map<int, TargetResult> active_targets;
    for (size_t i = 0; i < initial_boxes.size(); i++) {
        sam3_pvs_params pvs;
        pvs.box = initial_boxes[i];
        pvs.use_box = true;
        
        int inst_id = sam3_tracker_add_instance(*tracker, *state, *model, pvs);
        if (inst_id >= 0) {
            TargetResult tr;
            tr.label = labels[i];
            tr.instance_id = inst_id;
            float cx = (initial_boxes[i].x0 + initial_boxes[i].x1) / 2.0f;
            float cy = (initial_boxes[i].y0 + initial_boxes[i].y1) / 2.0f;
            tr.trajectory.push_back({0, cx, cy, initial_boxes[i].x0, initial_boxes[i].y0, initial_boxes[i].x1, initial_boxes[i].y1});
            active_targets[inst_id] = tr;
        }
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

    std::cout << "{\n  \"status\": \"success\",\n  \"trajectories\": {\n";
    bool first = true;
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
    std::cout << "\n  }\n}" << std::endl;

    return 0;
}
