#include "sam3.h"
#include <iostream>
#include <vector>
#include <string>
#include <map>
#include <iomanip>
#include <cmath>
#include <algorithm>

struct Target {
    std::string label;
    std::vector<sam3_point> points;
    std::vector<sam3_point> neg_points;
};

struct Point {
    float x, y;
};

struct Detection {
    int frame;
    float cx, cy;
    float x0, y0, x1, y1;
    std::vector<Point> oriented_box; // 4 corners
};

struct TargetResult {
    std::string label;
    int instance_id = -1;
    std::vector<Detection> trajectory;
};

// Simple PCA-based Oriented Bounding Box
std::vector<Point> get_oriented_box(const sam3_mask& mask) {
    if (mask.data.empty()) return {};

    double sum_x = 0, sum_y = 0, sum_xx = 0, sum_yy = 0, sum_xy = 0;
    int count = 0;

    for (int y = 0; y < mask.height; y++) {
        for (int x = 0; x < mask.width; x++) {
            if (mask.data[y * mask.width + x] > 128) {
                sum_x += x;
                sum_y += y;
                sum_xx += (double)x * x;
                sum_yy += (double)y * y;
                sum_xy += (double)x * y;
                count++;
            }
        }
    }

    if (count < 5) return {};

    double mx = sum_x / count;
    double my = sum_y / count;
    double var_x = sum_xx / count - mx * mx;
    double var_y = sum_yy / count - my * my;
    double cov_xy = sum_xy / count - mx * my;

    // Eigenvalues of [[var_x, cov_xy], [cov_xy, var_y]]
    double tr = var_x + var_y;
    double det = var_x * var_y - cov_xy * cov_xy;
    double diff = sqrt(tr * tr / 4.0 - det);
    double lambda1 = tr / 2.0 + diff;
    double lambda2 = tr / 2.0 - diff;

    // Eigenvector for lambda1 (Principal Axis)
    double vx = cov_xy;
    double vy = lambda1 - var_x;
    double mag = sqrt(vx * vx + vy * vy);
    if (mag < 1e-6) { vx = 1; vy = 0; } else { vx /= mag; vy /= mag; }

    // Orthogonal vector
    double ux = -vy;
    double uy = vx;

    // Project all points and find bounds
    double min_v = 1e18, max_v = -1e18, min_u = 1e18, max_u = -1e18;
    for (int y = 0; y < mask.height; y++) {
        for (int x = 0; x < mask.width; x++) {
            if (mask.data[y * mask.width + x] > 128) {
                double dx = x - mx;
                double dy = y - my;
                double v = dx * vx + dy * vy;
                double u = dx * ux + dy * uy;
                min_v = std::min(min_v, v); max_v = std::max(max_v, v);
                min_u = std::min(min_u, u); max_u = std::max(max_u, u);
            }
        }
    }

    // 4 corners in local space projected back to global
    auto back_proj = [&](double v, double u) {
        return Point{(float)(mx + v * vx + u * ux), (float)(my + v * vy + u * uy)};
    };

    return {
        back_proj(min_v, min_u), back_proj(max_v, min_u),
        back_proj(max_v, max_u), back_proj(min_v, max_u)
    };
}

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
    std::string model_sam3_path = "./models/sam3-q4_0.ggml";
    std::string model_sam2_path = "./models/sam2.1_hiera_tiny_f16.ggml";
    std::string video_path;
    std::vector<Target> targets;
    bool use_gpu = true;
    int n_threads = 8;
    int n_frames = -1;
    int start_frame = 0;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--model3" && i + 1 < argc) { model_sam3_path = argv[++i]; }
        else if (arg == "--model2" && i + 1 < argc) { model_sam2_path = argv[++i]; }
        else if (arg == "--video" && i + 1 < argc) { video_path = argv[++i]; }
        else if (arg == "--n-frames" && i + 1 < argc) { n_frames = atoi(argv[++i]); }
        else if (arg == "--start-frame" && i + 1 < argc) { start_frame = atoi(argv[++i]); }
        else if (arg == "--targets" && i + 1 < argc) {
            std::string t_str = argv[++i];
            size_t p = 0;
            while (p < t_str.size()) {
                if (t_str[p] == '[' || t_str[p] == ',' || t_str[p] == ' ' || t_str[p] == ']') { p++; continue; }
                if (t_str[p] == '"') {
                    size_t q = t_str.find('"', p + 1);
                    targets.push_back({t_str.substr(p + 1, q - p - 1), {}, {}});
                    p = q + 1;
                } else if (t_str[p] == '{') {
                    size_t q = t_str.find('}', p);
                    std::string obj = t_str.substr(p, q - p + 1);
                    Target t;
                    size_t lp = obj.find("\"label\":");
                    if (lp != std::string::npos) {
                        size_t lq1 = obj.find('"', lp + 8);
                        size_t lq2 = obj.find('"', lq1 + 1);
                        t.label = obj.substr(lq1 + 1, lq2 - lq1 - 1);
                    }
                    auto extract_pts = [&](const std::string& key, std::vector<sam3_point>& out) {
                        size_t k_pos = obj.find(key);
                        if (k_pos == std::string::npos) return;
                        size_t start_pts = obj.find('[', k_pos);
                        size_t end_pts = obj.find(']', obj.find(']', start_pts) + 1);
                        std::string s = obj.substr(start_pts, end_pts - start_pts + 1);
                        size_t cur = 0;
                        while ((cur = s.find('[', cur + 1)) != std::string::npos) {
                            float x, y;
                            if (sscanf(s.c_str() + cur, "[%f,%f]", &x, &y) == 2) {
                                out.push_back({x, y});
                            }
                        }
                    };
                    extract_pts("\"points\":", t.points);
                    extract_pts("\"neg_points\":", t.neg_points);
                    targets.push_back(t);
                    p = q + 1;
                } else { p++; }
            }
        }
    }

    if (video_path.empty() || targets.empty()) {
        std::cerr << "Usage: sam2_hybrid_worker --video <path> --targets <json_array>" << std::endl;
        return 1;
    }

    auto vinfo = sam3_get_video_info(video_path);
    if (vinfo.n_frames <= 0) return 1;
    if (n_frames < 0 || (start_frame + n_frames) > vinfo.n_frames) {
        n_frames = vinfo.n_frames - start_frame;
    }

    sam3_params p3;
    p3.model_path = model_sam3_path;
    p3.use_gpu = use_gpu;
    p3.n_threads = n_threads;

    auto model3 = sam3_load_model(p3);
    if (!model3) return 1;
    auto state3 = sam3_create_state(*model3, p3);

    auto first_frame = sam3_decode_video_frame(video_path, start_frame);
    if (first_frame.data.empty()) return 1;
    if (!sam3_encode_image(*state3, *model3, first_frame)) return 1;

    std::vector<std::pair<std::string, sam3_detection>> found_targets;
    for (const auto& target : targets) {
        if (!target.points.empty()) {
            sam3_pvs_params pvs;
            pvs.pos_points = target.points;
            pvs.neg_points = target.neg_points;
            fprintf(stderr, "Initializing '%s' with %zu pos, %zu neg points\n", 
                    target.label.c_str(), target.points.size(), target.neg_points.size());
            for (auto pt : target.points) fprintf(stderr, "  POS: [%.1f, %.1f]\n", pt.x, pt.y);
            for (auto pt : target.neg_points) fprintf(stderr, "  NEG: [%.1f, %.1f]\n", pt.x, pt.y);
            
            auto res = sam3_segment_pvs(*state3, *model3, pvs);
            if (!res.detections.empty()) {
                found_targets.push_back({target.label, res.detections[0]});
            }
        } else {
            sam3_pcs_params pcs;
            pcs.text_prompt = target.label;
            pcs.score_threshold = 0.15f;
            auto res = sam3_segment_pcs(*state3, *model3, pcs);
            if (!res.detections.empty()) {
                found_targets.push_back({target.label, res.detections[0]});
            }
        }
    }

    sam3_params p2;
    p2.model_path = model_sam2_path;
    p2.use_gpu = use_gpu;
    p2.n_threads = n_threads;

    auto model2 = sam3_load_model(p2);
    if (!model2) return 1;
    auto state2 = sam3_create_state(*model2, p2);

    sam3_visual_track_params vtp;
    auto tracker = sam3_create_visual_tracker(*model2, vtp);
    if (!sam3_encode_image(*state2, *model2, first_frame)) return 1;

    std::map<int, TargetResult> active_targets;
    for (const auto& found : found_targets) {
        sam3_pvs_params pvs;
        pvs.box = found.second.box;
        pvs.use_box = true;
        int inst_id = sam3_tracker_add_instance(*tracker, *state2, *model2, pvs);
        if (inst_id >= 0) {
            TargetResult tr;
            tr.label = found.first;
            tr.instance_id = inst_id;
            float cx = (found.second.box.x0 + found.second.box.x1) / 2.0f;
            float cy = (found.second.box.y0 + found.second.box.y1) / 2.0f;
            tr.trajectory.push_back({start_frame, cx, cy, found.second.box.x0, found.second.box.y0, found.second.box.x1, found.second.box.y1, get_oriented_box(found.second.mask)});
            active_targets[inst_id] = tr;
        }
    }

    char pipe_cmd[1024];
    float start_time_s = (float)start_frame / vinfo.fps;
    snprintf(pipe_cmd, sizeof(pipe_cmd),
             "ffmpeg -ss %.3f -nostdin -loglevel error -i \"%s\" "
             "-frames:v %d -f rawvideo -pix_fmt rgb24 pipe:1 2>/dev/null",
             start_time_s, video_path.c_str(), n_frames);
    
    FILE* pipe = popen(pipe_cmd, "r");
    if (!pipe) return 1;

    size_t frame_bytes = vinfo.width * vinfo.height * 3;
    std::vector<uint8_t> buffer(frame_bytes);

    if (fread(buffer.data(), 1, frame_bytes, pipe) == frame_bytes) {
        for (int f = 1; f < n_frames; f++) {
            if (fread(buffer.data(), 1, frame_bytes, pipe) != frame_bytes) break;

            sam3_image frame;
            frame.width = vinfo.width; frame.height = vinfo.height; frame.channels = 3;
            frame.data = buffer;

            auto res = sam3_propagate_frame(*tracker, *state2, *model2, frame);
            for (const auto& det : res.detections) {
                if (active_targets.count(det.instance_id)) {
                    float cx = (det.box.x0 + det.box.x1) / 2.0f;
                    float cy = (det.box.y0 + det.box.y1) / 2.0f;
                    active_targets[det.instance_id].trajectory.push_back({
                        start_frame + f, cx, cy, 
                        det.box.x0, det.box.y0, det.box.x1, det.box.y1,
                        get_oriented_box(det.mask)
                    });
                }
            }
        }
    }
    pclose(pipe);

    std::cout << "{\n  \"status\": \"success\",\n  \"trajectories\": {\n";
    bool first = true;
    for (auto& pair : active_targets) {
        if (!first) std::cout << ",\n";
        std::cout << "    \"" << json_escape(pair.second.label) << "\": [\n";
        bool f_first = true;
        for (const auto& d : pair.second.trajectory) {
            if (!f_first) std::cout << ",\n";
            std::cout << "      {\"frame\": " << d.frame << ", \"cx\": " << d.cx << ", \"cy\": " << d.cy 
                      << ", \"bbox\": [" << d.x0 << ", " << d.y0 << ", " << d.x1 << ", " << d.y1 << "]";
            if (!d.oriented_box.empty()) {
                std::cout << ", \"obox\": [[ " << d.oriented_box[0].x << "," << d.oriented_box[0].y << "],["
                          << d.oriented_box[1].x << "," << d.oriented_box[1].y << "],["
                          << d.oriented_box[2].x << "," << d.oriented_box[2].y << "],["
                          << d.oriented_box[3].x << "," << d.oriented_box[3].y << "]]";
            }
            std::cout << "}";
            f_first = false;
        }
        std::cout << "\n    ]";
        first = false;
    }
    std::cout << "\n  }\n}" << std::endl;

    return 0;
}
