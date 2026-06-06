#include <cuda_runtime.h>
#include <stdio.h>

__global__ void add_kernel(const float *a, const float *b, float *c) {
    int i = threadIdx.x;
    c[i] = a[i] + b[i];
}

int main(void) {
    const int n = 4;
    float h_a[n] = {1.0f, 2.0f, 3.0f, 4.0f};
    float h_b[n] = {10.0f, 20.0f, 30.0f, 40.0f};
    float h_c[n] = {0.0f, 0.0f, 0.0f, 0.0f};
    float *d_a = NULL;
    float *d_b = NULL;
    float *d_c = NULL;

    cudaError_t err = cudaMalloc((void **)&d_a, n * sizeof(float));
    if (err != cudaSuccess) {
        printf("cudaMalloc d_a failed: %s\n", cudaGetErrorString(err));
        return 1;
    }
    cudaMalloc((void **)&d_b, n * sizeof(float));
    cudaMalloc((void **)&d_c, n * sizeof(float));
    cudaMemcpy(d_a, h_a, n * sizeof(float), cudaMemcpyHostToDevice);
    cudaMemcpy(d_b, h_b, n * sizeof(float), cudaMemcpyHostToDevice);
    add_kernel<<<1, n>>>(d_a, d_b, d_c);
    err = cudaDeviceSynchronize();
    if (err != cudaSuccess) {
        printf("kernel failed: %s\n", cudaGetErrorString(err));
        return 2;
    }
    cudaMemcpy(h_c, d_c, n * sizeof(float), cudaMemcpyDeviceToHost);
    printf("CUDA result: %.1f %.1f %.1f %.1f\n", h_c[0], h_c[1], h_c[2], h_c[3]);
    cudaFree(d_a);
    cudaFree(d_b);
    cudaFree(d_c);
    return 0;
}
