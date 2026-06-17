#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"

#ifdef GGML_USE_CUDA
#include "ggml-cuda.h"
#endif

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <vector>

static ggml_context * make_ctx(size_t n_tensors) {
    const ggml_init_params params = {
        /*.mem_size   =*/ ggml_tensor_overhead() * (n_tensors + 32) + ggml_graph_overhead_custom(64, false) + 256 * 1024,
        /*.mem_buffer =*/ nullptr,
        /*.no_alloc   =*/ true,
    };
    return ggml_init(params);
}

static void check_close(const std::vector<float> & got, const std::vector<float> & want) {
    GGML_ASSERT(got.size() == want.size());
    for (size_t i = 0; i < got.size(); ++i) {
        if (fabsf(got[i] - want[i]) > 1e-6f) {
            fprintf(stderr, "mismatch at %zu: got=%f want=%f\n", i, got[i], want[i]);
            GGML_ABORT("test failed");
        }
    }
}

#ifdef GGML_USE_CUDA
static void test_add_f32_f16_binbcast(ggml_backend_t backend, int nf) {
    const int64_t ne0 = 320;
    const int64_t ne1 = 32;

    ggml_context * ctx_data = make_ctx(1 + nf);
    ggml_context * ctx_graph = make_ctx(8 + nf);

    ggml_tensor * a = ggml_new_tensor_2d(ctx_data, GGML_TYPE_F32, ne0, ne1);
    std::vector<ggml_tensor *> b(nf);
    for (int i = 0; i < nf; ++i) {
        b[i] = ggml_new_tensor_2d(ctx_data, GGML_TYPE_F16, ne0, 1);
    }

    ggml_tensor * out = a;
    for (int i = 0; i < nf; ++i) {
        out = ggml_add(ctx_graph, out, b[i]);
    }

    ggml_cgraph * graph = ggml_new_graph(ctx_graph);
    ggml_build_forward_expand(graph, out);

    ggml_backend_buffer_t data_buf = ggml_backend_alloc_ctx_tensors(ctx_data, backend);
    GGML_ASSERT(data_buf != nullptr);

    ggml_gallocr_t galloc = ggml_gallocr_new(ggml_backend_get_default_buffer_type(backend));
    GGML_ASSERT(ggml_gallocr_reserve(galloc, graph));
    GGML_ASSERT(ggml_gallocr_alloc_graph(galloc, graph));

    std::vector<float> a_data(ne0 * ne1);
    std::vector<float> b_data(ne0);
    std::vector<ggml_fp16_t> b_f16(ne0);
    std::vector<float> expected(ne0 * ne1);
    std::vector<float> got(ne0 * ne1);

    for (int64_t x = 0; x < ne0; ++x) {
        b_data[x] = 0.5f * float((x % 7) - 3);
        b_f16[x] = ggml_fp32_to_fp16(b_data[x]);
        b_data[x] = ggml_fp16_to_fp32(b_f16[x]);
    }

    for (int64_t y = 0; y < ne1; ++y) {
        for (int64_t x = 0; x < ne0; ++x) {
            const size_t i = y * ne0 + x;
            a_data[i] = float((i % 11) - 5);
            expected[i] = a_data[i] + nf * b_data[x];
        }
    }

    ggml_backend_tensor_set(a, a_data.data(), 0, a_data.size() * sizeof(float));
    for (int i = 0; i < nf; ++i) {
        ggml_backend_tensor_set(b[i], b_f16.data(), 0, b_f16.size() * sizeof(ggml_fp16_t));
    }

    const ggml_status status = ggml_backend_graph_compute(backend, graph);
    GGML_ASSERT(status == GGML_STATUS_SUCCESS);
    ggml_backend_tensor_get(out, got.data(), 0, got.size() * sizeof(float));

    check_close(got, expected);

    ggml_gallocr_free(galloc);
    ggml_backend_buffer_free(data_buf);
    ggml_free(ctx_graph);
    ggml_free(ctx_data);
}
#endif

int main() {
#ifndef GGML_USE_CUDA
    return 0;
#else
    ggml_backend_t backend = ggml_backend_cuda_init(0);
    if (backend == nullptr) {
        return 0;
    }

    test_add_f32_f16_binbcast(backend, 1);
    test_add_f32_f16_binbcast(backend, 2);

    ggml_backend_free(backend);
    return 0;
#endif
}
