/**
 * demo_segment — single-image segmentation with mask overlay output.
 *
 * Usage:
 *   demo_segment --model <path> --image <path> --prompt "road" --output out.png
 *   demo_segment --model <path> --image <path> --point-x 400 --point-y 300
 */

#include "sam3.h"
#include "ggml.h"
#include "stb_image_write.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static void overlay_mask(uint8_t* rgb, int w, int h,
                          const sam3_mask& mask,
                          uint8_t mr, uint8_t mg, uint8_t mb, int alpha) {
    if (mask.width != w || mask.height != h) return;
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++)
            if (mask.data[y * w + x] > 0) {
                int i = (y * w + x) * 3;
                rgb[i+0] = (uint8_t)((rgb[i+0] * (255-alpha) + mr * alpha) / 255);
                rgb[i+1] = (uint8_t)((rgb[i+1] * (255-alpha) + mg * alpha) / 255);
                rgb[i+2] = (uint8_t)((rgb[i+2] * (255-alpha) + mb * alpha) / 255);
            }
}

static void draw_outline(uint8_t* rgb, int w, int h, const sam3_mask& mask,
                          uint8_t r, uint8_t g, uint8_t b) {
    if (mask.width != w || mask.height != h) return;
    for (int y = 1; y < h-1; y++)
        for (int x = 1; x < w-1; x++)
            if (mask.data[y*w+x] > 0 &&
                (mask.data[(y-1)*w+x]==0 || mask.data[(y+1)*w+x]==0 ||
                 mask.data[y*w+x-1]==0 || mask.data[y*w+x+1]==0)) {
                for (int dy = -1; dy <= 1; dy++)
                    for (int dx = -1; dx <= 1; dx++) {
                        int px=x+dx, py=y+dy;
                        if (px>=0&&px<w&&py>=0&&py<h) {
                            int i = (py*w+px)*3;
                            rgb[i]=r; rgb[i+1]=g; rgb[i+2]=b;
                        }
                    }
            }
}

int main(int argc, char** argv) {
    std::string model_path, image_path, output_path = "segment_output.png";
    std::string text_prompt;
    float px = -1, py = -1;
    bool use_gpu = true;

    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if      (a == "--model"   && i+1<argc) model_path = argv[++i];
        else if (a == "--image"   && i+1<argc) image_path = argv[++i];
        else if (a == "--output"  && i+1<argc) output_path = argv[++i];
        else if (a == "--prompt"  && i+1<argc) text_prompt = argv[++i];
        else if (a == "--point-x" && i+1<argc) { px = (float)atof(argv[++i]); }
        else if (a == "--point-y" && i+1<argc) { py = (float)atof(argv[++i]); }
        else if (a == "--no-gpu") use_gpu = false;
        else { fprintf(stderr, "Unknown: %s\n", a.c_str()); return 1; }
    }

    if (image_path.empty()) {
        fprintf(stderr, "Usage: %s --image <path> [--prompt <text>|--point-x/y] [--model <path>]\n", argv[0]);
        return 1;
    }

    if (model_path.empty()) {
        const char* c[] = {"models/sam3-q4_0.ggml","models/sam3-f16.ggml",
                           "models/sam2.1_hiera_tiny_f16.ggml",nullptr};
        for (int i=0; c[i]; i++) { FILE* f=fopen(c[i],"r"); if(f){fclose(f);model_path=c[i];break;} }
        if (model_path.empty()) { fprintf(stderr, "No model found\n"); return 1; }
    }

    if (text_prompt.empty() && px < 0) {
        fprintf(stderr, "Need --prompt or --point-x/--point-y\n");
        return 1;
    }

    fprintf(stderr, "Model:  %s\n", model_path.c_str());
    fprintf(stderr, "Image:  %s\n", image_path.c_str());
    if (!text_prompt.empty()) fprintf(stderr, "Prompt: \"%s\"\n", text_prompt.c_str());
    else fprintf(stderr, "Point:  (%.0f, %.0f)\n", px, py);

    sam3_params params;
    params.model_path = model_path;
    params.use_gpu = use_gpu;
    params.n_threads = 4;

    auto model = sam3_load_model(params);
    if (!model) { fprintf(stderr, "ERROR: load failed\n"); return 1; }

    auto state = sam3_create_state(*model, params);
    if (!state) { fprintf(stderr, "ERROR: state failed\n"); return 1; }

    auto image = sam3_load_image(image_path);
    if (image.data.empty()) { fprintf(stderr, "ERROR: image load failed\n"); return 1; }
    fprintf(stderr, "Image:  %dx%d\n", image.width, image.height);

    int64_t t0 = ggml_time_us();
    if (!sam3_encode_image(*state, *model, image)) {
        fprintf(stderr, "ERROR: encode failed\n"); return 1;
    }
    double encode_ms = (ggml_time_us() - t0) / 1000.0;
    fprintf(stderr, "Encode: %.0f ms\n", encode_ms);

    sam3_result result;
    t0 = ggml_time_us();

    if (!text_prompt.empty()) {
        sam3_pcs_params pcs;
        pcs.text_prompt = text_prompt;
        pcs.score_threshold = 0.3f;
        result = sam3_segment_pcs(*state, *model, pcs);
    } else {
        sam3_pvs_params pvs;
        pvs.pos_points.push_back({px, py});
        pvs.multimask = false;
        result = sam3_segment_pvs(*state, *model, pvs);
    }
    double seg_ms = (ggml_time_us() - t0) / 1000.0;
    fprintf(stderr, "Segment: %.0f ms (%zu detections)\n", seg_ms, result.detections.size());

    // Render
    auto rgb = image.data;
    uint8_t colors[][3] = {{50,200,255},{255,100,50},{100,255,50},{255,50,200},{200,200,50}};
    for (size_t d = 0; d < result.detections.size(); d++) {
        auto& det = result.detections[d];
        if (det.mask.data.empty()) continue;
        int ci = d % 5;
        overlay_mask(rgb.data(), image.width, image.height, det.mask,
                     colors[ci][0], colors[ci][1], colors[ci][2], 120);
        draw_outline(rgb.data(), image.width, image.height, det.mask, 255, 255, 255);
        fprintf(stderr, "  det %zu: score=%.3f iou=%.3f box=(%.0f,%.0f)-(%.0f,%.0f)\n",
                d, det.score, det.iou_score, det.box.x0, det.box.y0, det.box.x1, det.box.y1);
    }

    stbi_write_png(output_path.c_str(), image.width, image.height, 3, rgb.data(), image.width*3);
    fprintf(stderr, "Output: %s\n", output_path.c_str());
    fprintf(stderr, "Total:  %.0f ms\n", encode_ms + seg_ms);
    return 0;
}
