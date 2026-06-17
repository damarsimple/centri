/**
 * demo_track — visual tracking demo with mask overlay output.
 *
 * Tracks an object (point click) across video frames using SAM2/SAM3,
 * renders colored mask overlays onto each frame, and writes output as
 * individual PNGs or an mp4 video (via ffmpeg pipe).
 *
 * Usage:
 *   demo_track --model <path> --video <path> [options]
 *
 * Options:
 *   --model <path>      Model .ggml file
 *   --video <path>      Input video        (default: data/test_video.mp4)
 *   --point-x <f>       Click point X      (default: 315.0)
 *   --point-y <f>       Click point Y      (default: 250.0)
 *   --n-frames <n>      Frames to track    (default: 30)
 *   --output <path>     Output video       (default: demo_output.mp4)
 *   --no-gpu            Force CPU backend
 */

#include "sam3.h"
#include "ggml.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#ifdef _WIN32
#include <io.h>
#define popen _popen
#define pclose _pclose
#define SAM3_NULL_DEV    "NUL"
#define SAM3_POPEN_WRITE "wb"
#else
#define SAM3_NULL_DEV    "/dev/null"
#define SAM3_POPEN_WRITE "w"
#endif

// stb_image_write for PNG output (implementation already in libsam3)
#include "stb_image_write.h"

static void overlay_mask(uint8_t* rgb, int w, int h,
                          const sam3_mask& mask,
                          uint8_t mr, uint8_t mg, uint8_t mb, int alpha) {
    if (mask.width != w || mask.height != h) return;
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            if (mask.data[y * w + x] > 0) {
                int idx = (y * w + x) * 3;
                rgb[idx + 0] = (uint8_t)((rgb[idx + 0] * (255 - alpha) + mr * alpha) / 255);
                rgb[idx + 1] = (uint8_t)((rgb[idx + 1] * (255 - alpha) + mg * alpha) / 255);
                rgb[idx + 2] = (uint8_t)((rgb[idx + 2] * (255 - alpha) + mb * alpha) / 255);
            }
        }
    }
}

static void draw_mask_outline(uint8_t* rgb, int w, int h,
                               const sam3_mask& mask,
                               uint8_t r, uint8_t g, uint8_t b, int thickness) {
    if (mask.width != w || mask.height != h) return;
    for (int y = 1; y < h - 1; y++) {
        for (int x = 1; x < w - 1; x++) {
            bool is_edge = false;
            if (mask.data[y * w + x] > 0) {
                // Check 4-neighbors for edge detection
                if (mask.data[(y-1)*w + x] == 0 || mask.data[(y+1)*w + x] == 0 ||
                    mask.data[y*w + (x-1)] == 0 || mask.data[y*w + (x+1)] == 0) {
                    is_edge = true;
                }
            }
            if (is_edge) {
                for (int dy = -thickness; dy <= thickness; dy++) {
                    for (int dx = -thickness; dx <= thickness; dx++) {
                        int px = x + dx, py = y + dy;
                        if (px >= 0 && px < w && py >= 0 && py < h) {
                            int idx = (py * w + px) * 3;
                            rgb[idx + 0] = r;
                            rgb[idx + 1] = g;
                            rgb[idx + 2] = b;
                        }
                    }
                }
            }
        }
    }
}

static void draw_circle(uint8_t* rgb, int w, int h,
                         int cx, int cy, int radius,
                         uint8_t r, uint8_t g, uint8_t b) {
    for (int dy = -radius; dy <= radius; dy++) {
        for (int dx = -radius; dx <= radius; dx++) {
            if (dx*dx + dy*dy <= radius*radius) {
                int px = cx + dx, py = cy + dy;
                if (px >= 0 && px < w && py >= 0 && py < h) {
                    int idx = (py * w + px) * 3;
                    rgb[idx + 0] = r;
                    rgb[idx + 1] = g;
                    rgb[idx + 2] = b;
                }
            }
        }
    }
}

// Simple text rendering (8x8 bitmap font, basic ASCII)
static void draw_text(uint8_t* rgb, int w, int h,
                       int x0, int y0, const char* text,
                       uint8_t r, uint8_t g, uint8_t b, int scale) {
    // Minimal 5x7 bitmap font for digits, letters, and basic punctuation
    // Just draw a dark background rectangle for the text area
    int len = (int)strlen(text);
    int tw = len * 6 * scale;
    int th = 8 * scale;
    for (int y = y0 - 2; y < y0 + th + 2; y++)
        for (int x = x0 - 2; x < x0 + tw + 2; x++)
            if (x >= 0 && x < w && y >= 0 && y < h) {
                int idx = (y * w + x) * 3;
                rgb[idx + 0] = (uint8_t)(rgb[idx + 0] * 0.3f);
                rgb[idx + 1] = (uint8_t)(rgb[idx + 1] * 0.3f);
                rgb[idx + 2] = (uint8_t)(rgb[idx + 2] * 0.3f);
            }
    (void)r; (void)g; (void)b; (void)text; (void)scale;
    // Note: for a real demo, link with a font renderer. This just darkens the area.
}

int main(int argc, char** argv) {
    std::string model_path;
    std::string video_path = "data/test_video.mp4";
    std::string output_path = "demo_output.mp4";
    std::string text_prompt;
    float px = 315.0f, py = 250.0f;
    int n_frames = 30;
    bool use_gpu = true;
    bool have_point = false;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--model" && i + 1 < argc) { model_path = argv[++i]; }
        else if (arg == "--video" && i + 1 < argc) { video_path = argv[++i]; }
        else if (arg == "--output" && i + 1 < argc) { output_path = argv[++i]; }
        else if (arg == "--prompt" && i + 1 < argc) { text_prompt = argv[++i]; }
        else if (arg == "--point-x" && i + 1 < argc) { px = (float)atof(argv[++i]); have_point = true; }
        else if (arg == "--point-y" && i + 1 < argc) { py = (float)atof(argv[++i]); have_point = true; }
        else if (arg == "--n-frames" && i + 1 < argc) { n_frames = atoi(argv[++i]); }
        else if (arg == "--no-gpu") { use_gpu = false; }
        else if (arg == "--help" || arg == "-h") {
            fprintf(stderr,
                "Usage: %s [options]\n"
                "  --model <path>    Model .ggml file\n"
                "  --video <path>    Input video        (default: data/test_video.mp4)\n"
                "  --prompt <text>   Text prompt for SAM3 detection (e.g. \"car\")\n"
                "  --point-x <f>     Click point X      (default: 315.0)\n"
                "  --point-y <f>     Click point Y      (default: 250.0)\n"
                "  --n-frames <n>    Frames to track    (default: 30)\n"
                "  --output <path>   Output video       (default: demo_output.mp4)\n"
                "  --no-gpu          Force CPU backend\n", argv[0]);
            return 0;
        } else {
            fprintf(stderr, "Unknown option: %s\n", arg.c_str());
            return 1;
        }
    }

    if (model_path.empty()) {
        // Prefer SAM3 for text prompts, SAM2 for point prompts
        const char* sam3_candidates[] = {
            "models/sam3-q4_0.ggml",
            "models/sam3-f16.ggml",
        };
        const char* sam2_candidates[] = {
            "models/sam2.1_hiera_tiny_f16.ggml",
            "models/sam2.1_hiera_tiny_q4_0.ggml",
        };
        auto try_find = [](const char* paths[], int n) -> std::string {
            for (int i = 0; i < n; i++) {
                FILE* f = fopen(paths[i], "r");
                if (f) { fclose(f); return paths[i]; }
            }
            return "";
        };
        if (!text_prompt.empty()) {
            model_path = try_find(sam3_candidates, 2);
            if (model_path.empty()) model_path = try_find(sam2_candidates, 2);
        } else {
            model_path = try_find(sam2_candidates, 2);
            if (model_path.empty()) model_path = try_find(sam3_candidates, 2);
        }
        if (model_path.empty()) {
            fprintf(stderr, "ERROR: no model found. Use --model <path>\n");
            return 1;
        }
    }

    fprintf(stderr, "Model:  %s\n", model_path.c_str());
    fprintf(stderr, "Video:  %s\n", video_path.c_str());
    if (!text_prompt.empty())
        fprintf(stderr, "Prompt: \"%s\"\n", text_prompt.c_str());
    else
        fprintf(stderr, "Point:  (%.1f, %.1f)\n", px, py);
    fprintf(stderr, "Frames: %d\n", n_frames);
    fprintf(stderr, "Output: %s\n\n", output_path.c_str());

    // Load model
    sam3_params params;
    params.model_path = model_path;
    params.use_gpu = use_gpu;
    params.n_threads = 4;

    auto model = sam3_load_model(params);
    if (!model) { fprintf(stderr, "ERROR: failed to load model\n"); return 1; }
    fprintf(stderr, "Backend: %s\n", sam3_get_backend_name(*model));

    auto state = sam3_create_state(*model, params);
    if (!state) { fprintf(stderr, "ERROR: failed to create state\n"); return 1; }

    bool visual_only = sam3_is_visual_only(*model);
    bool use_text = !text_prompt.empty();

    if (use_text && visual_only) {
        fprintf(stderr, "ERROR: text prompt requires full SAM3 model (not visual-only/SAM2)\n");
        return 1;
    }

    sam3_tracker_ptr tracker;
    if (use_text) {
        sam3_video_params vp;
        vp.text_prompt = text_prompt;
        vp.hotstart_delay = 0;
        vp.max_keep_alive = 100;
        tracker = sam3_create_tracker(*model, vp);
    } else if (visual_only) {
        sam3_visual_track_params vtp;
        tracker = sam3_create_visual_tracker(*model, vtp);
    } else {
        sam3_video_params vp;
        vp.hotstart_delay = 0;
        tracker = sam3_create_tracker(*model, vp);
    }
    if (!tracker) { fprintf(stderr, "ERROR: failed to create tracker\n"); return 1; }

    // Get video info
    auto vinfo = sam3_get_video_info(video_path);
    if (vinfo.n_frames <= 0) {
        fprintf(stderr, "ERROR: cannot read video\n");
        return 1;
    }
    if (n_frames > vinfo.n_frames) n_frames = vinfo.n_frames;
    fprintf(stderr, "Video: %dx%d, %d frames\n", vinfo.width, vinfo.height, vinfo.n_frames);

    // Open ffmpeg pipe for output video
    char ffmpeg_cmd[1024];
    snprintf(ffmpeg_cmd, sizeof(ffmpeg_cmd),
             "ffmpeg -y -f rawvideo -pix_fmt rgb24 -s %dx%d -r 10 "
             "-i pipe:0 -c:v libx264 -pix_fmt yuv420p -crf 18 \"%s\" 2>%s",
             vinfo.width, vinfo.height, output_path.c_str(), SAM3_NULL_DEV);
    FILE* ffmpeg_pipe = popen(ffmpeg_cmd, SAM3_POPEN_WRITE);
    if (!ffmpeg_pipe) {
        fprintf(stderr, "ERROR: failed to open ffmpeg pipe\n");
        return 1;
    }

    // Process frames
    std::vector<uint8_t> frame_rgb;
    int64_t t_total_start = ggml_time_us();

    for (int f = 0; f < n_frames; f++) {
        auto frame = sam3_decode_video_frame(video_path, f);
        if (frame.data.empty()) {
            fprintf(stderr, "ERROR: failed to decode frame %d\n", f);
            break;
        }

        int64_t t0 = ggml_time_us();
        sam3_result result;

        if (use_text) {
            // Text-prompted: sam3_track_frame handles detection + tracking
            result = sam3_track_frame(*tracker, *state, *model, frame);
        } else if (f == 0) {
            // Point-prompted frame 0: encode + add instance
            if (!sam3_encode_image(*state, *model, frame)) {
                fprintf(stderr, "ERROR: encode failed\n");
                break;
            }
            sam3_pvs_params pvs;
            pvs.pos_points.push_back({px, py});
            pvs.multimask = false;
            int inst_id = sam3_tracker_add_instance(*tracker, *state, *model, pvs);
            if (inst_id < 0) {
                fprintf(stderr, "ERROR: add_instance failed\n");
                break;
            }
            auto seg = sam3_segment_pvs(*state, *model, pvs);
            if (!seg.detections.empty()) {
                result = seg;
            }
        } else {
            // Point-prompted subsequent frames: propagate
            if (visual_only) {
                result = sam3_propagate_frame(*tracker, *state, *model, frame);
            } else {
                result = sam3_track_frame(*tracker, *state, *model, frame);
            }
        }

        double dt = (ggml_time_us() - t0) / 1000.0;
        double fps = dt > 0 ? 1000.0 / dt : 0;

        // Render overlay
        frame_rgb = frame.data;  // copy for modification

        // Draw mask overlay for each detection
        uint8_t colors[][3] = {
            {50, 200, 255}, {255, 100, 50}, {100, 255, 50},
            {255, 50, 200}, {200, 200, 50}, {50, 255, 200}
        };
        for (size_t d = 0; d < result.detections.size(); d++) {
            auto& det = result.detections[d];
            if (det.mask.data.empty()) continue;
            int ci = d % 6;
            overlay_mask(frame_rgb.data(), frame.width, frame.height,
                         det.mask, colors[ci][0], colors[ci][1], colors[ci][2], 100);
            draw_mask_outline(frame_rgb.data(), frame.width, frame.height,
                              det.mask, 255, 255, 255, 1);
        }

        // Draw click point
        draw_circle(frame_rgb.data(), frame.width, frame.height,
                    (int)px, (int)py, 8, 255, 50, 50);
        draw_circle(frame_rgb.data(), frame.width, frame.height,
                    (int)px, (int)py, 10, 255, 255, 255);

        // Write frame to ffmpeg
        fwrite(frame_rgb.data(), 1, frame_rgb.size(), ffmpeg_pipe);

        fprintf(stderr, "  frame %2d/%d  %6.0f ms  %4.1f fps  %zu det\n",
                f, n_frames - 1, dt, fps, result.detections.size());

        // Also save a preview PNG for frame 5
        if (f == 5 || (f == n_frames - 1 && n_frames <= 5)) {
            std::string preview = output_path;
            auto dot = preview.rfind('.');
            if (dot != std::string::npos) preview = preview.substr(0, dot);
            preview += "_preview.png";
            stbi_write_png(preview.c_str(), frame.width, frame.height, 3,
                           frame_rgb.data(), frame.width * 3);
            fprintf(stderr, "  -> preview saved: %s\n", preview.c_str());
        }
    }

    pclose(ffmpeg_pipe);

    double t_total = (ggml_time_us() - t_total_start) / 1000.0;
    fprintf(stderr, "\nTotal: %.1f s for %d frames\n", t_total / 1000.0, n_frames);
    fprintf(stderr, "Output: %s\n", output_path.c_str());

    return 0;
}
